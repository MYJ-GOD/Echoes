"""
Qdrant 向量数据库服务
支持：
- 纯向量检索
- BM25 关键词检索
- 混合检索（向量 + BM25）
"""
import hashlib
import logging
import asyncio
from typing import List, Optional, Dict, Any, Tuple
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import SparseVector
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# 全局客户端实例
_qdrant_client: Optional[QdrantClient] = None
_qdrant_async_client: Optional[AsyncQdrantClient] = None


def get_client() -> QdrantClient:
    """获取同步 Qdrant 客户端"""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
        )
    return _qdrant_client


def get_async_client() -> AsyncQdrantClient:
    """获取异步 Qdrant 客户端"""
    global _qdrant_async_client
    if _qdrant_async_client is None:
        _qdrant_async_client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
        )
    return _qdrant_async_client


async def check_qdrant_health() -> bool:
    """检查 Qdrant 服务健康状态"""
    try:
        client = get_client()
        collections = client.get_collections()
        logger.info(f"Qdrant health check: {len(collections.collections)} collections found")
        return True
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        return False


async def init_qdrant_collections():
    """
    初始化 Qdrant Collections

    创建以下集合：
    - knowledge_chunks: 知识片段向量集合（密集向量 + 稀疏向量/BM25）
    - conversation_history: 对话历史向量集合
    """
    client = get_client()

    collections_config = {
        settings.COLLECTION_KNOWLEDGE: {
            "vectors": models.VectorParams(
                size=settings.VECTOR_SIZE,
                distance=models.Distance.COSINE,
                hnsw_config=models.HnswConfigDiff(
                    m=16,           # 每个节点的出边数
                    ef_construct=100,  # 构建时的搜索深度
                )
            ),
            # BM25 稀疏向量配置
            "sparse_vectors": {
                "bm25": models.SparseVectorParams(
                    index=models.SparseIndexParams(
                        on_disk=True,
                    )
                )
            },
            "shard_number": 1,
            "replication_factor": 1,
            "payload_index": [
                {
                    "field_name": "kb_id",
                    "field_schema": models.PayloadSchemaType.KEYWORD,
                },
                {
                    "field_name": "doc_id",
                    "field_schema": models.PayloadSchemaType.KEYWORD,
                },
            ]
        },
        settings.COLLECTION_CONVERSATION: {
            "vectors": models.VectorParams(
                size=settings.VECTOR_SIZE,
                distance=models.Distance.COSINE,
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                )
            ),
            "shard_number": 1,
            "replication_factor": 1,
            "payload_index": [
                {
                    "field_name": "conversation_id",
                    "field_schema": models.PayloadSchemaType.KEYWORD,
                },
                {
                    "field_name": "message_type",
                    "field_schema": models.PayloadSchemaType.KEYWORD,
                },
            ]
        }
    }

    for collection_name, config in collections_config.items():
        if not client.collection_exists(collection_name):
            logger.info(f"Creating collection: {collection_name}")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=config["vectors"],
                sparse_vectors_config=config.get("sparse_vectors"),
                shard_number=config.get("shard_number", 1),
                replication_factor=config.get("replication_factor", 1),
            )

            # 创建 payload 索引
            for idx_config in config.get("payload_index", []):
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=idx_config["field_name"],
                    field_schema=idx_config["field_schema"],
                )
            logger.info(f"Collection {collection_name} created successfully")
        else:
            logger.info(f"Collection {collection_name} already exists")


