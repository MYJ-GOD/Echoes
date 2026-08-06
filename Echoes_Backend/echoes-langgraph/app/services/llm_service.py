"""
LLM 服务 - 调用 Echoes-AI 进行文本生成

提供：
- Query 改写（拼写纠错、指代消解、查询扩展）
- 意图分类（多类别支持）
- RAG 生成
- 纯 LLM 生成
- 引用标注
"""
import logging
import json
from typing import List, Dict, Any, AsyncGenerator, Tuple
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Echoes-AI 服务地址
ECHOES_AI_URL = settings.ECHOES_AI_URL

# 意图分类 Prompt 模板
INTENT_CLASSIFICATION_PROMPT = """你是一个意图分类助手。请将用户查询分类为以下类别之一：

类别定义:
- knowledge_query: 查询事实、概念、定义、操作方法等知识性问题
- chat: 闲聊、问候、情感交流、开放性讨论
- task: 需要执行具体任务，如创建、删除、修改、设置等
- other: 不属于以上类别的其他查询

示例:
- "什么是 RAG?" -> knowledge_query
- "你好" -> chat
- "帮我创建一个待办事项" -> task
- "今天天气怎么样？" -> other

查询：{query}

请只返回类别名称（knowledge_query/chat/task/other），不要返回其他内容。
"""

# Query 改写 Prompt 模板
QUERY_REWRITE_PROMPT = """你是一个查询改写助手。请对用户查询进行以下优化：

1. 拼写纠错：修正明显的拼写错误
2. 指代消解：将代词替换为具体的名词（如果有上下文）
3. 查询扩展：补充隐含的信息，使查询更完整
4. 标准化：使用标准术语和表达

示例:
- 用户："rag 是啥" -> 改写："RAG（检索增强生成）是什么"
- 用户："怎么用它" -> 改写："怎么使用 RAG 技术"
- 用户："python list 转 set" -> 改写："Python 中将列表转换为集合的方法"

用户查询：{query}

请直接返回改写后的查询，不要返回其他内容。
"""

# 意图类别定义
INTENT_CATEGORIES = {
    "knowledge_query": "知识查询",
    "chat": "闲聊对话",
    "task": "任务执行",
    "other": "其他",
}


