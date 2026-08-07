"""
陪伴工具集（Week2：真实现）

- analyze_emotion        LLM structured output（失败降级规则版）
- search_memory          Qdrant conversation_history：向量 + 实体链接双信号
- get_user_profile       Qdrant user_profile
- update_user_state      写 Qdrant user_profile
- generate_comfort_response  规则模板话术

工具全部 async（executor 统一 await）。
"""
import json
import logging
from typing import Any, Dict, List

from app.agent import memory
from app.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

# 情绪关键词（LLM 失败时的规则降级）
_SAD_WORDS = ["难过", "伤心", "哭", "失落", "沮丧", "委屈"]
_ANXIOUS_WORDS = ["焦虑", "压力", "紧张", "担心", "烦", "睡不着"]
_HAPPY_WORDS = ["开心", "高兴", "太好了", "哈哈", "喜欢", "棒"]

_VALID_EMOTIONS = {"sad", "anxious", "happy", "angry", "neutral"}

EMOTION_PROMPT = """你是情绪分析器。从用户文本判断主要情绪，只输出 JSON：
{{"emotion": "sad|anxious|happy|angry|neutral", "intensity": 0.0到1.0, "confidence": 0.0到1.0}}

用户文本：{text}"""


def _rule_based_emotion(text: str) -> Dict[str, Any]:
    """规则降级版情绪分析"""
    if any(w in text for w in _SAD_WORDS):
        return {"emotion": "sad", "intensity": 0.8, "confidence": 0.7}
    if any(w in text for w in _ANXIOUS_WORDS):
        return {"emotion": "anxious", "intensity": 0.7, "confidence": 0.7}
    if any(w in text for w in _HAPPY_WORDS):
        return {"emotion": "happy", "intensity": 0.6, "confidence": 0.7}
    return {"emotion": "neutral", "intensity": 0.2, "confidence": 0.5}


async def analyze_emotion(text: str) -> Dict[str, Any]:
    """识别用户情绪（LLM structured output，失败降级规则版）"""
    try:
        raw = await chat_completion(
            [{"role": "user", "content": EMOTION_PROMPT.format(text=text[:300])}],
            max_tokens=60,
            temperature=0.0,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        emotion = data.get("emotion", "neutral")
        if emotion not in _VALID_EMOTIONS:
            emotion = "neutral"
        return {
            "emotion": emotion,
            "intensity": float(data.get("intensity", 0.5)),
            "confidence": float(data.get("confidence", 0.6)),
        }
    except Exception as e:
        logger.warning("LLM 情绪分析失败，降级规则版: %s", e)
        return _rule_based_emotion(text)


async def search_memory(query: str, user_id: str = "") -> List[Dict[str, Any]]:
    """检索历史对话（向量 + 实体链接双信号，记忆图谱）"""
    return await memory.search_memory(query, user_id=user_id)


async def get_user_profile(user_id: str = "") -> Dict[str, Any]:
    """聚合用户长期画像（Qdrant user_profile）"""
    return await memory.get_user_profile(user_id)


async def update_user_state(user_id: str = "", **updates: Any) -> Dict[str, Any]:
    """更新情绪标签/画像（写 Qdrant user_profile）"""
    return await memory.update_user_profile(user_id, **updates)


async def generate_comfort_response(emotion: str = "neutral", intensity: float = 0.5) -> str:
    """安慰场景专用话术（规则模板；可后续换 LLM 专用 prompt）"""
    templates = {
        "sad": "我在呢。慢慢说，我陪你一起想办法，你不是一个人。",
        "anxious": "先深呼吸一下。事情一件一件来，你已经做得很好了。",
        "happy": "真为你开心！多和我分享一些，我想听。",
        "angry": "听起来确实让人生气。我站在你这边，先消消气，慢慢说。",
        "neutral": "嗯，我在听，你继续说。",
    }
    return templates.get(emotion, templates["neutral"])


TOOL_REGISTRY: Dict[str, Any] = {
    "analyze_emotion": analyze_emotion,
    "search_memory": search_memory,
    "get_user_profile": get_user_profile,
    "update_user_state": update_user_state,
    "generate_comfort_response": generate_comfort_response,
}
