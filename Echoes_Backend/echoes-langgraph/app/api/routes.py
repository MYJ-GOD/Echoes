"""
API 路由定义
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, AsyncGenerator, Dict, Any
import json
import time
import os

from app.config import settings
from app.graph.workflow import rag_workflow

router = APIRouter()
logger = logging.getLogger(__name__)


# ============== 请求/响应模型 ==============

class RAGRequest(BaseModel):
    query: str
    turn_id: str
    conversation_id: Optional[str] = None
    kb_ids: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1, le=20)
    stream: bool = True


class RAGResponse(BaseModel):
    response: str
    context: List[dict]
    citations: List[dict]
    latency_ms: int
    fallback_reason: Optional[str] = None


class ChunkResponse(BaseModel):
    chunk_id: str
    content: str
    score: float
    document: dict


class SearchRequest(BaseModel):
    query: str
    kb_ids: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1, le=50)
    threshold: float = Field(default=0.5, ge=0, le=1)


class SearchResponse(BaseModel):
    results: List[ChunkResponse]
    latency_ms: int


class HybridSearchRequest(BaseModel):
    query: str
    kb_ids: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1, le=50)
    threshold: float = Field(default=0.5, ge=0, le=1)
    alpha: float = Field(default=0.7, ge=0, le=1, description="向量检索权重")
    use_rerank: bool = Field(default=True, description="是否使用 Rerank")


class HybridSearchResponse(BaseModel):
    results: List[ChunkResponse]
    retrieval_method: str
    vector_count: int
    bm25_count: int
    final_count: int
    latency_ms: int


class MetricsResponse(BaseModel):
    total_requests: int
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_retrieval_score: float
    fallback_rate: float


# ============== 健康检查 ==============

@router.get("/health")
def health_check():
    """健康检查"""
    return {"status": "healthy"}


# ============== 向量检索 ==============

@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    向量检索 API（非流式）

    用于直接检索知识库片段
    """
    start_time = time.time()

    try:
        from app.services.qdrant_service import search_knowledge
        from app.services.embedding_service import generate_embedding

        # 生成查询向量
        query_vector = await generate_embedding(request.query)

        # 执行检索
        results = await search_knowledge(
            query_vector=query_vector,
            kb_ids=request.kb_ids,
            top_k=request.top_k,
            threshold=request.threshold,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        return SearchResponse(
            results=[
                ChunkResponse(
                    chunk_id=chunk["chunk_id"],
                    content=chunk["content"],
                    score=chunk["score"],
                    document=chunk.get("document", {}),
                )
                for chunk in results
            ],
            latency_ms=latency_ms,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/hybrid", response_model=HybridSearchResponse)
async def search_hybrid(request: HybridSearchRequest):
    """
    混合检索 API（向量 + BM25）

    使用 RRF (Reciprocal Rank Fusion) 融合两种检索结果
    """
    start_time = time.time()

    try:
        from app.services.qdrant_service import search_knowledge_hybrid
        from app.services.embedding_service import generate_embedding
        from app.services.rerank_service import rerank_chunks

        # 生成查询向量
        query_vector = await generate_embedding(request.query)

        # 执行混合检索
        results = await search_knowledge_hybrid(
            query_vector=query_vector,
            query_text=request.query,
            kb_ids=request.kb_ids,
            top_k=request.top_k * 3,  # 初检更多结果用于 Rerank
            alpha=request.alpha,
            threshold=request.threshold,
        )

        # 可选 Rerank
        if request.use_rerank and results:
            results = await rerank_chunks(
                query=request.query,
                chunks=results,
                top_k=request.top_k,
            )
        else:
            results = results[:request.top_k]

        latency_ms = int((time.time() - start_time) * 1000)

        return HybridSearchResponse(
            results=[
                ChunkResponse(
                    chunk_id=chunk["chunk_id"],
                    content=chunk["content"],
                    score=chunk.get("rerank_score", chunk["score"]),
                    document=chunk.get("document", {}),
                )
                for chunk in results
            ],
            retrieval_method="hybrid_rrf",
            vector_count=len(results),
            bm25_count=len(results),
            final_count=len(results),
            latency_ms=latency_ms,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== RAG 对话（核心） ==============

@router.post("/rag/chat", response_model=RAGResponse)
async def chat(request: RAGRequest) -> RAGResponse:
    """
    RAG 对话（非流式）

    执行完整的 RAG 工作流并返回最终结果
    """
    from app.services.conversation_service import save_message
    from app.services.retrieval_logger import log_retrieval_request

    start_time = time.time()

    try:
        # 执行工作流
        result = await rag_workflow.ainvoke({
            "query": request.query,
            "turn_id": request.turn_id,
            "conversation_id": request.conversation_id or "",
            "kb_ids": request.kb_ids or [],
            "top_k": request.top_k,
        })

        latency_ms = int((time.time() - start_time) * 1000)

        # 组装响应
        response_text = "".join(result.get("response_chunks", []))

        # 持久化对话消息
        conversation_id = request.conversation_id or ""
        if conversation_id:
            await save_message(conversation_id, "user", request.query, request.turn_id)
            await save_message(conversation_id, "assistant", response_text, request.turn_id)

        # 写入检索日志
        await log_retrieval_request(
            query=request.query,
            turn_id=request.turn_id,
            conversation_id=conversation_id,
            kb_ids=request.kb_ids or [],
            reranked_results=result.get("reranked_chunks", []),
            final_chunks=result.get("reranked_chunks", []),
            latencies={"total": latency_ms},
            fallback_info={
                "triggered": bool(result.get("fallback_reason")),
                "reason": result.get("fallback_reason"),
            },
        )

        return RAGResponse(
            response=response_text,
            context=result.get("reranked_chunks", []),
            citations=result.get("citations", []),
            latency_ms=latency_ms,
            fallback_reason=result.get("fallback_reason"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/chat/stream")
async def chat_stream(request: RAGRequest):
    """
    RAG 对话（流式）- 输出 NDJSON 格式

    Java 端负责将 NDJSON 转为 SSE 事件
    """
    from app.services.conversation_service import save_message
    from app.services.retrieval_logger import log_retrieval_request

    conversation_id = request.conversation_id or ""
    seq = 0

    async def generate() -> AsyncGenerator[str, None]:
        nonlocal seq
        collected_response = ""
        stream_start = time.time()
        last_reranked = []
        last_fallback_reason = None

        try:
            # 使用 astream 流式执行
            async for event in rag_workflow.astream(
                {
                    "query": request.query,
                    "turn_id": request.turn_id,
                    "conversation_id": conversation_id,
                    "kb_ids": request.kb_ids or [],
                    "top_k": request.top_k,
                },
                stream_mode="values",  # 输出状态变化
            ):
                # 根据节点类型输出不同事件
                if "rewritten_query" in event and event.get("rewritten_query"):
                    yield json.dumps({
                        "type": "query_rewrite",
                        "rewritten_query": event["rewritten_query"],
                        "seq": seq,
                    }) + "\n"
                    seq += 1

                if "query_intent" in event and event.get("query_intent"):
                    yield json.dumps({
                        "type": "intent",
                        "intent": event["query_intent"],
                        "seq": seq,
                    }) + "\n"
                    seq += 1

                if "retrieval_count" in event:
                    yield json.dumps({
                        "type": "retrieval",
                        "count": event["retrieval_count"],
                        "seq": seq,
                    }) + "\n"
                    seq += 1

                # 跟踪检索结果用于日志
                if "reranked_chunks" in event:
                    last_reranked = event["reranked_chunks"] or []
                if "fallback_reason" in event:
                    last_fallback_reason = event.get("fallback_reason")

                if "response_chunks" in event and event["response_chunks"]:
                    # 流式输出文本
                    for chunk in event["response_chunks"]:
                        collected_response += chunk
                        yield json.dumps({
                            "type": "message.delta",
                            "content": chunk,
                            "seq": seq,
                        }) + "\n"
                        seq += 1

                if "citations" in event:
                    yield json.dumps({
                        "type": "citation",
                        "citations": event["citations"],
                        "seq": seq,
                    }) + "\n"
                    seq += 1

                # 结束事件
                if "response" in event:
                    yield json.dumps({
                        "type": "end",
                        "status": "SUCCESS",
                        "fallback_reason": event.get("fallback_reason"),
                        "seq": seq,
                    }) + "\n"

            # 流结束后持久化对话消息
            if conversation_id:
                await save_message(conversation_id, "user", request.query, request.turn_id)
                await save_message(conversation_id, "assistant", collected_response, request.turn_id)

            # 写入检索日志
            stream_latency = int((time.time() - stream_start) * 1000)
            await log_retrieval_request(
                query=request.query,
                turn_id=request.turn_id,
                conversation_id=conversation_id,
                kb_ids=request.kb_ids or [],
                reranked_results=last_reranked,
                final_chunks=last_reranked,
                latencies={"total": stream_latency},
                fallback_info={
                    "triggered": bool(last_fallback_reason),
                    "reason": last_fallback_reason,
                },
            )

        except Exception as e:
            yield json.dumps({
                "type": "error",
                "code": "WORKFLOW_ERROR",
                "message": str(e),
                "seq": seq,
            }) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "X-Turn-ID": request.turn_id,
            "X-Trace-ID": conversation_id,
        }
    )


# ============== 工作流管理 ==============

@router.get("/workflows")
async def list_workflows():
    """查询工作流列表"""
    return {"workflows": []}


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """获取工作流详情"""
    raise HTTPException(status_code=404, detail="Workflow not found")


# ============== 可观测性 ==============

@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    days: int = Query(default=7, ge=1, le=30, description="查询天数"),
):
    """
    获取检索指标

    返回：
    - 总请求数
    - 平均延迟
    - P95/P99 延迟
    - 平均检索分数
    - Fallback 率
    """
    from app.services.retrieval_logger import get_retrieval_logger

    # 读取日志文件
    logs = await _read_logs(days)

    if not logs:
        return MetricsResponse(
            total_requests=0,
            avg_latency_ms=0.0,
            p95_latency_ms=0.0,
            p99_latency_ms=0.0,
            avg_retrieval_score=0.0,
            fallback_rate=0.0,
        )

    # 计算指标
    total_requests = len(logs)
    latencies = [log.get("total_latency_ms", 0) for log in logs]
    latencies_sorted = sorted(latencies)

    # 平均延迟
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    # P95/P99 延迟
    p95_idx = int(len(latencies_sorted) * 0.95)
    p99_idx = int(len(latencies_sorted) * 0.99)
    p95_latency = latencies_sorted[p95_idx] if latencies_sorted else 0
    p99_latency = latencies_sorted[p99_idx] if latencies_sorted else 0

    # 平均检索分数
    retrieval_scores = [
        log.get("avg_retrieval_score", 0)
        for log in logs
        if log.get("avg_retrieval_score", 0) > 0
    ]
    avg_retrieval_score = (
        sum(retrieval_scores) / len(retrieval_scores)
        if retrieval_scores else 0.0
    )

    # Fallback 率
    fallback_count = sum(
        1 for log in logs
        if log.get("fallback_triggered", False)
    )
    fallback_rate = fallback_count / total_requests if total_requests > 0 else 0.0

    return MetricsResponse(
        total_requests=total_requests,
        avg_latency_ms=avg_latency,
        p95_latency_ms=float(p95_latency),
        p99_latency_ms=float(p99_latency),
        avg_retrieval_score=avg_retrieval_score,
        fallback_rate=fallback_rate,
    )


@router.get("/retrieval-logs")
async def get_retrieval_logs(
    days: int = Query(default=7, ge=1, le=30),
    conversation_id: Optional[str] = Query(None),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """
    查询检索日志

    支持按会话 ID 过滤
    """
    logs = await _read_logs(days)

    # 过滤
    if conversation_id:
        logs = [log for log in logs if log.get("conversation_id") == conversation_id]

    # 按时间排序
    logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return {"logs": logs[:limit]}


@router.get("/health/detailed")
async def detailed_health_check():
    """
    详细健康检查

    检查：
    - Qdrant 连接
    - 模型加载
    - 磁盘空间
    """
    from app.services.qdrant_service import check_qdrant_health

    health_status = {
        "overall": "healthy",
        "checks": {},
    }

    # Qdrant 健康检查
    qdrant_healthy = await check_qdrant_health()
    health_status["checks"]["qdrant"] = "healthy" if qdrant_healthy else "unhealthy"

    # 磁盘空间检查
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        health_status["checks"]["disk"] = {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "status": "healthy" if free > 1024**3 else "warning",
        }
        if free <= 1024**3:
            health_status["overall"] = "warning"
    except Exception as e:
        health_status["checks"]["disk"] = {"status": "unknown", "error": str(e)}

    # 模型加载检查
    try:
        from app.services.embedding_service import get_embedding_model
        get_embedding_model()
        health_status["checks"]["embedding_model"] = "loaded"
    except Exception as e:
        health_status["checks"]["embedding_model"] = {"status": "error", "error": str(e)}

    if not qdrant_healthy:
        health_status["overall"] = "unhealthy"

    return health_status


async def _read_logs(days: int) -> List[Dict[str, Any]]:
    """读取日志文件"""
    from datetime import datetime, timedelta

    logs = []
    logs_dir = "logs"

    if not os.path.exists(logs_dir):
        return logs

    # 计算日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # 读取日志文件
    for filename in os.listdir(logs_dir):
        if not filename.startswith("retrieval_"):
            continue

        # 解析日期
        try:
            date_str = filename.replace("retrieval_", "").replace(".jsonl", "")
            log_date = datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            continue

        # 检查日期范围
        if not (start_date <= log_date <= end_date):
            continue

        # 读取文件
        filepath = os.path.join(logs_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        log = json.loads(line.strip())
                        logs.append(log)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to read log file {filename}: {e}")

    return logs
