"""
陪伴工具集（Week1 mock 版）

工具 = 情感/记忆/人格管理的原子能力。Week1 返回 mock/规则数据保证 workflow 可跑；
Week2 逐个接真：
- analyze_emotion    → LLM structured output
- search_memory      → Qdrant conversation_history + 实体链接（记忆图谱）
- get_user_profile   → Qdrant user_profile
- update_user_state  → 写 Qdrant + 画像更新
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 情绪关键词（Week1 规则版；Week2 换 LLM）
_SAD_WORDS = ["难过", "伤心", "哭", "失落", "沮丧", "委屈"]
_ANXIOUS_WORDS = ["焦虑", "压力", "紧张", "担心", "烦", "睡不着"]
_HAPPY_WORDS = ["开心", "高兴", "太好了", "哈哈", "喜欢", "棒"]


def analyze_emotion(text: str) -> Dict[str, Any]:
    """识别用户情绪（MOCK: 关键词规则；Week2 改 LLM structured output）"""
    if any(w in text for w in _SAD_WORDS):
        return {"emotion": "sad", "intensity": 0.8, "confidence": 0.7}
    if any(w in text for w in _ANXIOUS_WORDS):
        return {"emotion": "anxious", "intensity": 0.7, "confidence": 0.7}
    if any(w in text for w in _HAPPY_WORDS):
        return {"emotion": "happy", "intensity": 0.6, "confidence": 0.7}
    return {"emotion": "neutral", "intensity": 0.2, "confidence": 0.5}


def search_memory(query: str, user_id: str = "") -> List[Dict[str, Any]]:
    """检索历史对话（MOCK: 返回空；Week2 接 Qdrant conversation_history + 实体链接）"""
    logger.debug("search_memory mock: query=%s user_id=%s", query, user_id)
    return []


def get_user_profile(user_id: str = "") -> Dict[str, Any]:
    """聚合用户长期画像（MOCK: 占位；Week2 接 Qdrant user_profile collection）"""
    return {
        "user_id": user_id,
        "nickname": "用户",
        "personality": ["温柔", "敏感"],
        "preferences": [],
        "recent_state": "平静",
        "source": "mock",
    }


def update_user_state(user_id: str = "", **updates: Any) -> Dict[str, Any]:
    """更新情绪标签/关系亲密度（MOCK: 仅记录；Week2 写 Qdrant + 画像更新）"""
    logger.info("update_user_state mock: user_id=%s changes=%s", user_id, updates)
    return {"updated": True, "changes": updates, "source": "mock"}


def generate_comfort_response(emotion: str = "neutral", intensity: float = 0.5) -> str:
    """安慰场景专用话术（规则模板；Week2 换专用 prompt template）"""
    templates = {
        "sad": "我在呢。慢慢说，我陪你一起想办法，你不是一个人。",
        "anxious": "先深呼吸一下。事情一件一件来，你已经做得很好了。",
        "happy": "真为你开心！多和我分享一些，我想听。",
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
