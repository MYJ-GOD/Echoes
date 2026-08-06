"""
Agent 编排节点（Week1 骨架）

planner → (conditional_edges) → tool_router → executor → response_generator → memory_updater
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, Literal

from app.agent import memory
from app.agent.state import AgentState
from app.agent.tools import TOOL_REGISTRY
from app.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

PLANNER_PROMPT = """你是「一闻如故」语音陪伴 Agent 的规划器。根据用户输入判断意图，并决定需要调用哪些工具。

意图类别：
- chat: 闲聊/问候/日常分享，不需要工具
- emotional_support: 情绪支持（难过/焦虑/压力大/失落）
- memory_recall: 回忆过去对话（"你还记得吗"）
- profile_query: 关于用户自身的问题（"我是什么样的人"）
- task: 需要执行具体操作（记录偏好、设置提醒）

可用工具：
- analyze_emotion: 识别用户情绪
- search_memory: 检索历史对话记忆
- get_user_profile: 获取用户长期画像
- update_user_state: 更新用户状态
- generate_comfort_response: 生成安慰话术

只输出 JSON（不要其他内容）：
{"intent": "chat|emotional_support|memory_recall|profile_query|task", "tools": ["工具名"], "reasoning": "一句话理由"}

用户输入：{query}"""

RESPONSE_PROMPT = """你是「一闻如故」语音陪伴助手。人格模式：{personality_mode}。

用户：{query}
意图：{intent}
情绪分析：{emotion}
记忆命中：{memory_hits}
用户画像：{profile}
工具结果：{tool_results}

