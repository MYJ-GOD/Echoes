"""
Agent 编排 workflow（Week1-2）

planner → (conditional_edges) → tool_router → executor → response_generator → memory_updater
纯闲聊走 direct 短路径，任务型走完整工具链。

checkpointer：AsyncSqliteSaver（async 图必须用异步实现），惰性初始化——
首次调用 get_agent_workflow() 时在事件循环内创建连接并编译。
"""
import logging

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
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

_workflow = None
_checkpointer = None
_checkpointer_conn = None


async def _make_checkpointer() -> AsyncSqliteSaver:
    """创建 AsyncSqliteSaver（持久化到 agent_checkpoints.sqlite，同 thread_id 断点续跑）"""
    global _checkpointer, _checkpointer_conn
    if _checkpointer is None:
        conn = await aiosqlite.connect("agent_checkpoints.sqlite")
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
        _checkpointer = saver
        _checkpointer_conn = conn
        logger.info("Agent checkpointer: AsyncSqliteSaver 已启用 (agent_checkpoints.sqlite)")
    return _checkpointer


async def close_agent_checkpointer() -> None:
    """关闭 checkpointer 的 sqlite 连接（进程退出/测试收尾时调用）。

    不 close 会让 aiosqlite 后台线程阻塞解释器退出（pytest 进程挂住）。
    """
    global _workflow, _checkpointer, _checkpointer_conn
    conn = _checkpointer_conn
    _workflow = None
    _checkpointer = None
    _checkpointer_conn = None
    if conn is not None:
        try:
            await conn.close()
            logger.info("Agent checkpointer 连接已关闭")
        except Exception as e:
            logger.warning("关闭 checkpointer 连接失败: %s", e)


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


async def get_agent_workflow():
    """惰性编译 Agent workflow（首次调用时初始化 AsyncSqliteSaver）"""
    global _workflow
    if _workflow is None:
        saver = await _make_checkpointer()
        _workflow = build_agent_workflow().compile(checkpointer=saver)
        logger.info("Agent workflow 编译完成（含 AsyncSqliteSaver checkpointer）")
    return _workflow
