"""
BM25 关键词检索服务

使用 Qdrant 稀疏向量功能实现 BM25 检索
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional
from collections import Counter
import math

from qdrant_client.http import models
from qdrant_client.http.models import SparseVector

from app.config import settings
from app.services.qdrant_service import get_async_client

logger = logging.getLogger(__name__)


class BM25Scorer:
    """
    BM25 评分器

    BM25 (Best Matching 25) 是一种经典的词频 - 逆文档频率算法
    用于评估文档与查询的相关性

    公式:
    BM25(q, d) = Σ IDF(qi) * (f(qi, d) * (k1 + 1)) / (f(qi, d) + k1 * (1 - b + b * |d|/avgdl))

    其中:
    - qi: 查询词
    - d: 文档
    - f(qi, d): 词 qi 在文档 d 中的词频
    - IDF(qi): 逆文档频率
    - |d|: 文档长度
    - avgdl: 平均文档长度
    - k1, b: 超参数
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        初始化 BM25 参数

        Args:
            k1: 控制词频饱和度的参数 (1.2-2.0)，越大词频影响越大
            b: 控制文档长度归一化的参数 (0-1)，越大长度影响越大
        """
        self.k1 = k1
        self.b = b

        # 倒排索引缓存
        self._inverted_index: Dict[str, Dict[str, float]] = {}
        self._doc_lengths: Dict[str, int] = {}
        self._avg_doc_length: float = 0.0
        self._num_docs: int = 0

    def _tokenize(self, text: str) -> List[str]:
        """
        文本分词

        支持:
        - 英文：按空格分词
        - 中文：简单按字符分词（可替换为 jieba 等）
        """
        # 简单实现：按空格和标点分词
        import re
        # 提取所有字母数字和中文字符
        tokens = re.findall(r'[\w\u4e00-\u9fff]+', text.lower())
        return [t for t in tokens if len(t) > 0]

    def _compute_idf(self, term: str, doc_count_with_term: int) -> float:
        """
        计算逆文档频率 (IDF)

        IDF(qi) = log((N - n(qi) + 0.5) / (n(qi) + 0.5) + 1)

        Args:
            doc_count_with_term: 包含该词的文档数

        Returns:
            IDF 分数
        """
        if self._num_docs == 0:
            return 0.0
        return math.log((self._num_docs - doc_count_with_term + 0.5) / (doc_count_with_term + 0.5) + 1)


# 全局 BM25 实例
_bm25_scorer: Optional[BM25Scorer] = None


def get_bm25_scorer() -> BM25Scorer:
    """获取 BM25 评分器实例"""
    global _bm25_scorer
    if _bm25_scorer is None:
        _bm25_scorer = BM25Scorer()
    return _bm25_scorer


async def compute_bm25_scores(
    query: str,
    kb_ids: Optional[List[str]] = None,
    top_k: int = 50,
    threshold: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    计算 BM25 分数

    使用 Qdrant 的全文检索功能

    Args:
        query: 查询文本
        kb_ids: 知识库 ID 列表
        top_k: 返回数量
        threshold: 最低分数阈值

    Returns:
        带 BM25 分数的检索结果
    """
    try:
        client = get_async_client()

        # 构建过滤条件
        must_conditions = []
        if kb_ids:
            must_conditions.append(
                models.FieldCondition(
                    key="kb_id",
                    match=models.MatchAny(any=kb_ids),
                )
            )

        # 使用 Qdrant 的全文检索（需要 Qdrant 1.7+）
        # 注意：如果 Qdrant 版本不支持，使用备用方案
        try:
            from qdrant_client.http import models

            # 创建稀疏向量（词频向量）
            sparse_vector = await _create_sparse_vector(query)

            results = await client.search(
                collection_name=settings.COLLECTION_KNOWLEDGE,
                query_vector=sparse_vector,
                query_filter=models.Filter(must=must_conditions) if must_conditions else None,
                limit=top_k,
                with_payload=True,
            )

            return [
                {
                    "chunk_id": hit.payload.get("chunk_id"),
                    "doc_id": hit.payload.get("doc_id"),
                    "kb_id": hit.payload.get("kb_id"),
                    "content": hit.payload.get("content"),
                    "score": hit.score,
                    "bm25_score": hit.score,
                    "vector_score": 0.0,
                    "document": {
                        "title": hit.payload.get("title"),
                        "source_url": hit.payload.get("source_url"),
                    },
                }
                for hit in results
                if hit.score >= threshold
            ]

        except Exception as e:
            logger.warning(f"Qdrant sparse vector search not available: {e}")
            # 备用方案：内存中计算 BM25
            return await _compute_bm25_in_memory(query, kb_ids, top_k)

    except Exception as e:
        logger.error(f"BM25 search failed: {e}")
        return []


