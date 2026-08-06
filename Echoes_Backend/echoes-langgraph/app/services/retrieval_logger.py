"""
检索日志服务 - 记录 RAG 检索详情

用于:
- 检索效果分析
- 用户行为追踪
- 问题排查
- 质量优化
"""
import logging
import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import asyncio

logger = logging.getLogger(__name__)


class RetrievalLog(BaseModel):
    """检索日志数据模型"""

    # 基础信息
    log_id: str = Field(default_factory=lambda: datetime.now().isoformat())
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    conversation_id: str = ""
    turn_id: str = ""
    query: str = ""

    # 检索配置
    kb_ids: List[str] = Field(default_factory=list)
    top_k: int = 5
    retrieval_method: str = "hybrid"  # vector, bm25, hybrid

    # 向量检索结果
    vector_results: List[Dict[str, Any]] = Field(default_factory=list)
    vector_latency_ms: int = 0

    # BM25 检索结果
    bm25_results: List[Dict[str, Any]] = Field(default_factory=list)
    bm25_latency_ms: int = 0

    # 融合后结果
    fused_results: List[Dict[str, Any]] = Field(default_factory=list)

    # Rerank 后结果
    reranked_results: List[Dict[str, Any]] = Field(default_factory=list)
    rerank_latency_ms: int = 0

    # 最终使用的内容
    final_chunks: List[Dict[str, Any]] = Field(default_factory=list)

    # 性能指标
    total_latency_ms: int = 0
    total_chunks_retrieved: int = 0

    # 质量指标
    avg_retrieval_score: float = 0.0
    avg_rerank_score: float = 0.0
    max_retrieval_score: float = 0.0
    max_rerank_score: float = 0.0

    # 元数据
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    client_ip: Optional[str] = None

    # Fallback 信息
    fallback_triggered: bool = False
    fallback_reason: Optional[str] = None


