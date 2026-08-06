"""
文档索引服务 - 负责文档的向量化和存储
"""
import logging
from typing import List, Dict, Any
import hashlib

from app.services.qdrant_service import upsert_chunks, delete_chunks_by_doc
from app.services.embedding_service import generate_embeddings_batch

logger = logging.getLogger(__name__)


async def index_document(
    doc_id: str,
    kb_id: str,
    chunks: List[Dict[str, Any]],
    embedding_version: str = "bge-m3-v1",
) -> bool:
    """
    索引文档 - 将文档片段向量化并存储到 Qdrant

    Args:
        doc_id: 文档 ID
        kb_id: 知识库 ID
        chunks: 文档片段列表（包含 content, chunk_index 等字段）
        embedding_version: Embedding 模型版本

    Returns:
        是否成功
    """
    try:
        logger.info(f"Indexing document: doc_id={doc_id}, chunks={len(chunks)}")

        # 提取内容
        texts = [chunk["content"] for chunk in chunks]

        # 批量生成向量
        vectors = await generate_embeddings_batch(texts, batch_size=32)

        # 准备上传数据
        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            chunk_id = chunk.get("chunk_id") or f"{doc_id}_chunk_{i}"
            points.append({
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "kb_id": kb_id,
                "content": chunk["content"],
                "chunk_index": chunk.get("chunk_index", i),
                "title": chunk.get("title", ""),
                "source_url": chunk.get("source_url", ""),
                "metadata": chunk.get("metadata", {}),
            })

        # 存储到 Qdrant
        await upsert_chunks(points, vectors)

        logger.info(f"Document indexed successfully: doc_id={doc_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to index document: doc_id={doc_id}, error={e}")
        return False


async def reindex_document(
    doc_id: str,
    kb_id: str,
    chunks: List[Dict[str, Any]],
) -> bool:
    """
    重新索引文档 - 先删除旧的，再添加新的

    Args:
        doc_id: 文档 ID
        kb_id: 知识库 ID
        chunks: 新的文档片段列表

    Returns:
        是否成功
    """
    try:
        # 删除旧的向量
        await delete_chunks_by_doc(doc_id)

        # 索引新的
        return await index_document(doc_id, kb_id, chunks)

    except Exception as e:
        logger.error(f"Failed to reindex document: doc_id={doc_id}, error={e}")
        return False


async def delete_document_index(doc_id: str) -> bool:
    """
    删除文档索引

    Args:
        doc_id: 文档 ID

    Returns:
        是否成功
    """
    try:
        await delete_chunks_by_doc(doc_id)
        logger.info(f"Document index deleted: doc_id={doc_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete document index: doc_id={doc_id}, error={e}")
        return False


def generate_chunk_id(doc_id: str, index: int) -> str:
    """
    生成 Chunk ID

    使用 doc_id + index 的 hash 确保唯一性
    """
    content = f"{doc_id}_chunk_{index}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]
