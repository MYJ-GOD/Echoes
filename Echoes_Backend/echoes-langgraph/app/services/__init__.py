"""
Services 模块

提供核心服务功能:
- Qdrant 向量数据库服务
- Embedding 生成服务
- BM25 关键词检索
- Rerank 重排序服务
- LLM 文本生成服务
- 检索日志服务
- 文档索引服务
"""

from app.services.qdrant_service import (
    get_client,
    get_async_client,
    check_qdrant_health,
    init_qdrant_collections,
    search_knowledge,
    search_knowledge_hybrid,
    upsert_chunks,
    delete_chunks_by_doc,
)

from app.services.embedding_service import (
    get_embedding_model,
    generate_embedding,
)

from app.services.rerank_service import (
    get_rerank_model,
    rerank_chunks,
    rerank_with_diversity,
)

from app.services.llm_service import (
    rewrite_query,
    classify_intent,
    generate_with_context,
    generate_plain,
    add_citations,
)

from app.services.retrieval_logger import (
    RetrievalLogger,
    RetrievalLog,
    get_retrieval_logger,
    log_retrieval_request,
    RetrievalAnalytics,
)

from app.services.bm25_service import (
    BM25Scorer,
    get_bm25_scorer,
    compute_bm25_scores,
    build_bm25_index,
)

__all__ = [
    # Qdrant
    "get_client",
    "get_async_client",
    "check_qdrant_health",
    "init_qdrant_collections",
    "search_knowledge",
    "search_knowledge_hybrid",
    "upsert_chunks",
    "delete_chunks_by_doc",
    # Embedding
    "get_embedding_model",
    "generate_embedding",
    # Rerank
    "get_rerank_model",
    "rerank_chunks",
    "rerank_with_diversity",
    # LLM
    "rewrite_query",
    "classify_intent",
    "generate_with_context",
    "generate_plain",
    "add_citations",
    # Logger
    "RetrievalLogger",
    "RetrievalLog",
    "get_retrieval_logger",
    "log_retrieval_request",
    "RetrievalAnalytics",
    # BM25
    "BM25Scorer",
    "get_bm25_scorer",
    "compute_bm25_scores",
    "build_bm25_index",
]
