"""
Rerank 服务 - 对检索结果重排序

使用 BGE-Reranker-v2-m3 模型
支持:
- 单个模型重排序
- 混合检索结果重排序
- 分数归一化
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from sentence_transformers import CrossEncoder

from app.config import settings

logger = logging.getLogger(__name__)

# 全局 Rerank 模型实例
_rerank_model: CrossEncoder = None


def get_rerank_model() -> CrossEncoder:
    """获取 Rerank 模型实例（懒加载）"""
    global _rerank_model
    if _rerank_model is None:
        logger.info(f"Loading rerank model: {settings.RERANK_MODEL}")
        _rerank_model = CrossEncoder(settings.RERANK_MODEL)
        logger.info("Rerank model loaded successfully")
    return _rerank_model


async def rerank_chunks(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int = 3,
    min_score: float = 0.0,
    normalize: bool = True,
    text_field: str = "content",
) -> List[Dict[str, Any]]:
    """
    对检索结果重排序（Cross-Encoder 精排）

    Args:
        query: 查询文本
        chunks: 检索结果列表
        top_k: 返回前 N 个
        min_score: 最低分数阈值（Threshold 门禁）
        normalize: 是否归一化分数
        text_field: 用于重排的文本字段名（知识库用 "content"，记忆用 "summary"）

    Returns:
        重排序后的结果
    """
    if not chunks:
        return []

    model = get_rerank_model()

    # 构建 (query, passage) 对；兼容记忆场景的 summary 字段
    pairs = [(query, chunk.get(text_field) or chunk.get("content", "")) for chunk in chunks]

    # 计算相关性分数
    scores = model.predict(pairs)

    # 分数归一化 (sigmoid 到 0-1)
    if normalize:
        scores = _normalize_scores(scores)

    # 附加分数到 chunk
    for i, chunk in enumerate(chunks):
        chunk["rerank_score"] = float(scores[i])

    # 应用最低分数阈值
    filtered_chunks = [
        chunk for chunk in chunks
        if chunk.get("rerank_score", 0) >= min_score
    ]

    # 按 rerank_score 排序
    sorted_chunks = sorted(
        filtered_chunks,
        key=lambda x: x["rerank_score"],
        reverse=True,
    )

    return sorted_chunks[:top_k]


def _normalize_scores(scores: np.ndarray, method: str = "sigmoid") -> np.ndarray:
    """
    分数归一化

    Args:
        scores: 原始分数数组
        method: 归一化方法 (sigmoid, minmax, softmax)

    Returns:
        归一化后的分数 (0-1 范围)
    """
    if method == "sigmoid":
        # Sigmoid 归一化
        return 1 / (1 + np.exp(-scores))
    elif method == "minmax":
        # Min-Max 归一化
        min_score = np.min(scores)
        max_score = np.max(scores)
        if max_score - min_score == 0:
            return np.ones_like(scores) * 0.5
        return (scores - min_score) / (max_score - min_score)
    elif method == "softmax":
        # Softmax 归一化
        exp_scores = np.exp(scores - np.max(scores))
        return exp_scores / np.sum(exp_scores)
    else:
        return scores


async def rerank_with_diversity(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int = 3,
    diversity_alpha: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    带多样性保护的重排序

    使用 MMR (Maximal Marginal Relevance) 思想
    在保证相关性的同时增加结果多样性

    Args:
        query: 查询文本
        chunks: 检索结果列表
        top_k: 返回数量
        diversity_alpha: 多样性权重 (0-1, 越大越多样)

    Returns:
        重排序后的结果
    """
    if not chunks or len(chunks) <= 1:
        return await rerank_chunks(query, chunks, top_k)

    model = get_rerank_model()

    # 计算所有 chunk 的 rerank 分数
    pairs = [(query, chunk["content"]) for chunk in chunks]
    scores = model.predict(pairs)

    # 计算 chunk 之间的相似度（用于多样性）
    chunk_similarities = await _compute_chunk_similarities(chunks)

    # MMR 选择
    selected_indices = _mmr_select(
        scores=scores,
        similarities=chunk_similarities,
        top_k=top_k,
        alpha=diversity_alpha,
    )

    # 返回选中的 chunk
    result = []
    for i, idx in enumerate(selected_indices):
        chunk = chunks[idx].copy()
        chunk["rerank_score"] = float(scores[idx])
        chunk["mmr_rank"] = i + 1
        result.append(chunk)

    return result


async def _compute_chunk_similarities(
    chunks: List[Dict[str, Any]],
) -> np.ndarray:
    """
    计算 chunk 之间的相似度矩阵

    使用 Jaccard 相似度（简化实现）
    """
    n = len(chunks)
    similarities = np.zeros((n, n))

    for i in range(n):
        tokens_i = set(chunks[i]["content"].lower().split())
        for j in range(i + 1, n):
            tokens_j = set(chunks[j]["content"].lower().split())
            # Jaccard 相似度
            intersection = len(tokens_i & tokens_j)
            union = len(tokens_i | tokens_j)
            if union > 0:
                sim = intersection / union
                similarities[i, j] = sim
                similarities[j, i] = sim

    return similarities


def _mmr_select(
    scores: np.ndarray,
    similarities: np.ndarray,
    top_k: int,
    alpha: float = 0.5,
) -> List[int]:
    """
    MMR (Maximal Marginal Relevance) 选择算法

    Args:
        scores: 相关性分数
        similarities: 相似度矩阵
        top_k: 选择数量
        alpha: 多样性权重

    Returns:
        选中的索引列表
    """
    n = len(scores)
    if n <= top_k:
        return list(range(n))

    # 归一化分数
    max_score = np.max(scores)
    if max_score > 0:
        norm_scores = scores / max_score
    else:
        norm_scores = scores

    selected = []
    remaining = set(range(n))

    # 选择第一个（最高分）
    first_idx = int(np.argmax(scores))
    selected.append(first_idx)
    remaining.remove(first_idx)

    # 贪心选择剩余
    while len(selected) < top_k and remaining:
        best_idx = None
        best_mmr = -float("inf")

        for idx in remaining:
            # 相关性分数
            relevance = norm_scores[idx]
            # 与已选内容的最大相似度
            max_sim = max(similarities[idx, s] for s in selected)
            # MMR 分数
            mmr = alpha * relevance - (1 - alpha) * max_sim

            if mmr > best_mmr:
                best_mmr = mmr
                best_idx = idx

        if best_idx is not None:
            selected.append(best_idx)
            remaining.remove(best_idx)
        else:
            break

    return selected
