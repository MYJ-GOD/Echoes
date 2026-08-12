"""
Qdrant 向量数据库服务（基础设施层，Agent 记忆用）

保留功能：
- get_client / get_async_client
- check_qdrant_health
- init_qdrant_collections（3 个 collection：knowledge_chunks/conversation_history/user_profile）

已移除：
- RAG 检索函数（search_knowledge / search_knowledge_hybrid / upsert_chunks / delete_chunks）
- BM25 混合检索逻辑
"""
import logging
from typing import Optional
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http import models

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
    - knowledge_chunks: 知识片段向量集合（保留定义但 Agent 不用，避免启动报错）
    - conversation_history: 对话历史向量集合（Agent 记忆用）
    - user_profile: 用户画像集合（Agent 用）
    """
    client = get_client()

    collections_config = {
        settings.COLLECTION_KNOWLEDGE: {
            "vectors": models.VectorParams(
                size=settings.VECTOR_SIZE,
                distance=models.Distance.COSINE,
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                )
            ),
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
                {
                    "field_name": "user_id",
                    "field_schema": models.PayloadSchemaType.KEYWORD,
                },
            ]
        },
        settings.COLLECTION_PROFILE: {
            "vectors": models.VectorParams(
                size=settings.VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
            "shard_number": 1,
            "replication_factor": 1,
            "payload_index": [
                {
                    "field_name": "user_id",
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
