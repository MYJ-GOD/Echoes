"""
Agent 状态定义（Stage 1: 真 ReAct 循环）

独立于 RAG 的 State，支持 Thought→Action→Observation 迭代循环。
"""
from typing import Any, Dict, List, Literal, Optional, TypedDict


class AgentState(TypedDict, total=False):
    """Agent 编排状态（ReAct 循环版）"""

    # ============== 输入 ==============
    query: str
    user_id: str
    session_id: str
    turn_id: str
    conversation_history: List[Dict[str, str]]  # [{role, content}]
    personality_mode: str                        # 温柔/理性/活泼

    # ============== ReAct 循环控制 ==============
    iteration: int                               # 当前迭代轮数（从 0 开始）
    max_iterations: int                          # 最大迭代次数（防止无限循环）
    is_sufficient: bool                          # 信息是否充足（True → 结束循环进入生成）
    loop_history: List[str]                      # 循环日志（调试用）

    # ============== planner 输出（Thought）==============
    intent: Literal["chat", "emotional_support", "memory_recall", "profile_query", "task", "other"]
    next_tool: Optional[str]                     # 下一步要调用的工具名（单步决策，非列表）
    tool_args: Optional[Dict[str, Any]]          # 工具参数
    plan_reasoning: str                          # 决策理由（Thought）
    needs_tools: bool

    # ============== 工具执行（Action）==============
    tool_results: Dict[str, Any]                 # 本轮工具执行结果
    all_tool_results: List[Dict[str, Any]]       # 累积所有工具结果（跨迭代）
    observation: str                             # 对本轮工具结果的观察总结（Observation）
    emotion: Optional[Dict[str, Any]]            # {emotion, intensity, confidence}
    memory_hits: List[Dict[str, Any]]
    profile: Optional[Dict[str, Any]]

    # ============== 生成 ==============
    response: str

    # ============== 记忆更新 + Grounding ==============
    memory_entry: Optional[Dict[str, Any]]       # {summary, entities, intent, grounding_score}
    grounding: Optional[Dict[str, Any]]          # {faithful, score, unsupported_claims}
