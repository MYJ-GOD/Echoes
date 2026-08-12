"""
Services 模块（已移除 RAG 独占服务）

保留的服务:
- Qdrant 向量数据库服务（Agent 记忆用）
- Embedding 生成服务（Agent 记忆检索用）
- LLM 客户端服务（Agent planner/response 用）
"""

from app.services.qdrant_service import (
    get_client,
    get_async_client,
    check_qdrant_health,
    init_qdrant_collections,
)

from app.services.embedding_service import (
    get_embedding_model,
    generate_embedding,
)

__all__ = [
    # Qdrant
    "get_client",
    "get_async_client",
    "check_qdrant_health",
    "init_qdrant_collections",
    # Embedding
    "get_embedding_model",
    "generate_embedding",
]
