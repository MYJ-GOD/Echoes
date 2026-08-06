"""
LangGraph 工作流节点实现

Phase 3 增强：
- Query 改写（拼写纠错、指代消解、查询扩展）
- 意图分类（多类别支持）
- 对话管理
"""
import logging
from typing import Literal

from app.graph.state import State
from app.models.guardrail import check_guardrail

logger = logging.getLogger(__name__)


# ============== Guardrail 节点 ==============

async def guardrail_node(state: State) -> State:
    """
    Guardrail 节点 - 安全护栏
    - 检测敏感/违规内容
    - 拦截恶意查询
    """
    query = state.get("query", "")
    result = await check_guardrail(query)

    if not result.passed:
        return {
            "guardrail_passed": False,
            "guardrail_message": result.message,
            "should_use_rag": False,
            "response": result.message,  # 直接返回提示
        }

    return {"guardrail_passed": True}


# ============== Query 改写节点 ==============

async def query_rewrite_node(state: State) -> State:
    """
    Query 改写节点 - 优化用户查询
    - 拼写纠错
    - 查询扩展
    - 指代消解
    """
    from app.services.llm_service import rewrite_query
    from app.services.conversation_service import resolve_reference, get_recent_messages

    query = state.get("query", "")
    conversation_id = state.get("conversation_id", "")

    # 指代消解（如果有对话历史）
    if conversation_id:
        resolved_query = await resolve_reference(query, conversation_id)
        history = await get_recent_messages(conversation_id, limit=6)
    else:
        resolved_query = query
        history = None

    # LLM 改写（带对话历史上下文）
    rewrite_result = await rewrite_query(resolved_query, conversation_history=history)

    return {
        "rewritten_query": rewrite_result["rewritten_query"],
        "query_rewrite_info": rewrite_result,
    }


# ============== 意图分类节点 ==============

async def intent_classification_node(state: State) -> State:
    """
    意图分类节点 - 识别用户意图
    - knowledge_query: 知识查询类问题
    - chat: 闲聊
    - task: 任务执行
    - other: 其他
    """
    from app.services.llm_service import classify_intent

    query = state.get("rewritten_query") or state.get("query", "")

    # LLM 意图分类
    result = await classify_intent(query)

    return {
        "query_intent": result["intent"],
        "intent_confidence": result["confidence"],
        "intent_scores": result["all_scores"],
    }


# ============== 检索节点 ==============

async def retrieval_node(state: State) -> State:
    """
    检索节点 - 从向量库检索相关内容

    支持：
    - 纯向量检索
    - 混合检索（向量 + BM25）
    """
    from app.services.qdrant_service import search_knowledge, search_knowledge_hybrid
    from app.services.embedding_service import generate_embedding

    query = state.get("rewritten_query") or state.get("query", "")
    original_query = state.get("query", "")
    kb_ids = state.get("kb_ids", [])
    top_k = state.get("top_k", 5)
    use_hybrid = state.get("use_hybrid", True)  # 默认使用混合检索

    try:
        # 生成查询向量
        query_vector = await generate_embedding(query)

        if use_hybrid:
            # 混合检索
            chunks = await search_knowledge_hybrid(
                query_vector=query_vector,
                query_text=original_query,
                kb_ids=kb_ids,
                top_k=top_k * 2,  # 初检更多结果
                alpha=0.7,
            )
        else:
            # 纯向量检索
            chunks = await search_knowledge(
                query_vector=query_vector,
                kb_ids=kb_ids,
                top_k=top_k,
                threshold=0.5,
            )

        return {
            "retrieved_chunks": chunks,
            "retrieval_count": len(chunks),
            "retrieval_method": "hybrid" if use_hybrid else "vector",
        }
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        return {
            "retrieved_chunks": [],
            "retrieval_count": 0,
        }


# ============== 重排序节点 ==============

async def rerank_node(state: State) -> State:
    """
    重排序节点 - 对检索结果重新排序
    """
    from app.services.rerank_service import rerank_chunks

    query = state.get("rewritten_query") or state.get("query", "")
    chunks = state.get("retrieved_chunks", [])

    if not chunks:
        return {"reranked_chunks": []}

    try:
        reranked = await rerank_chunks(query, chunks, top_k=3)
        return {"reranked_chunks": reranked}
    except Exception as e:
        logger.error(f"Rerank failed: {e}")
        return {"reranked_chunks": chunks}