async def search_knowledge(
    query_vector: List[float],
    kb_ids: Optional[List[str]] = None,
    top_k: int = 5,
    threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    检索知识库（纯向量检索）

    Args:
        query_vector: 查询向量 (1024 维)
        kb_ids: 知识库 ID 列表（None 表示搜索全部）
        top_k: 返回数量
        threshold: 最低相似度阈值

    Returns:
        检索结果列表
    """
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

    results = await client.search(
        collection_name=settings.COLLECTION_KNOWLEDGE,
        query_vector=query_vector,
        query_filter=models.Filter(must=must_conditions) if must_conditions else None,
        limit=top_k,
        score_threshold=threshold,
        with_payload=True,
    )

    return [
        {
            "chunk_id": hit.payload.get("chunk_id"),
            "doc_id": hit.payload.get("doc_id"),
            "kb_id": hit.payload.get("kb_id"),
            "content": hit.payload.get("content"),
            "score": hit.score,
            "document": {
                "title": hit.payload.get("title"),
                "source_url": hit.payload.get("source_url"),
            },
        }
        for hit in results
    ]


async def search_knowledge_hybrid(
    query_vector: List[float],
    query_text: str,
    kb_ids: Optional[List[str]] = None,
    top_k: int = 5,
    alpha: float = 0.7,
    threshold: float = 0.5,
    bm25_top_k: int = 50,
) -> List[Dict[str, Any]]:
    """
    混合检索：向量 + BM25

    使用 Reciprocal Rank Fusion (RRF) 融合两种检索结果

    Args:
        query_vector: 查询向量 (1024 维)
        query_text: 原始查询文本（用于 BM25）
        kb_ids: 知识库 ID 列表
        top_k: 最终返回数量
        alpha: 向量检索权重 (0-1, 0.7 表示向量占 70%，BM25 占 30%)
        threshold: 最低相似度阈值
        bm25_top_k: BM25 初检数量

    Returns:
        融合后的检索结果列表
    """
    logger.info(f"Hybrid search: top_k={top_k}, alpha={alpha}")

    # 并行执行向量检索和 BM25 检索
    vector_results_task = _search_vector_only(
        query_vector=query_vector,
        kb_ids=kb_ids,
        top_k=bm25_top_k,
        threshold=threshold,
    )

    bm25_results_task = _search_bm25(
        query_text=query_text,
        kb_ids=kb_ids,
        top_k=bm25_top_k,
    )

    vector_results, bm25_results = await asyncio.gather(
        vector_results_task,
        bm25_results_task,
        return_exceptions=True
    )

    # 处理异常
    if isinstance(vector_results, Exception):
        logger.error(f"Vector search failed: {vector_results}")
        vector_results = []
    if isinstance(bm25_results, Exception):
        logger.error(f"BM25 search failed: {bm25_results}")
        bm25_results = []

    # 使用 RRF (Reciprocal Rank Fusion) 融合结果
    fused_results = _reciprocal_rank_fusion(
        vector_results=vector_results if vector_results else [],
        bm25_results=bm25_results if bm25_results else [],
        k=60,  # RRF 平滑参数
    )

    # 加权分数融合
    final_results = _weighted_score_fusion(
        fused_results=fused_results,
        vector_results={r["chunk_id"]: r["score"] for r in (vector_results or [])},
        bm25_results={r["chunk_id"]: r["score"] for r in (bm25_results or [])},
        alpha=alpha,
    )

    # 应用阈值过滤
    final_results = [r for r in final_results if r["score"] >= threshold]

    # 返回 top_k
    return final_results[:top_k]


async def _search_vector_only(
    query_vector: List[float],
    kb_ids: Optional[List[str]] = None,
    top_k: int = 50,
    threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """纯向量检索内部方法"""
    client = get_async_client()

    must_conditions = []
    if kb_ids:
        must_conditions.append(
            models.FieldCondition(
                key="kb_id",
                match=models.MatchAny(any=kb_ids),
            )
        )

    results = await client.search(
        collection_name=settings.COLLECTION_KNOWLEDGE,
        query_vector=query_vector,
        query_filter=models.Filter(must=must_conditions) if must_conditions else None,
        limit=top_k,
        score_threshold=threshold,
        with_payload=True,
    )

    return [
        {
            "chunk_id": hit.payload.get("chunk_id"),
            "doc_id": hit.payload.get("doc_id"),
            "kb_id": hit.payload.get("kb_id"),
            "content": hit.payload.get("content"),
            "score": hit.score,
            "vector_score": hit.score,
            "bm25_score": 0.0,
            "document": {
                "title": hit.payload.get("title"),
                "source_url": hit.payload.get("source_url"),
            },
        }
        for hit in results
    ]


async def _search_bm25(
    query_text: str,
    kb_ids: Optional[List[str]] = None,
    top_k: int = 50,
) -> List[Dict[str, Any]]:
    """
    BM25 关键词检索

    使用 Qdrant 的稀疏向量功能实现 BM25
    """
    from app.services.bm25_service import compute_bm25_scores

    client = get_async_client()

    # 过滤条件
    must_conditions = []
    if kb_ids:
        must_conditions.append(
            models.FieldCondition(
                key="kb_id",
                match=models.MatchAny(any=kb_ids),
            )
        )

    # 使用 BM25 服务计算分数
    results = await compute_bm25_scores(
        query=query_text,
        kb_ids=kb_ids,
        top_k=top_k,
    )

    return results


def _reciprocal_rank_fusion(
    vector_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    k: int = 60,
) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) 融合算法

    RRF 分数 = Σ 1/(k + rank_i)

    Args:
        vector_results: 向量检索结果
        bm25_results: BM25 检索结果
        k: 平滑参数，通常为 60

    Returns:
        融合后的结果（按 RRF 分数排序）
    """
    # 构建 chunk_id -> 结果映射
    results_map: Dict[str, Dict[str, Any]] = {}

    # 添加向量检索结果
    for i, result in enumerate(vector_results):
        chunk_id = result["chunk_id"]
        results_map[chunk_id] = {
            **result,
            "vector_rank": i + 1,
            "bm25_rank": None,
            "rrf_score": 1.0 / (k + i + 1),
        }

    # 添加/合并 BM25 结果
    for i, result in enumerate(bm25_results):
        chunk_id = result["chunk_id"]
        if chunk_id in results_map:
            # 已存在，更新
            results_map[chunk_id]["bm25_rank"] = i + 1
            results_map[chunk_id]["rrf_score"] += 1.0 / (k + i + 1)
        else:
            # 新结果
            results_map[chunk_id] = {
                **result,
                "vector_rank": None,
                "bm25_rank": i + 1,
                "rrf_score": 1.0 / (k + i + 1),
            }

    # 按 RRF 分数排序
    fused_list = sorted(
        results_map.values(),
        key=lambda x: x["rrf_score"],
        reverse=True,
    )

    return fused_list


def _weighted_score_fusion(
    fused_results: List[Dict[str, Any]],
    vector_results: Dict[str, float],
    bm25_results: Dict[str, float],
    alpha: float = 0.7,
) -> List[Dict[str, Any]]:
    """
    加权分数融合

    final_score = alpha * vector_score + (1 - alpha) * bm25_score

    Args:
        fused_results: RRF 融合后的结果
        vector_results: 向量分数映射
        bm25_results: BM25 分数映射
        alpha: 向量权重

    Returns:
        加权融合后的结果
    """
    for result in fused_results:
        chunk_id = result["chunk_id"]
        vector_score = vector_results.get(chunk_id, 0.0)
        bm25_score = bm25_results.get(chunk_id, 0.0)

        # 标准化分数 (0-1 范围)
        normalized_vector = min(max(vector_score, 0), 1)
        normalized_bm25 = min(max(bm25_score / 10.0, 0), 1)  # BM25 分数通常较大，需要缩放

        # 加权融合
        result["score"] = alpha * normalized_vector + (1 - alpha) * normalized_bm25
        result["fusion_method"] = "weighted_rrf"

    # 按最终分数重新排序
    return sorted(fused_results, key=lambda x: x["score"], reverse=True)


async def upsert_chunks(
    chunks: List[Dict[str, Any]],
    vectors: List[List[float]],
):
    """
    向量化存储文档片段

    Args:
        chunks: 文档片段列表
        vectors: 对应的向量列表
    """
    client = get_async_client()

    points = []
    for chunk, vector in zip(chunks, vectors):
        chunk_id_str = str(chunk.get("chunk_id", ""))
        point_id = int(hashlib.md5(chunk_id_str.encode()).hexdigest()[:16], 16) % (2**63)
        points.append(models.PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "kb_id": chunk["kb_id"],
                "content": chunk["content"],
                "chunk_index": chunk["chunk_index"],
                "title": chunk.get("title", ""),
                "source_url": chunk.get("source_url", ""),
                "metadata": chunk.get("metadata", {}),
            },
        ))

    await client.upsert(
        collection_name=settings.COLLECTION_KNOWLEDGE,
        points=points,
    )


async def delete_chunks_by_doc(doc_id: str):
    """
    删除指定文档的所有片段

    Args:
        doc_id: 文档 ID
    """
    client = get_async_client()

    await client.delete(
        collection_name=settings.COLLECTION_KNOWLEDGE,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="doc_id",
                        match=models.MatchValue(value=doc_id),
                    )
                ]
            )
        ),
    )
