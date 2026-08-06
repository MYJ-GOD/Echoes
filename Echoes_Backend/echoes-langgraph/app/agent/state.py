"""
Agent 状态定义（Week1）

独立于 RAG 的 State（app/graph/state.py），避免破坏现有 pipeline。
"""
from typing import Any, Dict, List, Literal, Optional, TypedDict


class AgentState(TypedDict, total=False):
    """Agent 编排状态"""

    # ============== 输入 ==============
    query: str
    user_id: str
    session_id: str
    turn_id: str
    conversation_history: List[Dict[str, str]]  # [{role, content}]
    personality_mode: str                        # 温柔/理性/活泼

    # ============== planner 输出 ==============
    intent: Literal["chat", "emotional_support", "memory_recall", "profile_query", "task", "other"]
    plan: List[str]                              # 工具名列表
    plan_reasoning: str
    needs_tools: bool

    # ============== 工具执行 ==============
    execution_plan: List[Dict[str, Any]]         # tool_router 产出 [{name, fn, args}]
    tool_results: Dict[str, Any]
    emotion: Optional[Dict[str, Any]]            # {emotion, intensity, confidence}
    memory_hits: List[Dict[str, Any]]
    profile: Optional[Dict[str, Any]]

    # ============== 生成 ==============
    response: str

    # ============== 记忆更新 ==============
    memory_entry: Optional[Dict[str, Any]]       # {summary, entities, intent}
