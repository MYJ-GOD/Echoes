"""
测试配置
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_embedding_vector():
    """Mock Embedding 向量"""
    return [0.1] * 1024


@pytest.fixture
def sample_chunks():
    """样本检索结果"""
    return [
        {
            "chunk_id": "chunk_001",
            "content": "RAG (Retrieval-Augmented Generation) is a technique that combines retrieval and generation.",
            "score": 0.85,
            "kb_id": "kb_test",
            "doc_id": "doc_001",
        },
        {
            "chunk_id": "chunk_002",
            "content": "Vector databases store embeddings for efficient similarity search.",
            "score": 0.78,
            "kb_id": "kb_test",
            "doc_id": "doc_002",
        },
        {
            "chunk_id": "chunk_003",
            "content": "BM25 is a probabilistic ranking function used in information retrieval.",
            "score": 0.72,
            "kb_id": "kb_test",
            "doc_id": "doc_003",
        },
    ]


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant 客户端"""
    client = MagicMock()
    client.search = AsyncMock(return_value=[])
    client.upsert = AsyncMock(return_value=None)
    client.delete = AsyncMock(return_value=None)
    client.scroll = AsyncMock(return_value=([], None))
    return client


@pytest.fixture
def relevant_ids():
    """相关文档 ID 集合（用于评估测试）"""
    return {
        "query_1": {"chunk_001", "chunk_002"},
        "query_2": {"chunk_003", "chunk_004", "chunk_005"},
        "query_3": {"chunk_001", "chunk_005"},
    }
