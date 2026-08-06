"""
LangGraph 工作流状态定义
"""
from typing import TypedDict, List, Optional, Literal, Dict, Any


class State(TypedDict, total=False):
    """工作流状态"""

    # ============== 输入 ==============
    query: str
    turn_id: str
    conversation_id: str
    kb_ids: List[str]
    top_k: int

    # ============== Guardrail ==============
    guardrail_passed: bool
    guardrail_message: str

    # ============== Query 改写 ==============
    rewritten_query: str
    query_rewrite_info: Dict[str, Any]  # 改写详情（original_query, changes, use_rewrite）

    # ============== 意图分类 ==============
    query_intent: Literal["knowledge_query", "chat", "task", "other"]
    intent_confidence: float
    intent_scores: Dict[str, float]

    # ============== 检索 ==============
    retrieved_chunks: List[dict]
    retrieval_count: int
    retrieval_method: Literal["hybrid", "vector"]

    # ============== Rerank ==============
    reranked_chunks: List[dict]

    # ============== 路由决策 ==============
    should_use_rag: bool
    fallback_reason: str

    # ============== Grounding ==============
    grounding_passed: bool
    grounding_score: float

    # ============== 生成 ==============
    response: str
    response_chunks: List[str]  # 流式输出用

    # ============== 增强 ==============
    citations: List[dict]

    # ============== 元数据 ==============
    error: Optional[str]
    latency_ms: int