# ============== 路由决策函数 ==============

def should_use_rag(state: State) -> Literal["rag_path", "fallback_path"]:
    """
    条件路由 - 决定是否使用 RAG
    """
    # Guardrail 未通过 → 直接返回
    if not state.get("guardrail_passed", True):
        return "fallback_path"

    # 意图为闲聊 → 不需要 RAG
    if state.get("query_intent") == "chat":
        return "fallback_path"

    # 检索结果为空 → 降级
    if not state.get("reranked_chunks"):
        return "fallback_path"

    return "rag_path"


# ============== 回答生成节点 ==============

async def generate_rag_node(state: State) -> State:
    """
    RAG 生成节点 - 基于检索结果生成回答
    """
    from app.services.llm_service import generate_with_context

    context = state.get("reranked_chunks", [])
    query = state.get("rewritten_query") or state.get("query", "")

    try:
        response_chunks = await generate_with_context(
            context=context,
            query=query,
            stream=True,
        )
        return {"response_chunks": response_chunks}
    except Exception as e:
        logger.error(f"RAG generation failed: {e}")
        return {"response_chunks": [], "error": str(e)}


async def generate_fallback_node(state: State) -> State:
    """
    降级生成节点 - 纯 LLM 生成（无检索结果时）
    """
    from app.services.llm_service import generate_plain

    query = state.get("rewritten_query") or state.get("query", "")

    try:
        response_chunks = await generate_plain(
            query=query,
            stream=True,
        )
        return {
            "response_chunks": response_chunks,
            "fallback_reason": state.get("fallback_reason", "no_retrieval_results"),
        }
    except Exception as e:
        logger.error(f"Fallback generation failed: {e}")
        return {"response_chunks": [], "error": str(e)}


# ============== Grounding 检查节点 ==============

async def grounding_check_node(state: State) -> State:
    """
    Grounding 检查节点 - 验证生成内容是否基于检索结果

    检查逻辑：
    1. 如果是 fallback 路径（无检索结果），跳过检查
    2. 计算生成内容与检索结果的关键词重叠率
    3. 重叠率过低说明模型"幻觉"，标记警告
    """
    response_chunks = state.get("response_chunks", [])
    reranked_chunks = state.get("reranked_chunks", [])
    fallback_reason = state.get("fallback_reason")

    # fallback 路径无需检查
    if fallback_reason or not reranked_chunks:
        return {"grounding_passed": True, "grounding_score": 1.0}

    response_text = "".join(response_chunks)
    if not response_text:
        return {"grounding_passed": True, "grounding_score": 1.0}

    # 提取检索结果中的关键词（取每个 chunk 的前 200 字）
    context_snippets = []
    for chunk in reranked_chunks:
        content = chunk.get("content", "")
        if content:
            context_snippets.append(content[:200])

    if not context_snippets:
        return {"grounding_passed": True, "grounding_score": 1.0}

    # 计算简单的关键词重叠率
    # 将 response 按标点和空格拆成片段，检查有多少出现在 context 中
    import re
    response_segments = re.split(r'[，。！？、；：\s]+', response_text)
    response_segments = [s for s in response_segments if len(s) >= 2]

    if not response_segments:
        return {"grounding_passed": True, "grounding_score": 1.0}

    context_text = " ".join(context_snippets)
    matched = sum(1 for seg in response_segments if seg in context_text)
    score = matched / len(response_segments)

    # 阈值：至少 15% 的片段能在 context 中找到（宽松阈值，避免误判）
    passed = score >= 0.15

    if not passed:
        logger.warning(
            f"Grounding check failed: score={score:.2f}, "
            f"matched={matched}/{len(response_segments)}"
        )

    return {"grounding_passed": passed, "grounding_score": score}


# ============== 引用标注节点 ==============

async def citation_node(state: State) -> State:
    """
    引用标注节点 - 添加引用来源
    """
    chunks = state.get("reranked_chunks", [])

    if not chunks:
        return {"citations": []}

    try:
        from app.services.llm_service import add_citations
        citations = await add_citations("", chunks)  # response 在后续组装
        return {"citations": citations}
    except Exception as e:
        logger.error(f"Citation failed: {e}")
        return {"citations": []}
