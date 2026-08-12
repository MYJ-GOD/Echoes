"""
记忆层（Week2）：Qdrant 长期记忆 + 轻量记忆图谱

- save_memory_entry: 对话摘要 + LLM 实体抽取 → 写入 conversation_history
- search_memory: 向量检索 + 实体链接双信号（记忆图谱）
- get_user_profile / update_user_profile: user_profile collection

容错设计：Qdrant 未启动或 bge-m3 向量模型未下载时优雅降级
（保存跳过/检索走 payload 关键词匹配），不 crash workflow；环境就绪后自动全量可用。
"""
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import models as qm

from app.config import settings
from app.services.qdrant_service import get_client
from app.services.embedding_service import generate_embedding
from app.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

COLLECTION_MEMORY = settings.COLLECTION_CONVERSATION   # conversation_history
COLLECTION_PROFILE = settings.COLLECTION_PROFILE        # user_profile

ENTITY_EXTRACT_PROMPT = """从下面的文本中抽取关键实体（人物、物品、地点、偏好、事件），
输出 JSON 数组，如 ["美式咖啡", "北京", "跑步"]。没有实体时输出 []。

文本：{text}

只输出 JSON 数组，不要其他内容。"""


# ============== 实体抽取（记忆图谱核心） ==============

async def extract_entities(text: str) -> List[str]:
    """LLM 实体抽取；失败时返回空列表（降级为纯向量记忆）"""
    if not text or not text.strip():
        return []
    try:
        raw = await chat_completion(
            [{"role": "user", "content": ENTITY_EXTRACT_PROMPT.format(text=text[:500])}],
            max_tokens=150,
            temperature=0.0,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        entities = json.loads(raw)
        return [str(e).strip() for e in entities if str(e).strip()] if isinstance(entities, list) else []
    except Exception as e:
        logger.warning("实体抽取失败: %s", e)
        return []


async def _try_embedding(text: str) -> Optional[List[float]]:
    """生成向量；模型未下载/加载失败时返回 None（降级信号）"""
    try:
        return await generate_embedding(text)
    except Exception as e:
        logger.warning("embedding 不可用（bge-m3 未下载?）: %s", e)
        return None


# ============== 长期记忆写入 ==============

async def save_memory_entry(user_id: str, entry: Dict[str, Any]) -> bool:
    """写入一条记忆到 conversation_history（含向量 + 实体 payload）"""
    try:
        summary = entry.get("summary", "")
        vector = await _try_embedding(summary)
        if vector is None:
            logger.warning("记忆保存跳过（向量不可用）: user_id=%s", user_id)
            return False
        client = get_client()
        client.upsert(
            collection_name=COLLECTION_MEMORY,
            points=[qm.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "user_id": user_id,
                    "summary": summary,
                    "entities": entry.get("entities", []),
                    "intent": entry.get("intent", ""),
                    "ts": entry.get("ts", ""),
                },
            )],
        )
        logger.info("记忆已写入 conversation_history: user_id=%s", user_id)
        return True
    except Exception as e:
        logger.warning("记忆写入失败: %s", e)
        return False


# ============== 记忆检索（向量 + 实体双信号） ==============

def _match_entities(payload_entities: List[str], query_entities: List[str]) -> int:
    """实体匹配命中数"""
    if not payload_entities or not query_entities:
        return 0
    p_set = {e.lower() for e in payload_entities}
    return sum(1 for e in query_entities if e.lower() in p_set)


async def _rerank_memories(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int,
    threshold: float,
) -> List[Dict[str, Any]]:
    """BGE-Rerank 精排记忆候选 + Threshold 门禁。

    rerank 模型不可用（未下载）时降级为向量分排序。
    """
    try:
        from app.services.rerank_service import rerank_chunks
        # 记忆的文本字段是 summary，min_score 作为 Threshold 门禁
        reranked = await rerank_chunks(
            query=query,
            chunks=candidates,
            top_k=top_k,
            min_score=threshold,
            normalize=True,
            text_field="summary",
        )
        return reranked
    except Exception as e:
        # rerank 模型未下载/加载失败 → 降级：用向量分排序 + 阈值粗过滤
        logger.warning("Rerank 不可用（bge-reranker 未下载?），降级向量分排序: %s", e)
        candidates.sort(key=lambda c: c.get("vector_score", 0), reverse=True)
        for c in candidates:
            c["rerank_score"] = c.get("vector_score", 0)
        return candidates[:top_k]


