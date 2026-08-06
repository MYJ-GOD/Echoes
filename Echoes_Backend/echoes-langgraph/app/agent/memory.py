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


async def search_memory(query: str, user_id: str = "", top_k: int = 5) -> List[Dict[str, Any]]:
    """向量检索 + 实体链接双信号；返回 [{summary, entities, score, ...}]"""
    query_entities = await extract_entities(query)

    # 路径 A：向量检索
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
                limit=top_k * 3,
                with_payload=True,
            )
            hits = []
            for p in res.points:
                payload = p.payload or {}
                entity_hits = _match_entities(payload.get("entities", []), query_entities)
                # 融合分：向量相似度 + 实体命中奖励
                score = float(p.score) + min(entity_hits * 0.15, 0.45)
                hits.append({
                    "summary": payload.get("summary", ""),
                    "entities": payload.get("entities", []),
                    "intent": payload.get("intent", ""),
                    "ts": payload.get("ts", ""),
                    "score": round(score, 3),
                    "entity_hits": entity_hits,
                })
            hits.sort(key=lambda h: h["score"], reverse=True)
            return hits[:top_k]
        except Exception as e:
            logger.warning("向量检索失败: %s", e)

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
