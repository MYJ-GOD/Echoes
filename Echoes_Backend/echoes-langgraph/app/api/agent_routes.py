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

from app.agent.workflow import agent_workflow
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
    }


def _thread_config(request: AgentRequest) -> Dict[str, Any]:
    return {"configurable": {"thread_id": request.session_id or request.turn_id or "default"}}


@router.post("/chat", response_model=AgentResponse)
async def agent_chat(request: AgentRequest) -> AgentResponse:
    """Agent 对话（非流式）：planner → 工具链 → 人格化生成 → 记忆入库"""
    start = time.time()
    try:
        result = await agent_workflow.ainvoke(
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
    """Agent 对话（流式 NDJSON）；Java 端负责 NDJSON → SSE"""
    seq = 0

    async def generate() -> AsyncGenerator[str, None]:
        nonlocal seq
        # state 在 values 模式下累积，同一字段会在后续事件重复出现，按节点去重
        yielded = {"intent": False, "emotion": False, "memory": False, "response": False}
        try:
            async for event in agent_workflow.astream(
                _build_inputs(request),
                config=_thread_config(request),
                stream_mode="values",
            ):
                if event.get("intent") and not yielded["intent"]:
                    yielded["intent"] = True
                    yield json.dumps({
                        "type": "intent",
                        "intent": event["intent"],
                        "tools": event.get("plan", []),
                        "seq": seq,
                    }, ensure_ascii=False) + "\n"
                    seq += 1

                if event.get("emotion") and not yielded["emotion"]:
                    yielded["emotion"] = True
                    yield json.dumps({
                        "type": "emotion",
                        "emotion": event["emotion"],
                        "seq": seq,
                    }, ensure_ascii=False) + "\n"
                    seq += 1

                if event.get("memory_hits") and not yielded["memory"]:
                    yielded["memory"] = True
                    yield json.dumps({
                        "type": "memory",
                        "hits": event["memory_hits"][:3],
                        "seq": seq,
                    }, ensure_ascii=False) + "\n"
                    seq += 1

                if event.get("response") and not yielded["response"]:
                    yielded["response"] = True
                    yield json.dumps({
                        "type": "message.delta",
                        "content": event["response"],
                        "seq": seq,
                    }, ensure_ascii=False) + "\n"
                    seq += 1

            yield json.dumps({
                "type": "end",
                "status": "SUCCESS",
                "seq": seq,
            }, ensure_ascii=False) + "\n"
        except Exception as e:
            logger.error("agent/chat/stream 失败: %s", e)
            yield json.dumps({
                "type": "error",
                "message": str(e),
                "seq": seq,
            }, ensure_ascii=False) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
