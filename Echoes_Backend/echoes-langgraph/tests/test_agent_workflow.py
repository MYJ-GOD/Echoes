"""
Agent workflow 集成测试（Week4）

mock LLM 与 Qdrant 层，可离线运行：
    cd echoes-langgraph && python -m pytest tests/test_agent_workflow.py -v

覆盖：单轮工具链、闲聊短路径、安慰话术短路、记忆检索命中、
planner/生成失败兜底、未知工具忽略、工具错误隔离、记忆实体写入。
"""
import pytest
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from app.agent.workflow import get_agent_workflow

TEST_CONFIG = {"configurable": {"thread_id": "test-session-1"}}


def _base_patches():
    """默认 mock：LLM 两层 + 记忆层（Qdrant/实体/保存）"""
    return [
        patch("app.agent.nodes.chat_completion",
              AsyncMock(side_effect=[
                  '{"intent": "chat", "tools": [], "reasoning": "test"}',  # planner
                  "测试回复",                                                # response_generator
              ])),
        patch("app.agent.tools.chat_completion",
              AsyncMock(return_value='{"emotion": "sad", "intensity": 0.8, "confidence": 0.7}')),
        patch("app.agent.memory.search_memory", AsyncMock(return_value=[])),
        patch("app.agent.memory.extract_entities", AsyncMock(return_value=["美式咖啡"])),
        patch("app.agent.memory.save_memory_entry", AsyncMock(return_value=True)),
    ]


# ============== 路由单元测试 ==============

def test_route_after_planner_direct():
    from app.agent.nodes import route_after_planner
    assert route_after_planner({"needs_tools": False}) == "direct"


def test_route_after_planner_tools():
    from app.agent.nodes import route_after_planner
    assert route_after_planner({"needs_tools": True}) == "tools"


def test_tool_router_ignores_unknown_tool():
    from app.agent.nodes import tool_router_node
    import asyncio
    result = asyncio.run(tool_router_node({"plan": ["not_a_tool", "analyze_emotion"], "query": "hi", "user_id": "u1"}))
    names = [item["name"] for item in result["execution_plan"]]
    assert names == ["analyze_emotion"]


# ============== 端到端（mock LLM + 记忆） ==============

@pytest.mark.asyncio
async def test_chat_direct_path_e2e():
    """闲聊：planner 无工具 → 短路径 → 生成 → 记忆写入"""
    with ExitStack() as stack:
        for p in _base_patches():
            stack.enter_context(p)
        workflow = await get_agent_workflow()
        result = await workflow.ainvoke(
            {"query": "你好呀", "user_id": "u1"}, config=TEST_CONFIG)
        assert result["intent"] == "chat"
        assert result["needs_tools"] is False
        assert result["response"] == "测试回复"
        assert result["memory_entry"] is not None


@pytest.mark.asyncio
async def test_emotional_support_comfort_shortcut():
    """情绪支持：plan 含 analyze_emotion + generate_comfort_response → 模板话术短路（不调生成 LLM）"""
    planner = AsyncMock(return_value='{"intent": "emotional_support", "tools": ["analyze_emotion", "generate_comfort_response"], "reasoning": "sad"}')
    with patch("app.agent.nodes.chat_completion", planner), \
         patch("app.agent.tools.chat_completion",
               AsyncMock(return_value='{"emotion": "sad", "intensity": 0.8, "confidence": 0.7}')), \
         patch("app.agent.memory.extract_entities", AsyncMock(return_value=[])), \
         patch("app.agent.memory.save_memory_entry", AsyncMock(return_value=True)):
        workflow = await get_agent_workflow()
        result = await workflow.ainvoke(
            {"query": "我今天很难过", "user_id": "u1"}, config=TEST_CONFIG)
        assert result["intent"] == "emotional_support"
        assert "我在呢" in result["response"]          # 模板话术
        assert planner.await_count == 1                 # 仅 planner 一次 LLM，生成走模板