async def _create_sparse_vector(query: str) -> SparseVector:
    """
    创建稀疏向量（词频向量）

    将查询文本转换为词频向量
    """
    from qdrant_client.http.models import SparseVector
    from app.services.tokenizer_service import tokenize_with_indices

    # 获取词及其在词汇表中的索引
    tokens_with_indices = await tokenize_with_indices(query)

    # 构建稀疏向量：{index: frequency}
    indices = []
    values = []
    for token, index in tokens_with_indices:
        indices.append(index)
        values.append(1.0)  # 简单词频，可以优化为 TF-IDF

    return SparseVector(
        indices=indices,
        values=values,
    )


async def _compute_bm25_in_memory(
    query: str,
    kb_ids: Optional[List[str]] = None,
    top_k: int = 50,
) -> List[Dict[str, Any]]:
    """
    内存中计算 BM25（备用方案）

    当 Qdrant 不支持稀疏向量时使用
    """
    from app.services.qdrant_service import get_async_client
    from app.config import settings
    from qdrant_client.http import models

    client = get_async_client()

    # 获取候选文档
    must_conditions = []
    if kb_ids:
        must_conditions.append(
            models.FieldCondition(
                key="kb_id",
                match=models.MatchAny(any=kb_ids),
            )
        )

    # 使用 scroll 获取所有候选文档
    scroll_filter = models.Filter(must=must_conditions) if must_conditions else None

    records, _ = await client.scroll(
        collection_name=settings.COLLECTION_KNOWLEDGE,
        scroll_filter=scroll_filter,
        limit=500,  # 最多处理 500 个文档
        with_payload=True,
    )

    if not records:
        return []

    # 计算 BM25 分数
    scorer = get_bm25_scorer()
    query_tokens = scorer._tokenize(query)

    if not query_tokens:
        return []

    results = []
    for record in records:
        content = record.payload.get("content", "")
        doc_tokens = scorer._tokenize(content)

        if not doc_tokens:
            continue

        # 计算 BM25 分数
        score = _compute_bm25_score(query_tokens, doc_tokens, len(content))

        if score > 0:
            results.append({
                "chunk_id": record.payload.get("chunk_id"),
                "doc_id": record.payload.get("doc_id"),
                "kb_id": record.payload.get("kb_id"),
                "content": record.payload.get("content"),
                "score": score,
                "bm25_score": score,
                "vector_score": 0.0,
                "document": {
                    "title": record.payload.get("title"),
                    "source_url": record.payload.get("source_url"),
                },
            })

    # 按分数排序并返回 top_k
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def _compute_bm25_score(
    query_tokens: List[str],
    doc_tokens: List[str],
    doc_length: int,
    k1: float = 1.5,
    b: float = 0.75,
    avg_doc_length: float = 500.0,
) -> float:
    """
    计算单个文档的 BM25 分数

    Args:
        query_tokens: 查询分词
        doc_tokens: 文档分词
        doc_length: 文档长度（字符数）
        k1: 词频饱和度参数
        b: 长度归一化参数
        avg_doc_length: 平均文档长度

    Returns:
        BM25 分数
    """
    # 统计文档词频
    doc_term_freq = Counter(doc_tokens)

    # 估算包含每个词的文档数（简化实现）
    num_docs = 1000  # 假设总文档数
    score = 0.0

    for term in query_tokens:
        if term not in doc_term_freq:
            continue

        tf = doc_term_freq[term]
        # 简化 IDF（假设每个词出现在 10% 的文档中）
        idf = math.log((num_docs * 0.9 + 0.5) / (num_docs * 0.1 + 0.5) + 1)

        # BM25 词频部分
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * doc_length / avg_doc_length)

        score += idf * numerator / denominator

    return score


async def build_bm25_index():
    """
    构建 BM25 索引

    从 Qdrant 读取所有文档并构建内存索引
    """
    from app.services.qdrant_service import get_async_client

    client = get_async_client()
    scorer = get_bm25_scorer()

    # 获取所有文档
    records, _ = await client.scroll(
        collection_name=settings.COLLECTION_KNOWLEDGE,
        limit=10000,
        with_payload=True,
    )

    # 构建索引
    total_length = 0
    for record in records:
        content = record.payload.get("content", "")
        chunk_id = record.payload.get("chunk_id")

        if not content or not chunk_id:
            continue

        tokens = scorer._tokenize(content)
        scorer._doc_lengths[chunk_id] = len(tokens)
        total_length += len(tokens)

        # 更新倒排索引
        for term in tokens:
            if term not in scorer._inverted_index:
                scorer._inverted_index[term] = {}
            if chunk_id not in scorer._inverted_index[term]:
                scorer._inverted_index[term][chunk_id] = 0
            scorer._inverted_index[term][chunk_id] += 1

    scorer._num_docs = len(records)
    scorer._avg_doc_length = total_length / max(len(records), 1)

    logger.info(f"BM25 index built: {scorer._num_docs} docs, avg_length={scorer._avg_doc_length:.1f}")
