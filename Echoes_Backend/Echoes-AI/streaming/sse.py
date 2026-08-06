"""
SSE (Server-Sent Events) streaming utilities for Echoes-AI
"""

import json
from typing import Any, Dict
from fastapi.responses import StreamingResponse
import asyncio


def format_sse_event(event_type: str, data: Any = None) -> str:
    """
    Format data as SSE event

    Args:
        event_type: Type of event (text, audio_chunk, error, end)
        data: Event data

    Returns:
        Formatted SSE string
    """
    event = {"type": event_type}
    if data is not None:
        event["data"] = data

    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def create_sse_stream(generator):
    """
    Create SSE streaming response from async generator

    Args:
        generator: Async generator yielding event data

    Returns:
        StreamingResponse with SSE content
    """
    async def event_generator():
        try:
            async for event_data in generator:
                if isinstance(event_data, dict):
                    event_type = event_data.get("type", "data")
                    data = event_data.get("data")
                    yield format_sse_event(event_type, data)
                else:
                    # Default to text event
                    yield format_sse_event("text", event_data)
        except Exception as e:
            yield format_sse_event("error", str(e))
        finally:
            yield format_sse_event("end")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        }
    )