async def rewrite_query(query: str, conversation_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Query 改写

    功能：
    - 拼写纠错
    - 指代消解
    - 查询扩展
    - 标准化

    Args:
        query: 用户原始查询
        conversation_history: 对话历史（用于指代消解）

    Returns:
        {
            "original_query": str,
            "rewritten_query": str,
            "changes": List[str],
            "use_rewrite": bool
        }
    """
    try:
        # 构建上下文信息
        context_info = ""
        if conversation_history:
            context_info = "\n对话历史:\n"
            for msg in conversation_history[-4:]:  # 最近 4 轮
                role = "用户" if msg["role"] == "user" else "助手"
                context_info += f"{role}: {msg['content']}\n"

        prompt = QUERY_REWRITE_PROMPT.format(query=query)
        if context_info:
            prompt = f"{context_info}\n\n{prompt}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ECHOES_AI_URL}/generate",
                json={"prompt": prompt, "stream": False, "max_tokens": 200},
            )
            response.raise_for_status()
            rewritten = response.json().get("text", "").strip()

            # 如果改写失败或为空，返回原查询
            if not rewritten or len(rewritten) < len(query) * 0.5:
                return {
                    "original_query": query,
                    "rewritten_query": query,
                    "changes": [],
                    "use_rewrite": False,
                }

            # 分析变化
            changes = _analyze_changes(query, rewritten)

            return {
                "original_query": query,
                "rewritten_query": rewritten,
                "changes": changes,
                "use_rewrite": rewritten != query,
            }
    except Exception as e:
        logger.warning(f"Query rewrite failed: {e}, using original query")
        return {
            "original_query": query,
            "rewritten_query": query,
            "changes": [],
            "use_rewrite": False,
        }


def _analyze_changes(original: str, rewritten: str) -> List[str]:
    """分析改写前后的变化"""
    changes = []

    # 长度变化
    if len(rewritten) > len(original) * 1.2:
        changes.append("查询扩展")
    elif len(rewritten) < len(original) * 0.8:
        changes.append("查询精简")

    # 术语标准化（简单检测）
    if original.lower() != rewritten.lower():
        if any(term in rewritten for term in ["是什么", "如何", "怎么", "方法"]):
            changes.append("表达标准化")

    # 拼写纠错检测（简化）
    if len(original) > 3 and rewritten != original:
        changes.append("可能的拼写/语法优化")

    return changes if changes else ["表达优化"]


async def classify_intent(query: str) -> Dict[str, Any]:
    """
    意图分类

    支持类别:
    - knowledge_query: 知识查询
    - chat: 闲聊对话
    - task: 任务执行
    - other: 其他

    Args:
        query: 用户查询

    Returns:
        {
            "intent": str,
            "confidence": float,
            "all_scores": Dict[str, float]
        }
    """
    try:
        prompt = INTENT_CLASSIFICATION_PROMPT.format(query=query)

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{ECHOES_AI_URL}/generate",
                json={"prompt": prompt, "stream": False, "max_tokens": 50},
            )
            response.raise_for_status()
            intent = response.json().get("text", "").strip().lower()

            # 验证返回的意图类别
            if intent not in INTENT_CATEGORIES:
                intent = "knowledge_query"  # 默认

            # 计算置信度（简化实现）
            confidence = _calculate_intent_confidence(query, intent)

            return {
                "intent": intent,
                "confidence": confidence,
                "all_scores": {
                    intent: confidence,
                    **{k: (1 - confidence) / 3 for k in INTENT_CATEGORIES if k != intent}
                }
            }
    except Exception as e:
        logger.warning(f"Intent classification failed: {e}, using default")
        return {
            "intent": "knowledge_query",
            "confidence": 0.5,
            "all_scores": {k: 0.25 for k in INTENT_CATEGORIES}
        }


def _calculate_intent_confidence(query: str, intent: str) -> float:
    """
    计算意图置信度（基于规则的简化实现）

    实际应该使用模型输出的概率
    """
    query_lower = query.lower()

    # 知识查询特征词
    knowledge_patterns = ["是什么", "为什么", "怎么做", "如何", "定义", "概念", "解释", "说明"]
    # 闲聊特征词
    chat_patterns = ["你好", "您好", "hi", "hello", "谢谢", "再见", "早上好"]
    # 任务特征词
    task_patterns = ["创建", "删除", "修改", "更新", "设置", "打开", "关闭", "保存"]

    confidence = 0.7  # 基础置信度

    if intent == "knowledge_query":
        if any(p in query_lower for p in knowledge_patterns):
            confidence += 0.25
    elif intent == "chat":
        if any(p in query_lower for p in chat_patterns):
            confidence += 0.25
    elif intent == "task":
        if any(p in query_lower for p in task_patterns):
            confidence += 0.25

    return min(confidence, 0.99)


async def generate_with_context(
    context: List[Dict[str, Any]],
    query: str,
    stream: bool = True,
) -> List[str]:
    """
    基于上下文生成回答

    Returns:
        文本块列表（流式模式下为生成顺序的 chunk）
    """
    # 构建 RAG Prompt
    context_text = "\n\n".join([
        f"[{i+1}] {chunk['content']}"
        for i, chunk in enumerate(context)
    ])

    prompt = f"""基于以下知识库内容回答问题。如果知识库内容与问题无关，请说明你不知道。

知识库内容：
{context_text}

问题：{query}

回答："""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if stream:
                # 流式调用
                async with client.stream(
                    "POST",
                    f"{ECHOES_AI_URL}/generate",  # TODO: 确认实际 API 路径
                    json={"prompt": prompt, "stream": True},
                ) as response:
                    response.raise_for_status()
                    chunks = []
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            import json
                            try:
                                chunk_data = json.loads(data)
                                if "content" in chunk_data:
                                    chunks.append(chunk_data["content"])
                            except json.JSONDecodeError:
                                continue
                    return chunks
            else:
                response = await client.post(
                    f"{ECHOES_AI_URL}/generate",
                    json={"prompt": prompt, "stream": False},
                )
                response.raise_for_status()
                return [response.json()["text"]]
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        return [f"抱歉，生成回答时出现错误：{str(e)}"]


async def generate_plain(query: str, stream: bool = True) -> List[str]:
    """
    纯 LLM 生成（无检索结果时的降级）
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if stream:
                async with client.stream(
                    "POST",
                    f"{ECHOES_AI_URL}/generate",
                    json={"prompt": query, "stream": True},
                ) as response:
                    response.raise_for_status()
                    chunks = []
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            import json
                            try:
                                chunk_data = json.loads(data)
                                if "content" in chunk_data:
                                    chunks.append(chunk_data["content"])
                            except json.JSONDecodeError:
                                continue
                    return chunks
            else:
                response = await client.post(
                    f"{ECHOES_AI_URL}/generate",
                    json={"prompt": query, "stream": False},
                )
                response.raise_for_status()
                return [response.json()["text"]]
    except Exception as e:
        logger.error(f"Plain LLM generation failed: {e}")
        return [f"抱歉，生成回答时出现错误：{str(e)}"]


async def add_citations(
    response: str,
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    添加引用标注
    """
    citations = []
    for i, chunk in enumerate(chunks):
        citations.append({
            "index": i + 1,
            "document": chunk.get("document", {}),
            "chunk_id": chunk["chunk_id"],
            "score": chunk.get("rerank_score", chunk.get("score", 0)),
        })
    return citations