请用自然温暖、贴合人格模式（温柔/理性/活泼）的语气回复，150 字以内。"""


# ============== planner ==============

def _parse_planner_json(raw: str) -> Dict[str, Any]:
    """解析 planner 的 JSON 输出（容忍 markdown 代码块包裹）"""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取第一个 { ... }
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start:end + 1])
        else:
            raise
    if not isinstance(data, dict):
        raise ValueError("planner 输出不是 JSON 对象")
    return data


async def planner_node(state: AgentState) -> AgentState:
    """LLM 决策节点：输出 {intent, tools, reasoning}，决定流程走向"""
    query = state.get("query", "")
    prompt = PLANNER_PROMPT.format(query=query)
    try:
        raw = await chat_completion(
            [{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        plan = _parse_planner_json(raw)
        tools = plan.get("tools") or []
        if not isinstance(tools, list):
            tools = []
        intent = plan.get("intent") or "chat"
        if intent not in ("chat", "emotional_support", "memory_recall", "profile_query", "task"):
            intent = "chat"
        return {
            "intent": intent,
            "plan": [t for t in tools if t in TOOL_REGISTRY],
            "plan_reasoning": str(plan.get("reasoning", "")),
            "needs_tools": bool(tools),
        }
    except Exception as e:
        logger.warning("planner LLM 调用失败，回退 chat 路径: %s", e)
        return {"intent": "chat", "plan": [], "plan_reasoning": "planner failed", "needs_tools": False}


def route_after_planner(state: AgentState) -> Literal["tools", "direct"]:
    """planner 后条件路由：needs_tools → 工具链；纯闲聊 → 直接生成"""
    return "tools" if state.get("needs_tools") else "direct"


# ============== tool_router ==============

def _build_args(name: str, query: str, user_id: str, state: AgentState) -> Dict[str, Any]:
    """按工具签名构造参数"""
    if name == "analyze_emotion":
        return {"text": query}
    if name == "search_memory":
        return {"query": query, "user_id": user_id}
    if name == "get_user_profile":
        return {"user_id": user_id}
    if name == "update_user_state":
        emotion = state.get("emotion") or {}
        return {"user_id": user_id, "emotion": emotion.get("emotion"), "intensity": emotion.get("intensity")}
    if name == "generate_comfort_response":
        emotion = state.get("emotion") or {}
        return {"emotion": emotion.get("emotion", "neutral"), "intensity": emotion.get("intensity", 0.5)}
    return {}


async def tool_router_node(state: AgentState) -> AgentState:
    """选择工具：把 plan 解析为可执行清单（体现「工具选择」能力）"""
    plan = state.get("plan", [])
    query = state.get("query", "")
    user_id = state.get("user_id", "")
    execution = []
    for name in plan:
        fn = TOOL_REGISTRY.get(name)
        if fn is None:
            logger.warning("未知工具被忽略: %s", name)
            continue
        execution.append({"name": name, "fn": fn, "args": _build_args(name, query, user_id, state)})
    return {"execution_plan": execution}


# ============== executor ==============

async def executor_node(state: AgentState) -> AgentState:
    """执行工具（可多个，按 plan 顺序），结果写入 state"""
    execution = state.get("execution_plan", [])
    results: Dict[str, Any] = {}
    emotion = state.get("emotion")
    memory_hits = state.get("memory_hits", [])
    profile = state.get("profile")

    for item in execution:
        name, fn, args = item["name"], item["fn"], item["args"]
        try:
            if name == "analyze_emotion":
                emotion = await fn(**args)
            elif name == "search_memory":
                memory_hits = await fn(**args)
            elif name == "get_user_profile":
                profile = await fn(**args)
            elif name == "generate_comfort_response":
                results["comfort_response"] = await fn(**args)
            else:
                results[name] = await fn(**args)
        except Exception as e:
            logger.error("工具执行失败 %s: %s", name, e)
            results[name] = {"error": str(e)}

    return {
        "tool_results": results,
        "emotion": emotion,
        "memory_hits": memory_hits,
        "profile": profile,
    }


# ============== response_generator ==============

async def response_generator_node(state: AgentState) -> AgentState:
    """综合情绪/记忆/画像 + 人格模式生成回复"""
    query = state.get("query", "")
    intent = state.get("intent", "chat")
    personality = state.get("personality_mode", "温柔")
    emotion = state.get("emotion") or {}
    memory_hits = state.get("memory_hits", [])
    profile = state.get("profile") or {}
    tool_results = state.get("tool_results", {})

    # 安慰分支：计划了安慰话术且无记忆命中 → 直接用模板话术（不调 LLM，快且稳）
    comfort = tool_results.get("comfort_response")
    if comfort and intent == "emotional_support" and not memory_hits:
        return {"response": comfort}

    prompt = RESPONSE_PROMPT.format(
        personality_mode=personality,
        query=query,
        intent=intent,
        emotion=json.dumps(emotion, ensure_ascii=False),
        memory_hits=json.dumps(memory_hits[:3], ensure_ascii=False),
        profile=json.dumps(profile, ensure_ascii=False),
        tool_results=json.dumps(tool_results, ensure_ascii=False),
    )
    try:
        response = await chat_completion(
            [{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7,
        )
    except Exception as e:
        logger.error("response_generator LLM 调用失败: %s", e)
        response = "嗯，我在听，你慢慢说。"
    return {"response": response}


# ============== memory_updater ==============

async def memory_updater_node(state: AgentState) -> AgentState:
    """生成记忆条目（摘要 + LLM 实体抽取）并写入 Qdrant（长期记忆闭环）"""
    query = state.get("query", "")
    response = state.get("response", "")
    user_id = state.get("user_id", "")
    if not query or not response:
        return {"memory_entry": None}

    text = f"用户说：{query}。助手回复：{response}。"
    entities = await memory.extract_entities(text)
    entry = {
        "summary": f"用户说：{query} | 助手回复：{response}",
        "entities": entities,
        "intent": state.get("intent", "chat"),
        "ts": datetime.now().isoformat(),
    }
    saved = await memory.save_memory_entry(user_id, entry)
    logger.info("memory 保存: saved=%s entities=%s", saved, entities)
    return {"memory_entry": entry}
