"""
对话管理服务

提供：
- 对话历史存储
- 上下文压缩
- 多轮对话管理
- 指代消解支持
"""
import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class ConversationMessage:
    """对话消息"""

    def __init__(
        self,
        role: str,
        content: str,
        turn_id: str,
        timestamp: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.role = role
        self.content = content
        self.turn_id = turn_id
        self.timestamp = timestamp or datetime.now().isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "turn_id": self.turn_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMessage":
        return cls(
            role=data["role"],
            content=data["content"],
            turn_id=data["turn_id"],
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata"),
        )


class ConversationHistory:
    """
    对话历史管理

    功能：
    - 存储对话轮次
    - 上下文窗口管理
    - 消息压缩
    """

    def __init__(
        self,
        conversation_id: str,
        max_turns: int = 10,
        max_tokens: int = 4000,
    ):
        """
        初始化对话历史

        Args:
            conversation_id: 对话 ID
            max_turns: 最大保留轮次
            max_tokens: 最大 token 数（用于压缩）
        """
        self.conversation_id = conversation_id
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.messages: List[ConversationMessage] = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at

    def add_message(
        self,
        role: str,
        content: str,
        turn_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """添加消息"""
        message = ConversationMessage(
            role=role,
            content=content,
            turn_id=turn_id,
            metadata=metadata,
        )
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()

        # 裁剪超出轮次
        self._trim_turns()

    def _trim_turns(self):
        """裁剪到最大轮次"""
        if len(self.messages) > self.max_turns * 2:  # 每轮 2 条消息（user + assistant）
            # 保留最近的 max_turns 轮
            self.messages = self.messages[-self.max_turns * 2:]

    def get_messages(self, limit: int = None) -> List[Dict[str, Any]]:
        """获取消息列表"""
        messages = self.messages
        if limit:
            messages = messages[-limit:]
        return [m.to_dict() for m in messages]

    def get_context_for_llm(self) -> str:
        """
        获取用于 LLM 的上下文

        返回格式化的对话历史字符串
        """
        context_lines = []
        for msg in self.messages[-self.max_turns:]:
            role_name = "用户" if msg.role == "user" else "助手"
            context_lines.append(f"{role_name}: {msg.content}")
        return "\n".join(context_lines)

    def compress(self) -> str:
        """
        压缩对话历史

        使用摘要方式压缩早期对话
        """
        if len(self.messages) <= 4:
            return self.get_context_for_llm()

        # 保留最近 2 轮完整对话
        recent_messages = self.messages[-4:]
        recent_context = "\n".join([
            f"{'用户' if m.role == 'user' else '助手'}: {m.content}"
            for m in recent_messages
        ])

        # 压缩早期对话为摘要
        early_messages = self.messages[:-4]
        if early_messages:
            summary = self._generate_summary(early_messages)
            return f"[早期对话摘要] {summary}\n\n[最近对话]\n{recent_context}"

        return recent_context

    def _generate_summary(self, messages: List[ConversationMessage]) -> str:
        """生成对话摘要（简化实现）"""
        # 提取关键主题
        topics = []
        for msg in messages:
            if msg.role == "user" and len(msg.content) > 5:
                topics.append(msg.content[:50])

        if topics:
            return f"讨论了：{', '.join(topics[:3])}"
        return "进行了多轮对话"

    def clear(self):
        """清空对话"""
        self.messages = []
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "max_turns": self.max_turns,
            "messages": [m.to_dict() for m in self.messages],
        }


# 全局对话缓存（生产环境应该使用 Redis）
_conversation_cache: Dict[str, ConversationHistory] = {}
_cache_lock = asyncio.Lock()


async def get_conversation(
    conversation_id: str,
    max_turns: int = 10,
) -> ConversationHistory:
    """获取或创建对话历史"""
    global _conversation_cache

    async with _cache_lock:
        if conversation_id not in _conversation_cache:
            _conversation_cache[conversation_id] = ConversationHistory(
                conversation_id=conversation_id,
                max_turns=max_turns,
            )
        return _conversation_cache[conversation_id]


async def save_message(
    conversation_id: str,
    role: str,
    content: str,
    turn_id: str,
    metadata: Optional[Dict[str, Any]] = None,
):
    """保存消息到对话历史"""
    conversation = await get_conversation(conversation_id)
    conversation.add_message(role, content, turn_id, metadata)


async def get_recent_messages(
    conversation_id: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """获取最近的消息"""
    conversation = await get_conversation(conversation_id)
    return conversation.get_messages(limit=limit)


async def clear_conversation(conversation_id: str):
    """清空对话"""
    global _conversation_cache

    async with _cache_lock:
        if conversation_id in _conversation_cache:
            _conversation_cache[conversation_id].clear()


async def resolve_reference(
    query: str,
    conversation_id: str,
) -> str:
    """
    指代消解

    将查询中的代词替换为具体的名词

    Args:
        query: 用户查询
        conversation_id: 对话 ID

    Returns:
        消解后的查询
    """
    # 获取对话历史
    messages = await get_recent_messages(conversation_id, limit=6)

    # 检测代词
    pronouns = ["它", "他", "她", "这个", "那个", "这些", "那些", "其", "此"]
    has_pronoun = any(p in query for p in pronouns)

    if not has_pronoun:
        return query

    # 从历史中提取可能的指代对象
    referents = []
    for msg in reversed(messages):
        if msg["role"] == "user":
            # 提取名词短语（简化实现）
            content = msg["content"]
            if len(content) > 2 and len(content) < 50:
                referents.append(content)
            if len(referents) >= 2:
                break

    if not referents:
        return query

    # 替换代词（简化实现）
    resolved_query = query
    for pronoun in pronouns:
        if pronoun in resolved_query and referents:
            # 使用最近的指代对象
            resolved_query = resolved_query.replace(pronoun, referents[0], 1)
            break

    return resolved_query


class ConversationManager:
    """
    对话管理器

    提供高级对话管理功能
    """

    def __init__(self):
        self.conversations: Dict[str, ConversationHistory] = {}

    async def create_conversation(
        self,
        conversation_id: str,
        max_turns: int = 10,
    ) -> ConversationHistory:
        """创建新对话"""
        conversation = ConversationHistory(
            conversation_id=conversation_id,
            max_turns=max_turns,
        )
        self.conversations[conversation_id] = conversation
        return conversation

    async def get_conversation(
        self,
        conversation_id: str,
    ) -> Optional[ConversationHistory]:
        """获取对话"""
        return self.conversations.get(conversation_id)

    async def delete_conversation(self, conversation_id: str) -> bool:
        """删除对话"""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            return True
        return False

    async def get_active_conversations(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取活跃的对话列表"""
        conversations = sorted(
            self.conversations.values(),
            key=lambda c: c.updated_at,
            reverse=True,
        )
        return [
            {
                "conversation_id": c.conversation_id,
                "updated_at": c.updated_at,
                "message_count": len(c.messages),
            }
            for c in conversations[:limit]
        ]


# 全局管理器实例
_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """获取对话管理器"""
    global _manager
    if _manager is None:
        _manager = ConversationManager()
    return _manager
