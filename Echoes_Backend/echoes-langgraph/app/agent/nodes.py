"""
Agent 编排节点（Stage 1: 真 ReAct 循环）

Thought(planner) → Action(executor) → Observation → should_continue → 循环/结束
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

PLANNER_PROMPT = """你是「一闻如故」语音陪伴 Agent 的规划器（ReAct Thought 阶段）。

**当前状态**：
- 用户输入：{query}
- 已迭代：{iteration}/{max_iterations} 轮
- 已调用的工具：{called_tools}
- 已有的工具结果：{tool_results_summary}

**你的任务**：决定下一步做什么（单步决策，不是列全部计划）

**意图类别**：
- chat: 闲聊/问候/日常分享，信息已足够，无需工具
- emotional_support: 情绪支持（难过/焦虑/压力大/失落）
- memory_recall: 回忆过去对话（"你还记得吗"）
- profile_query: 关于用户自身的问题（"我是什么样的人"）
- task: 需要执行具体操作（记录偏好、设置提醒）

**可用工具**：
- analyze_emotion: 情绪分析（用户情绪不明确时）
- search_memory: 检索历史对话记忆（需要回忆时）
- get_user_profile: 获取用户长期画像（问及用户自身时）
- update_user_state: 更新用户画像/情绪标签
- generate_comfort_response: 生成情感安慰回复

**判断规则**：
1. 如果信息已足够回答（闲聊 / 已检索到记忆 / 已分析完情绪）→ 设 is_sufficient=true，无需再调工具
2. 如果还需要更多信息 → 选一个最需要的工具，设 is_sufficient=false
3. 避免重复调用相同工具（检查 called_tools）
4. 达到 max_iterations → 强制 is_sufficient=true

**输出 JSON**（不要包裹在 markdown 代码块里）：
{{
  "intent": "chat|emotional_support|memory_recall|profile_query|task",
  "is_sufficient": true/false,
  "next_tool": "工具名 或 null（信息足够时）",
  "tool_args": {{"arg1": "value1"}},
  "reasoning": "单步决策理由（Thought）"
}}
"""

RESPONSE_PROMPT = """你是「一闻如故」语音陪伴助手。人格模式：{personality_mode}。

用户：{query}
意图：{intent}
情绪分析：{emotion}
记忆命中：{memory_hits}
用户画像：{profile}
工具结果：{tool_results}

