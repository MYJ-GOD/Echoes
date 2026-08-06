"""
LangGraph RAG 工作流定义
"""
import logging
from langgraph.graph import StateGraph, END

from app.graph.state import State
from app.graph.nodes import (
    guardrail_node,
    query_rewrite_node,
    intent_classification_node,
    retrieval_node,
    rerank_node,
    should_use_rag,
    generate_rag_node,
    generate_fallback_node,
    grounding_check_node,
    citation_node,
)

logger = logging.getLogger(__name__)


def build_rag_workflow() -> StateGraph:
    """构建 RAG 工作流"""

    workflow = StateGraph(State)

    # ============== 添加节点 ==============
    workflow.add_node("guardrail", guardrail_node)
    workflow.add_node("query_rewrite", query_rewrite_node)
    workflow.add_node("intent_classify", intent_classification_node)
    workflow.add_node("retrieve", retrieval_node)
    workflow.add_node("rerank", rerank_node)
    workflow.add_node("generate_rag", generate_rag_node)
    workflow.add_node("generate_fallback", generate_fallback_node)
    workflow.add_node("grounding_check", grounding_check_node)
    workflow.add_node("cite", citation_node)

    # ============== 定义边 ==============
    # 入口 → Guardrail
    workflow.set_entry_point("guardrail")

    # Guardrail → Query Rewrite（无论是否通过都继续，节点内部处理拦截）
    workflow.add_edge("guardrail", "query_rewrite")

    # Query Rewrite → Intent Classify
    workflow.add_edge("query_rewrite", "intent_classify")

    # Intent Classify → Retrieve
    workflow.add_edge("intent_classify", "retrieve")

    # Retrieve → Rerank
    workflow.add_edge("retrieve", "rerank")

    # Rerank → 条件路由
    workflow.add_conditional_edges(
        "rerank",
        should_use_rag,
        {
            "rag_path": "generate_rag",
            "fallback_path": "generate_fallback",
        }
    )

    # 生成 → Grounding 检查
    workflow.add_edge("generate_rag", "grounding_check")
    workflow.add_edge("generate_fallback", "grounding_check")

    # Grounding 检查 → 引用标注
    workflow.add_edge("grounding_check", "cite")

    # 引用标注 → 结束
    workflow.add_edge("cite", END)

    return workflow


# 编译工作流
rag_workflow = build_rag_workflow().compile()
