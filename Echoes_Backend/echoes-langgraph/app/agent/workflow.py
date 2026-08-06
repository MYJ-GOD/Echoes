"""
Agent 编排 workflow（Week1）

planner → (conditional_edges) → tool_router → executor → response_generator → memory_updater
纯闲聊走 direct 短路径，任务型走完整工具链。
"""
import logging

from langgraph.graph import END, StateGraph

from app.agent.state import AgentState
from app.agent.nodes import (
    executor_node,
    memory_updater_node,
    planner_node,
    response_generator_node,
    route_after_planner,
    tool_router_node,
)

logger = logging.getLogger(__name__)

# checkpointer：SqliteSaver 持久化，同 thread_id 可断点续跑
try:
    from langgraph.checkpoint.sqlite import SqliteSaver

    _checkpointer = SqliteSaver.from_conn_string("agent_checkpoints.sqlite")
    logger.info("Agent checkpointer: SqliteSaver 已启用 (agent_checkpoints.sqlite)")
except Exception as e:  # pragma: no cover - 依赖缺失时降级
    logger.warning("SqliteSaver 初始化失败，Agent 无持久化 checkpointer: %s", e)
    _checkpointer = None

def build_agent_workflow() -> StateGraph:
    """构建 Agent 编排 workflow"""
    workflow = StateGraph(AgentState)

    # 节点
    workflow.add_node("planner", planner_node)
    workflow.add_node("tool_router", tool_router_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("response_generator", response_generator_node)
    workflow.add_node("memory_updater", memory_updater_node)

    # 入口
    workflow.set_entry_point("planner")

    # planner 后条件路由：needs_tools → 工具链；纯闲聊 → 直接生成
    workflow.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "tools": "tool_router",
            "direct": "response_generator",
        },
    )

    # 工具链
    workflow.add_edge("tool_router", "executor")
    workflow.add_edge("executor", "response_generator")

    # 收尾
    workflow.add_edge("response_generator", "memory_updater")
    workflow.add_edge("memory_updater", END)

    return workflow


# 编译 workflow（Agent 与 RAG 并存，互不影响）
agent_workflow = build_agent_workflow().compile(checkpointer=_checkpointer)