@pytest.mark.asyncio
async def test_memory_recall_with_hits():
    """记忆回忆：search_memory 命中 → response_generator 拿到记忆上下文"""
    hits = [{"summary": "用户说：我喜欢喝美式 | 助手回复：记住了", "entities": ["美式咖啡"], "score": 0.9}]
    planner = AsyncMock(return_value='{"intent": "memory_recall", "tools": ["search_memory"], "reasoning": "recall"}')
    with patch("app.agent.nodes.chat_completion", planner), \
         patch("app.agent.memory.search_memory", AsyncMock(return_value=hits)), \
         patch("app.agent.memory.extract_entities", AsyncMock(return_value=["美式咖啡"])), \
         patch("app.agent.memory.save_memory_entry", AsyncMock(return_value=True)):
        workflow = await get_agent_workflow()
        result = await workflow.ainvoke(
            {"query": "你还记得我喜欢喝什么吗", "user_id": "u1"}, config=TEST_CONFIG)
        assert result["intent"] == "memory_recall"
        assert result["memory_hits"] == hits
        assert result["response"]  # 生成 LLM 返回（planner mock 的返回值会被生成节点直接用，仅断言非空）


@pytest.mark.asyncio
async def test_planner_failure_fallback():
    """planner LLM 抛异常 → 回退 chat 短路径，不 crash"""
    with patch("app.agent.nodes.chat_completion", AsyncMock(side_effect=RuntimeError("llm down"))), \
         patch("app.agent.memory.extract_entities", AsyncMock(return_value=[])), \
         patch("app.agent.memory.save_memory_entry", AsyncMock(return_value=True)):
        workflow = await get_agent_workflow()
        result = await workflow.ainvoke(
            {"query": "hello", "user_id": "u1"}, config=TEST_CONFIG)
        assert result["intent"] == "chat"
        assert result["response"]  # 生成节点也会失败 → 兜底话术


@pytest.mark.asyncio
async def test_response_generator_failure_fallback():
    """response_generator LLM 失败 → 兜底回复文案"""
    planner = AsyncMock(return_value='{"intent": "chat", "tools": [], "reasoning": "x"}')
    with patch("app.agent.nodes.chat_completion",
               AsyncMock(side_effect=[
                   '{"intent": "chat", "tools": [], "reasoning": "x"}',  # planner OK
                   RuntimeError("gen down"),                                 # response_generator 抛异常
               ])), \
         patch("app.agent.memory.extract_entities", AsyncMock(return_value=[])), \
         patch("app.agent.memory.save_memory_entry", AsyncMock(return_value=True)):
        workflow = await get_agent_workflow()
        result = await workflow.ainvoke(
            {"query": "hi", "user_id": "u1"}, config=TEST_CONFIG)
        assert "我在听" in result["response"]  # 兜底文案


@pytest.mark.asyncio
async def test_executor_tool_error_isolation():
    """executor 中工具抛异常 → 记录 error 不 crash，后续工具继续"""
    planner = AsyncMock(return_value='{"intent": "profile_query", "tools": ["get_user_profile"], "reasoning": "x"}')
    async def boom(**kwargs):
        raise RuntimeError("profile db down")
    with patch("app.agent.nodes.chat_completion", planner), \
         patch("app.agent.tools.get_user_profile", boom), \
         patch("app.agent.memory.extract_entities", AsyncMock(return_value=[])), \
         patch("app.agent.memory.save_memory_entry", AsyncMock(return_value=True)):
        workflow = await get_agent_workflow()
        result = await workflow.ainvoke(
            {"query": "我是什么样的人", "user_id": "u1"}, config=TEST_CONFIG)
        # profile 工具失败 → 记录 error，流程继续（response 存在）
        assert result["response"]


@pytest.mark.asyncio
async def test_memory_save_with_entities():
    """memory_updater：实体抽取结果随 entry 保存（多轮修正/记忆图谱写入验证）"""
    captured = {}

    async def fake_save(user_id, entry):
        captured["entry"] = entry
        return True

    with patch("app.agent.nodes.chat_completion",
               AsyncMock(side_effect=[
                   '{"intent": "task", "tools": ["update_user_state"], "reasoning": "remember pref"}',
                   "记住了，你喜欢喝美式。",
               ])), \
         patch("app.agent.memory.extract_entities", AsyncMock(return_value=["美式咖啡"])), \
         patch("app.agent.memory.save_memory_entry", fake_save):
        workflow = await get_agent_workflow()
        result = await workflow.ainvoke(
            {"query": "我喜欢喝美式咖啡", "user_id": "u1"}, config=TEST_CONFIG)
        assert captured["entry"]["entities"] == ["美式咖啡"]
        assert captured["entry"]["intent"] == "task"
        assert result["memory_entry"] is not None
