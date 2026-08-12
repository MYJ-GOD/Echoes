"""
Agent 编排 API（Week3）

- POST /agent/chat:        非流式，返回最终结果
- POST /agent/chat/stream: NDJSON 流式（事件模式对齐 /rag/chat/stream，
                           文本事件 type=message.delta，Java 端直接转 SSE）

checkpointer：thread_id = session_id 或 turn_id，同会话可断点续跑。
"""
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.workflow import get_agent_workflow
from app.agent.guardrail import check_guardrail
from app.config import settings

router = APIRouter(prefix="/agent", tags=["Agent"])
logger = logging.getLogger(__name__)


class AgentRequest(BaseModel):
    query: str
    user_id: str = ""
    session_id: str = ""
    turn_id: str = ""
    conversation_history: List[Dict[str, str]] = []
    personality_mode: str = ""   # 空 → 用全局默认（AGENT_PERSONALITY_MODE）


class AgentResponse(BaseModel):
    intent: str = ""
    plan: List[str] = []
    response: str = ""
    emotion: Optional[Dict[str, Any]] = None
    memory_hits: List[Dict[str, Any]] = []
    memory_entry: Optional[Dict[str, Any]] = None


def _build_inputs(request: AgentRequest) -> Dict[str, Any]:
    return {
        "query": request.query,
        "user_id": request.user_id,
        "session_id": request.session_id,
        "turn_id": request.turn_id,
        "conversation_history": request.conversation_history or [],
        "personality_mode": request.personality_mode or settings.AGENT_PERSONALITY_MODE,
        # ReAct 循环控制
        "iteration": 0,
        "max_iterations": settings.AGENT_MAX_ITERATIONS,
        "all_tool_results": [],
    }


def _thread_config(request: AgentRequest) -> Dict[str, Any]:
    return {"configurable": {"thread_id": request.session_id or request.turn_id or "default"}}


@router.post("/chat", response_model=AgentResponse)
async def agent_chat(request: AgentRequest) -> AgentResponse:
    """Agent 对话（非流式）：Guardrail → ReAct 循环 → 人格化生成 → 记忆入库"""
    start = time.time()
    # Guardrail 入口安全门禁（第一关）
    blocked = check_guardrail(request.query)
    if blocked:
        return AgentResponse(intent="blocked", plan=[], response=blocked)
    try:
        workflow = await get_agent_workflow()
        result = await workflow.ainvoke(
            _build_inputs(request), config=_thread_config(request)
        )
        latency_ms = int((time.time() - start) * 1000)
        logger.info("agent/chat done: intent=%s latency=%dms", result.get("intent"), latency_ms)
        return AgentResponse(
            intent=result.get("intent", ""),
            plan=result.get("plan", []),
            response=result.get("response", ""),
            emotion=result.get("emotion"),
            memory_hits=result.get("memory_hits", []),
            memory_entry=result.get("memory_entry"),
        )
    except Exception as e:
        logger.error("agent/chat 失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def agent_chat_stream(request: AgentRequest):
    """Agent 对话（流式 NDJSON），封装四种事件类型：
    - message.delta: 文本回复（逐字/整段）
    - emotion: 情绪标签
    - citation: 引用来源（检索到的记忆）
    - audio: 语音（占位，实际 TTS 由 Java/CosyVoice 侧生成）
    末尾 end 事件。Java 端负责 NDJSON → SSE。
    """
    seq = 0

    def _event(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False) + "\n"

    async def generate() -> AsyncGenerator[str, None]:
        nonlocal seq

        # Guardrail 入口安全门禁：命中直接返回兜底文本 + end，不进入 workflow
        blocked = check_guardrail(request.query)
        if blocked:
            yield _event({"type": "message.delta", "content": blocked, "seq": seq})
            seq += 1
            yield _event({"type": "end", "status": "BLOCKED", "seq": seq})
            return

        # 四事件去重标记
        yielded = {"emotion": False, "citation": False, "response": False}
        try:
            workflow = await get_agent_workflow()
            async for event in workflow.astream(
                _build_inputs(request),
                config=_thread_config(request),
                stream_mode="values",
            ):
                # 事件2：情绪标签
                if event.get("emotion") and not yielded["emotion"]:
                    yielded["emotion"] = True
                    yield _event({"type": "emotion", "emotion": event["emotion"], "seq": seq})
                    seq += 1

                # 事件3：引用来源（检索到的记忆）
                if event.get("memory_hits") and not yielded["citation"]:
                    yielded["citation"] = True
                    citations = [
                        {"summary": h.get("summary", ""), "score": h.get("score"), "ts": h.get("ts")}
                        for h in event["memory_hits"][:3]
                    ]
                    yield _event({"type": "citation", "sources": citations, "seq": seq})
                    seq += 1

                # 事件1：文本回复
                if event.get("response") and not yielded["response"]:
                    yielded["response"] = True
                    yield _event({"type": "message.delta", "content": event["response"], "seq": seq})
                    seq += 1
                    # 事件4：语音占位（标记该文本可供 TTS 合成，实际音频由 Java 侧生成）
                    yield _event({"type": "audio", "text_ref": event["response"], "seq": seq})
                    seq += 1

            yield _event({"type": "end", "status": "SUCCESS", "seq": seq})
        except Exception as e:
            logger.error("agent/chat/stream 失败: %s", e)
            yield _event({"type": "error", "message": str(e), "seq": seq})

    return StreamingResponse(generate(), media_type="application/x-ndjson")