请用自然温暖、贴合人格模式（温柔/理性/活泼）的语气回复，150 字以内。"""


def _build_persona_anchor(personality: str) -> str:
    """构建 System Prompt 人设锚点（永不参与滑动窗口淘汰，稳定人格）"""
    personas = {
        "温柔": "你是一个温柔体贴的陪伴者，善于倾听和理解，说话轻声细语、温暖包容，像一位关心朋友的姐姐/哥哥。",
        "理性": "你是一个理性冷静的陪伴者，逻辑清晰、客观务实，擅长分析问题并给出建设性建议，但不失关怀。",
        "活泼": "你是一个活泼开朗的陪伴者，热情阳光、幽默风趣，用轻松愉快的方式陪伴用户，像一位贴心的闺蜜/兄弟。",
    }
    base = personas.get(personality, personas["温柔"])
    return f"{base}\n\n核心原则：以用户为中心，尊重其情绪和意愿，提供真诚、温暖、有价值的陪伴。这是你的永恒人格设定，不会因对话内容改变。"


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
    """ReAct Thought 节点：单步决策下一个工具，或判断信息已足够"""
    query = state.get("query", "")
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)
    all_results = state.get("all_tool_results", [])

    # 已调用工具摘要（供 planner 避免重复调用）
    called_tools = [r.get("tool_name") for r in all_results]
    tool_results_summary = "; ".join([
        f"{r.get('tool_name')}: {str(r.get('result'))[:50]}"
        for r in all_results[-3:]
    ]) if all_results else "无"

    prompt = PLANNER_PROMPT.format(
        query=query,
        iteration=iteration,
        max_iterations=max_iterations,
        called_tools=called_tools or "无",
        tool_results_summary=tool_results_summary,
    )

    try:
        raw = await chat_completion(
            [{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.3,
        )
        plan = _parse_planner_json(raw)

        intent = plan.get("intent") or "chat"
        if intent not in ("chat", "emotional_support", "memory_recall", "profile_query", "task"):
            intent = "chat"

        is_sufficient = bool(plan.get("is_sufficient", False))
        next_tool = plan.get("next_tool")
        tool_args = plan.get("tool_args") or {}
        reasoning = str(plan.get("reasoning", ""))

        # 强制：达到 max_iterations → 结束循环
        if iteration >= max_iterations:
            is_sufficient = True
            next_tool = None
            reasoning += f" [达到最大迭代 {max_iterations}，强制结束]"

        # 工具合法性校验
        if next_tool and next_tool not in TOOL_REGISTRY:
            logger.warning("planner 输出非法工具 %s，忽略", next_tool)
            next_tool = None
            is_sufficient = True

        return {
            "intent": intent,
            "is_sufficient": is_sufficient,
            "next_tool": next_tool,
            "tool_args": tool_args,
            "plan_reasoning": reasoning,
            "needs_tools": bool(next_tool and not is_sufficient),
            "iteration": iteration + 1,
        }
    except Exception as e:
        logger.warning("planner LLM 调用失败，标记充足直接生成: %s", e)
        return {
            "intent": "chat",
            "is_sufficient": True,
            "next_tool": None,
            "tool_args": {},
            "plan_reasoning": "planner failed",
            "needs_tools": False,
            "iteration": iteration + 1,
        }


def should_continue(state: AgentState) -> Literal["continue", "generate"]:
    """ReAct 条件边：信息充足 → 生成；否则 → 继续循环调工具"""
    if state.get("is_sufficient", False):
        return "generate"
    if not state.get("next_tool"):
        return "generate"
    # 安全阀：迭代超限强制生成
    if state.get("iteration", 0) > state.get("max_iterations", 3):
        return "generate"
    return "continue"


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
    # generate_comfort_response 不在此组参：它依赖 analyze_emotion 的输出，
    # 必须在 executor 执行时用实时 emotion（tool_router 阶段情绪还没分析）
    return {}


# ============== executor（ReAct Action + Observation）==============

async def executor_node(state: AgentState) -> AgentState:
    """ReAct Action 节点：执行 planner 选定的单个工具，写入 observation

    单步执行（非批量），结果累积到 all_tool_results 供下一轮 planner 参考。
    """
    name = state.get("next_tool")
    query = state.get("query", "")
    user_id = state.get("user_id", "")
    # planner 给的 args 优先，缺失则按工具签名补全
    args = state.get("tool_args") or {}
    if not args:
        args = _build_args(name, query, user_id, state)

    emotion = state.get("emotion")
    memory_hits = state.get("memory_hits", [])
    profile = state.get("profile")
    all_results = list(state.get("all_tool_results", []))

    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        logger.warning("executor 收到未知工具: %s", name)
        observation = f"工具 {name} 不存在，跳过"
        all_results.append({"tool_name": name, "result": {"error": "unknown tool"}})
        return {"observation": observation, "all_tool_results": all_results}

    result: Any = None
    try:
        if name == "analyze_emotion":
            emotion = await fn(text=args.get("text", query))
            result = emotion
            observation = f"情绪分析：{emotion.get('emotion')}（强度 {emotion.get('intensity')}）"
        elif name == "search_memory":
            memory_hits = await fn(query=args.get("query", query), user_id=user_id)
            result = memory_hits
            observation = f"检索到 {len(memory_hits)} 条相关记忆" if memory_hits else "未检索到达阈值的记忆"
        elif name == "get_user_profile":
            profile = await fn(user_id=user_id)
            result = profile
            observation = f"获取到用户画像：{list(profile.keys()) if profile else '空'}"
        elif name == "generate_comfort_response":
            emo = emotion or {}
            comfort = await fn(
                emotion=emo.get("emotion", "neutral"),
                intensity=emo.get("intensity", 0.5),
            )
            result = {"comfort_response": comfort}
            observation = "已生成安慰话术"
        else:
            result = await fn(**args)
            observation = f"工具 {name} 执行完成"
    except Exception as e:
        logger.error("工具执行失败 %s: %s", name, e)
        result = {"error": str(e)}
        observation = f"工具 {name} 执行失败：{e}"

    all_results.append({"tool_name": name, "result": result})
    logger.info("ReAct Action: tool=%s | Observation: %s", name, observation)

    return {
        "observation": observation,
        "all_tool_results": all_results,
        "emotion": emotion,
        "memory_hits": memory_hits,
        "profile": profile,
    }


# ============== response_generator ==============

def _extract_tool_results(all_results: list) -> Dict[str, Any]:
    """从累积的 all_tool_results 提取各工具最新结果，供生成节点使用"""
    flat: Dict[str, Any] = {}
    for item in all_results:
        name = item.get("tool_name")
        res = item.get("result")
        if name == "generate_comfort_response" and isinstance(res, dict):
            flat["comfort_response"] = res.get("comfort_response")
        else:
            flat[name] = res
    return flat


async def response_generator_node(state: AgentState) -> AgentState:
    """综合情绪/记忆/画像 + 人格模式生成回复（ReAct 循环结束后）"""
    query = state.get("query", "")
    intent = state.get("intent", "chat")
    personality = state.get("personality_mode", "温柔")
    emotion = state.get("emotion") or {}
    memory_hits = state.get("memory_hits", [])
    profile = state.get("profile") or {}
    tool_results = _extract_tool_results(state.get("all_tool_results", []))

    # 安慰分支：有安慰话术且无记忆命中 → 直接用模板话术（快且稳）
    comfort = tool_results.get("comfort_response")
    if comfort and intent == "emotional_support" and not memory_hits:
        return {"response": comfort}

    user_prompt = RESPONSE_PROMPT.format(
        personality_mode=personality,
        query=query,
        intent=intent,
        emotion=json.dumps(emotion, ensure_ascii=False),
        memory_hits=json.dumps(memory_hits[:3], ensure_ascii=False),
        profile=json.dumps(profile, ensure_ascii=False),
        tool_results=json.dumps(tool_results, ensure_ascii=False),
    )
    try:
        # System Prompt 人设锚点：置于最顶层，独立于用户消息，稳定人格
        response = await chat_completion(
            [
                {"role": "system", "content": _build_persona_anchor(personality)},
                {"role": "user", "content": user_prompt},
            ],
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

    # Grounding 校验：LLM 判断回复是否被记忆支撑（记录 faithfulness，不阻断写入）
    memory_hits = state.get("memory_hits", [])
    grounding = await memory.grounding_check_llm(response, memory_hits)
    logger.info(
        "Grounding: faithful=%s score=%.2f unsupported=%s",
        grounding.get("faithful"), grounding.get("score", 0), grounding.get("unsupported_claims", []),
    )

    text = f"用户说：{query}。助手回复：{response}。"
    entities = await memory.extract_entities(text)
    entry = {
        "summary": f"用户说：{query} | 助手回复：{response}",
        "entities": entities,
        "intent": state.get("intent", "chat"),
        "ts": datetime.now().isoformat(),
        "grounding_score": grounding.get("score", 1.0),
    }
    saved = await memory.save_memory_entry(user_id, entry)
    logger.info("memory 保存: saved=%s entities=%s", saved, entities)
    return {"memory_entry": entry, "grounding": grounding}