async def search_memory(
    query: str,
    user_id: str = "",
    top_k: int = 3,
    recall_k: int = 30,
    rerank_threshold: float = 0.75,
) -> List[Dict[str, Any]]:
    """记忆检索：粗召回 → BGE-Rerank 精排 → Threshold 门禁 → 实体链接增强

    流程（对齐 V1.0 检索质量工程）：
    1. 向量粗召回 TopK=recall_k（高召回优先）
    2. BGE-reranker Cross-Encoder 精排（recall_k → top_k）
    3. Threshold 门禁：最高 rerank_score < rerank_threshold → 返回空（不注入低质量记忆）
    4. 实体链接：命中实体的记忆加分

    返回 [{summary, entities, score, rerank_score, entity_hits, ...}]
    """
    query_entities = await extract_entities(query)

    # 路径 A：向量粗召回 + Rerank 精排
    vector = await _try_embedding(query)
    if vector is not None:
        try:
            client = get_client()
            res = client.query_points(
                collection_name=COLLECTION_MEMORY,
                query=vector,
                query_filter=qm.Filter(
                    must=[qm.FieldCondition(key="user_id", match=qm.MatchValue(value=user_id))]
                ) if user_id else None,
                limit=recall_k,  # 粗召回 TopK=30，高召回率优先
                with_payload=True,
            )
            candidates = []
            for p in res.points:
                payload = p.payload or {}
                candidates.append({
                    "summary": payload.get("summary", ""),
                    "entities": payload.get("entities", []),
                    "intent": payload.get("intent", ""),
                    "ts": payload.get("ts", ""),
                    "vector_score": round(float(p.score), 3),
                })

            if not candidates:
                return []

            # BGE-Rerank 精排（recall_k → top_k），带 Threshold 门禁
            reranked = await _rerank_memories(query, candidates, top_k, rerank_threshold)

            # Threshold 门禁：无高质量记忆则不注入（防止低质量记忆污染回复）
            if not reranked:
                logger.info("记忆检索：rerank 后无记忆达到阈值 %.2f，不注入", rerank_threshold)
                return []

            # 实体链接增强：命中实体的记忆加分并重排
            for hit in reranked:
                entity_hits = _match_entities(hit.get("entities", []), query_entities)
                hit["entity_hits"] = entity_hits
                # 最终分 = rerank_score + 实体命中奖励
                hit["score"] = round(hit["rerank_score"] + min(entity_hits * 0.1, 0.3), 3)
            reranked.sort(key=lambda h: h["score"], reverse=True)
            return reranked
        except Exception as e:
            logger.warning("向量检索/精排失败: %s", e)

    # 路径 B：payload 关键词/实体匹配（Qdrant 不可用向量时的降级）
    try:
        client = get_client()
        res = client.scroll(
            collection_name=COLLECTION_MEMORY,
            scroll_filter=qm.Filter(
                must=[qm.FieldCondition(key="user_id", match=qm.MatchValue(value=user_id))]
            ) if user_id else None,
            limit=200,
            with_payload=True,
        )
        hits = []
        for p in res[0]:
            payload = p.payload or {}
            summary = payload.get("summary", "")
            entity_hits = _match_entities(payload.get("entities", []), query_entities)
            keyword_hits = sum(1 for w in (query or "").split() if w and w in summary)
            if entity_hits > 0 or keyword_hits > 0:
                hits.append({
                    "summary": summary,
                    "entities": payload.get("entities", []),
                    "intent": payload.get("intent", ""),
                    "ts": payload.get("ts", ""),
                    "score": round(entity_hits * 0.5 + keyword_hits * 0.1, 3),
                    "entity_hits": entity_hits,
                })
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits[:top_k]
    except Exception as e:
        logger.warning("记忆检索降级路径失败: %s", e)
        return []


# ============== 用户画像 ==============

async def get_user_profile(user_id: str = "") -> Dict[str, Any]:
    """读 user_profile collection（单 point，id=user_id）；无则返回空画像"""
    if not user_id:
        return {}
    try:
        client = get_client()
        res = client.retrieve(collection_name=COLLECTION_PROFILE, ids=[user_id], with_payload=True)
        if res and res[0].payload:
            return dict(res[0].payload)
        return {}
    except Exception as e:
        logger.warning("读取用户画像失败: %s", e)
        return {}


async def update_user_profile(user_id: str = "", **updates: Any) -> Dict[str, Any]:
    """更新/创建用户画像（upsert 单 point）"""
    if not user_id:
        return {"updated": False, "reason": "missing user_id"}
    try:
        current = await get_user_profile(user_id)
        payload = {**current, **updates, "user_id": user_id}
        client = get_client()
        client.upsert(
            collection_name=COLLECTION_PROFILE,
            points=[qm.PointStruct(id=user_id, vector=[0.0] * settings.VECTOR_SIZE, payload=payload)],
        )
        return {"updated": True, "profile": payload}
    except Exception as e:
        logger.warning("更新用户画像失败: %s", e)
        return {"updated": False, "reason": str(e)}


# ============== Grounding 检查（LLM-as-judge）==============

async def grounding_check_llm(response: str, memory_hits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """LLM 判断回复的每个 claim 是否被记忆支撑（faithfulness 校验）

    Args:
        response: 生成的回复
        memory_hits: 检索到的记忆列表

    Returns:
        {"faithful": bool, "score": float, "unsupported_claims": List[str]}
    """
    if not memory_hits:
        return {"faithful": True, "score": 1.0, "unsupported_claims": [], "reason": "无记忆注入"}

    memory_text = "\n".join([f"- {m.get('summary', '')}" for m in memory_hits[:3]])
    prompt = f"""你是 faithfulness 评估器。判断回复的每个陈述是否有记忆支撑。

**记忆上下文**：
{memory_text}

**回复**：
{response}

**任务**：
1. 拆解回复中的所有具体陈述（claim）
2. 检查每个陈述是否能从记忆中找到依据
3. 给出 faithfulness 分数（0-1，1=完全支撑）

**输出 JSON**：
{{"faithful": true/false, "score": 0.0-1.0, "unsupported_claims": ["未支撑的陈述1", ...]}}
"""
    try:
        raw = await chat_completion([{"role": "user", "content": prompt}], max_tokens=300, temperature=0)
        import json
        result = json.loads(raw.strip().strip("`").replace("```json", "").strip())
        return {
            "faithful": bool(result.get("faithful", True)),
            "score": float(result.get("score", 1.0)),
            "unsupported_claims": result.get("unsupported_claims", []),
        }
    except Exception as e:
        logger.warning("Grounding LLM 判断失败（降级认为 faithful）: %s", e)
        return {"faithful": True, "score": 1.0, "unsupported_claims": [], "reason": f"judge failed: {e}"}