class RetrievalLogger:
    """检索日志记录器"""

    def __init__(self, log_to_file: bool = True, log_to_db: bool = False):
        """
        初始化日志记录器

        Args:
            log_to_file: 是否记录到文件
            log_to_db: 是否记录到数据库
        """
        self.log_to_file = log_to_file
        self.log_to_db = log_to_db
        self._logs_buffer: List[RetrievalLog] = []
        self._buffer_size = 100

    async def log_retrieval(
        self,
        query: str,
        turn_id: str,
        conversation_id: str = "",
        kb_ids: Optional[List[str]] = None,
        vector_results: Optional[List[Dict[str, Any]]] = None,
        bm25_results: Optional[List[Dict[str, Any]]] = None,
        fused_results: Optional[List[Dict[str, Any]]] = None,
        reranked_results: Optional[List[Dict[str, Any]]] = None,
        final_chunks: Optional[List[Dict[str, Any]]] = None,
        latencies: Optional[Dict[str, int]] = None,
        fallback_info: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> RetrievalLog:
        """
        记录一次检索请求

        Args:
            query: 用户查询
            turn_id: 轮次 ID
            conversation_id: 会话 ID
            kb_ids: 知识库 ID 列表
            vector_results: 向量检索结果
            bm25_results: BM25 检索结果
            fused_results: 融合后结果
            reranked_results: Rerank 后结果
            final_chunks: 最终使用的片段
            latencies: 各阶段延迟 (ms)
            fallback_info: Fallback 信息
            user_id: 用户 ID
            session_id: 会话 ID
            client_ip: 客户端 IP

        Returns:
            RetrievalLog 对象
        """
        # 构建日志对象
        log = RetrievalLog(
            conversation_id=conversation_id,
            turn_id=turn_id,
            query=query,
            kb_ids=kb_ids or [],
            vector_results=vector_results or [],
            bm25_results=bm25_results or [],
            fused_results=fused_results or [],
            reranked_results=reranked_results or [],
            final_chunks=final_chunks or [],
            user_id=user_id,
            session_id=session_id,
            client_ip=client_ip,
        )

        # 设置延迟
        if latencies:
            log.vector_latency_ms = latencies.get("vector", 0)
            log.bm25_latency_ms = latencies.get("bm25", 0)
            log.rerank_latency_ms = latencies.get("rerank", 0)
            log.total_latency_ms = latencies.get("total", 0)

        # 设置 Fallback 信息
        if fallback_info:
            log.fallback_triggered = fallback_info.get("triggered", False)
            log.fallback_reason = fallback_info.get("reason")

        # 计算质量指标
        self._compute_metrics(log)

        # 记录日志
        await self._write_log(log)

        return log

    def _compute_metrics(self, log: RetrievalLog):
        """计算检索质量指标"""
        # 检索分数统计
        all_scores = []
        for result in log.vector_results + log.bm25_results:
            if "score" in result and result["score"] > 0:
                all_scores.append(result["score"])

        if all_scores:
            log.avg_retrieval_score = sum(all_scores) / len(all_scores)
            log.max_retrieval_score = max(all_scores)

        # Rerank 分数统计
        rerank_scores = [
            r.get("rerank_score", 0)
            for r in log.reranked_results
            if r.get("rerank_score", 0) > 0
        ]

        if rerank_scores:
            log.avg_rerank_score = sum(rerank_scores) / len(rerank_scores)
            log.max_rerank_score = max(rerank_scores)

        # 总数统计
        log.total_chunks_retrieved = len(log.final_chunks)

    async def _write_log(self, log: RetrievalLog):
        """写入日志"""
        # 文件日志
        if self.log_to_file:
            self._write_to_file(log)

        # 数据库日志（异步批量写入）
        if self.log_to_db:
            self._logs_buffer.append(log)
            if len(self._logs_buffer) >= self._buffer_size:
                await self._flush_to_db()

    def _write_to_file(self, log: RetrievalLog):
        """写入文件日志"""
        log_data = log.model_dump()
        log_file = f"logs/retrieval_{datetime.now().strftime('%Y%m%d')}.jsonl"

        try:
            import os
            os.makedirs("logs", exist_ok=True)

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_data, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write retrieval log to file: {e}")

    async def _flush_to_db(self):
        """批量刷新到数据库"""
        if not self._logs_buffer:
            return

        try:
            # TODO: 实现数据库写入
            # 可以使用 MySQL 或 Qdrant 存储日志
            logger.info(f"Flushing {len(self._logs_buffer)} logs to database")
            self._logs_buffer.clear()
        except Exception as e:
            logger.error(f"Failed to flush logs to database: {e}")

    async def flush(self):
        """强制刷新缓冲区"""
        await self._flush_to_db()


# 全局日志实例
_retrieval_logger: Optional[RetrievalLogger] = None


def get_retrieval_logger() -> RetrievalLogger:
    """获取检索日志实例"""
    global _retrieval_logger
    if _retrieval_logger is None:
        _retrieval_logger = RetrievalLogger(
            log_to_file=True,
            log_to_db=False,  # 暂时只写文件
        )
    return _retrieval_logger


async def log_retrieval_request(
    query: str,
    turn_id: str,
    conversation_id: str = "",
    **kwargs,
) -> RetrievalLog:
    """
    便捷函数：记录检索请求

    Usage:
        await log_retrieval_request(
            query="什么是 RAG?",
            turn_id="turn_001",
            conversation_id="conv_001",
            vector_results=...,
            reranked_results=...,
        )
    """
    logger = get_retrieval_logger()
    return await logger.log_retrieval(
        query=query,
        turn_id=turn_id,
        conversation_id=conversation_id,
        **kwargs,
    )


class RetrievalAnalytics:
    """
    检索分析工具

    用于分析检索效果、用户行为等
    """

    @staticmethod
    def compute_precision_at_k(
        relevant_ids: set,
        retrieved_ids: List[str],
        k: int,
    ) -> float:
        """
        计算 P@K (Precision at K)

        Args:
            relevant_ids: 相关文档 ID 集合
            retrieved_ids: 检索结果 ID 列表
            k: 截断数量

        Returns:
            P@K 值
        """
        top_k = retrieved_ids[:k]
        hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
        return hits / min(k, len(retrieved_ids))

    @staticmethod
    def compute_recall_at_k(
        relevant_ids: set,
        retrieved_ids: List[str],
        k: int,
    ) -> float:
        """
        计算 R@K (Recall at K)

        Args:
            relevant_ids: 相关文档 ID 集合
            retrieved_ids: 检索结果 ID 列表
            k: 截断数量

        Returns:
            R@K 值
        """
        top_k = retrieved_ids[:k]
        hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
        return hits / len(relevant_ids) if relevant_ids else 0.0

    @staticmethod
    def compute_ndcg_at_k(
        relevant_ids: set,
        retrieved_ids: List[str],
        k: int,
    ) -> float:
        """
        计算 NDCG@K (Normalized Discounted Cumulative Gain)

        Args:
            relevant_ids: 相关文档 ID 集合
            retrieved_ids: 检索结果 ID 列表
            k: 截断数量

        Returns:
            NDCG@K 值
        """
        # DCG
        dcg = 0.0
        for i, doc_id in enumerate(retrieved_ids[:k]):
            if doc_id in relevant_ids:
                dcg += 1.0 / (i + 1)

        # IDCG (理想情况)
        ideal_hits = min(len(relevant_ids), k)
        idcg = sum(1.0 / (i + 1) for i in range(ideal_hits))

        return dcg / idcg if idcg > 0 else 0.0

    @staticmethod
    def compute_mrr(relevant_ids: set, retrieved_ids: List[str]) -> float:
        """
        计算 MRR (Mean Reciprocal Rank)

        Args:
            relevant_ids: 相关文档 ID 集合
            retrieved_ids: 检索结果 ID 列表

        Returns:
            MRR 值
        """
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in relevant_ids:
                return 1.0 / (i + 1)
        return 0.0
