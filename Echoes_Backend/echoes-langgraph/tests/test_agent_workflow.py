"""
Agent Workflow 单元测试

测试核心节点的输入输出逻辑（不依赖真实 LLM 和 checkpointer）
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agent.state import AgentState
from app.agent.nodes import (
    planner_node,
    executor_node,
    response_generator_node,
    should_continue,
)


@pytest.mark.asyncio
async def test_planner_node_sufficient():
    """planner 返回 is_sufficient=true 应设置状态"""
    mock_response = """
{
  "thought": "用户问候，无需工具",
  "next_tool": null,
  "is_sufficient": true
}
"""
    with patch("app.agent.nodes.ChatOpenAI") as MockLLM:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=mock_response))
        MockLLM.return_value = mock_llm

        state = AgentState(
            query="你好",
            user_id="test",
            session_id="s1",
            turn_id="t1",
            personality_mode="温柔",
            conversation_history=[],
            max_iterations=3,
        )

        result = await planner_node(state)

        assert result["is_sufficient"] is True
        assert result["next_tool"] is None


@pytest.mark.asyncio
async def test_planner_node_tool_call():
    """planner 返回 next_tool 应设置工具信息"""
    mock_response = """
{
  "thought": "需要检索记忆",
  "next_tool": "search_memory",
  "tool_input": {"query": "用户偏好"},
  "is_sufficient": false
}
"""
    with patch("app.agent.nodes.ChatOpenAI") as MockLLM:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=mock_response))
        MockLLM.return_value = mock_llm

        state = AgentState(
            query="我喜欢什么",
            user_id="test",
            session_id="s1",
            turn_id="t1",
            personality_mode="温柔",
            conversation_history=[],
            max_iterations=3,
        )

        result = await planner_node(state)

        assert result["next_tool"] == "search_memory"
        assert result["is_sufficient"] is False
        assert "tool_input" in result


@pytest.mark.asyncio
async def test_executor_node_calls_tool():
    """executor 应调用工具并记录 observation"""
    with patch("app.agent.tools.search_memory") as mock_tool:
        mock_tool.return_value = [
            {"summary": "用户喜欢美式咖啡", "score": 0.8}
        ]

        state = AgentState(
            query="我喜欢什么",
            user_id="test",
            session_id="s1",
            turn_id="t1",
            next_tool="search_memory",
            tool_input={"query": "偏好"},
            conversation_history=[],
            iterations=0,
            max_iterations=3,
        )

        result = await executor_node(state)

        assert result["iterations"] == 1
        # observation 应包含工具返回结果
        assert "observation" in result or len(result.get("memory_hits", [])) > 0


def test_should_continue_sufficient():
    """is_sufficient=true 应路由到 generate"""
    state = AgentState(
        query="你好",
        user_id="test",
        session_id="s1",
        turn_id="t1",
        is_sufficient=True,
        iterations=1,
        max_iterations=3,
        conversation_history=[],
    )

    result = should_continue(state)
    assert result == "generate"


def test_should_continue_max_iterations():
    """达到 max_iterations 应强制 generate"""
    state = AgentState(
        query="测试",
        user_id="test",
        session_id="s1",
        turn_id="t1",
        is_sufficient=False,
        iterations=3,
        max_iterations=3,
        conversation_history=[],
    )

    result = should_continue(state)
    assert result == "generate"


def test_should_continue_loop():
    """is_sufficient=false 且未超限应 continue"""
    state = AgentState(
        query="测试",
        user_id="test",
        session_id="s1",
        turn_id="t1",
        is_sufficient=False,
        iterations=1,
        max_iterations=3,
        conversation_history=[],
    )

    result = should_continue(state)
    assert result == "continue"


@pytest.mark.asyncio
async def test_response_generator_with_memory():
    """response_generator 应生成回复"""
    mock_response = "你喜欢美式咖啡"

    with patch("app.agent.nodes.ChatOpenAI") as MockLLM:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=mock_response))
        MockLLM.return_value = mock_llm

        state = AgentState(
            query="我喜欢什么",
            user_id="test",
            session_id="s1",
            turn_id="t1",
            memory_hits=[{"summary": "用户喜欢美式咖啡", "score": 0.8}],
            conversation_history=[],
            iterations=1,
            max_iterations=3,
        )

        result = await response_generator_node(state)

        assert "response" in result
        assert result["response"] == mock_response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
