"""
Embedding 服务 - 生成文本向量

使用 BGE-M3 模型，输出 1024 维向量

优化：
- 模型懒加载
- 批量向量化
- 查询向量缓存
"""
import logging
from typing import List
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import settings
from app.services.cache_service import get_vector_cache

logger = logging.getLogger(__name__)

# 全局模型实例（避免重复加载）
_embedding_model: SentenceTransformer = None


def get_embedding_model() -> SentenceTransformer:
    """获取 Embedding 模型实例（懒加载）

    local_files_only=True: 只用本地缓存，不联网校验（避免网络超时挂起 / 离线模式硬失败）
    """
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL, local_files_only=True)
        logger.info("Embedding model loaded successfully")
    return _embedding_model


async def generate_embedding(text: str) -> List[float]:
    """
    生成单个文本的向量

    Args:
        text: 输入文本

    Returns:
        1024 维向量（归一化）
    """
    # 尝试从缓存获取
    cache = get_vector_cache()
    cached = await cache.get_vector(text)
    if cached is not None:
        logger.debug(f"Embedding cache hit: {text[:30]}...")
        return cached

    # 生成向量
    model = get_embedding_model()
    embedding = model.encode(
        text,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    result = embedding.tolist()

    # 缓存结果
    await cache.set_vector(text, result)

    return result


async def generate_embeddings_batch(
    texts: List[str],
    batch_size: int = 32,
) -> List[List[float]]:
    """
    批量生成向量

    Args:
        texts: 输入文本列表
        batch_size: 批处理大小

    Returns:
        向量列表
    """
    model = get_embedding_model()
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    return embeddings.tolist()
