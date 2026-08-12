"""
Agent 编排 workflow（Stage 1: 真 ReAct 循环）

Thought(planner) → Action(executor) → Observation → should_continue:
  - 信息充足 → response_generator
  - 需更多信息 → 回 planner（形成循环）
  - 达到 max_iterations → 强制生成

checkpointer: AsyncSqliteSaver（async 图必须用异步实现）。
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
    should_continue,
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
    """构建 ReAct 循环 Agent workflow

    START → planner(Thought) → executor(Action) → should_continue:
      - continue → 回 planner（循环）
      - generate → response_generator → memory_updater → END
    """
    workflow = StateGraph(AgentState)

    # 节点
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("response_generator", response_generator_node)
    workflow.add_node("memory_updater", memory_updater_node)

    # 入口
    workflow.set_entry_point("planner")

    # planner(Thought) 后条件边：有工具要调 → executor；信息已足够 → 直接生成（跳过空 executor）
    workflow.add_conditional_edges(
        "planner",
        should_continue,
        {
            "continue": "executor",            # planner 决定了工具 → 执行
            "generate": "response_generator",  # 信息充足 → 直接生成
        },
    )

    # executor(Action) 后条件边（ReAct 循环核心）
    workflow.add_conditional_edges(
        "executor",
        should_continue,
        {
            "continue": "planner",             # 信息不足 → 回 planner，形成 Thought→Action 循环
            "generate": "response_generator",  # 信息充足 / 迭代超限 → 生成回复
        },
    )

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
