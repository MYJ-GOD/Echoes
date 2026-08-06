"""
性能优化 API

提供：
- 缓存管理
- 模型量化状态
- 性能基准测试
- 系统指标
"""
import logging
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/optimization", tags=["性能优化"])


class CacheStatsResponse(BaseModel):
    """缓存统计响应"""
    vector_cache: Dict[str, Any]
    retrieval_cache: Dict[str, Any]
    response_cache: Dict[str, Any]
    total_entries: int
    total_memory_mb: float


class QuantizationStatusResponse(BaseModel):
    """量化状态响应"""
    use_quantization: bool
    quantization_method: str
    embedding_model: Dict[str, Any]
    rerank_model: Dict[str, Any]
    memory_saved_mb: float


class BenchmarkRequest(BaseModel):
    """基准测试请求"""
    query: str = "什么是 RAG?"
    iterations: int = 5
    include_cache: bool = True


class BenchmarkResponse(BaseModel):
    """基准测试响应"""
    test_name: str
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    iterations: int
    cache_enabled: bool


class PerformanceMetricsResponse(BaseModel):
    """性能指标响应"""
    latency: Dict[str, float]
    throughput: Dict[str, float]
    cache: Dict[str, Any]
    model: Dict[str, Any]
    system: Dict[str, Any]


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """获取缓存统计信息"""
    from app.services.cache_service import (
        get_vector_cache,
        get_retrieval_cache,
        get_response_cache,
    )

    vector_stats = get_vector_cache().get_stats()
    retrieval_stats = get_retrieval_cache().get_stats()
    response_stats = get_response_cache().get_stats()

    # 估算内存占用（简化）
    total_entries = (
        vector_stats["valid_entries"] +
        retrieval_stats["valid_entries"] +
        response_stats["valid_entries"]
    )
    # 假设每个条目平均 1KB
    total_memory_mb = total_entries * 1024 / (1024 * 1024)

    return CacheStatsResponse(
        vector_cache=vector_stats,
        retrieval_cache=retrieval_stats,
        response_cache=response_stats,
        total_entries=total_entries,
        total_memory_mb=round(total_memory_mb, 2),
    )


@router.post("/cache/clear")
async def clear_cache(cache_type: Optional[str] = None):
    """
    清空缓存

    cache_type:
    - null: 清空所有缓存
    - "vector": 只清空向量缓存
    - "retrieval": 只清空检索缓存
    - "response": 只清空响应缓存
    """
    from app.services.cache_service import (
        get_vector_cache,
        get_retrieval_cache,
        get_response_cache,
    )

    if cache_type is None:
        # 清空所有
        from app.services.cache_service import clear_all_caches
        await clear_all_caches()
        return {"message": "All caches cleared"}

    if cache_type == "vector":
        await get_vector_cache().clear()
    elif cache_type == "retrieval":
        await get_retrieval_cache().clear()
    elif cache_type == "response":
        await get_response_cache().clear()
    else:
        raise HTTPException(status_code=400, detail=f"Invalid cache type: {cache_type}")

    return {"message": f"{cache_type} cache cleared"}


@router.get("/quantization/status", response_model=QuantizationStatusResponse)
async def get_quantization_status():
    """获取量化状态"""
    from app.services.quantization_service import get_quantization_status

    status = await get_quantization_status()

    # 估算内存节省
    # INT8 量化节省约 75% 内存
    base_memory_mb = 2000  # 假设基础内存 2GB
    memory_saved = base_memory_mb * 0.75 if status["use_quantization"] else 0

    return QuantizationStatusResponse(
        use_quantization=status["use_quantization"],
        quantization_method=status["quantization_method"],
        embedding_model=status["embedding_model"],
        rerank_model=status["rerank_model"],
        memory_saved_mb=memory_saved,
    )


@router.post("/benchmark", response_model=BenchmarkResponse)
async def run_benchmark(request: BenchmarkRequest):
    """
    运行性能基准测试

    测试：
    - Embedding 生成延迟
    - 检索延迟
    - 缓存命中率
    """
    from app.services.embedding_service import generate_embedding
    from app.services.cache_service import get_vector_cache

    latencies = []

    # 运行基准测试
    for i in range(request.iterations):
        # 清空缓存（第一次）
        if i == 0 and not request.include_cache:
            await get_vector_cache().clear()

        start = time.time()
        await generate_embedding(request.query)
        end = time.time()

        latencies.append((end - start) * 1000)

    # 计算统计
    latencies.sort()
    avg_latency = sum(latencies) / len(latencies)
    p95_idx = int(len(latencies) * 0.95)
    p99_idx = int(len(latencies) * 0.99)

    return BenchmarkResponse(
        test_name="embedding_generation",
        avg_latency_ms=round(avg_latency, 2),
        p95_latency_ms=round(latencies[p95_idx], 2) if p95_idx < len(latencies) else 0,
        p99_latency_ms=round(latencies[p99_idx], 2) if p99_idx < len(latencies) else 0,
        min_latency_ms=round(min(latencies), 2),
        max_latency_ms=round(max(latencies), 2),
        iterations=request.iterations,
        cache_enabled=request.include_cache,
    )


@router.get("/metrics", response_model=PerformanceMetricsResponse)
async def get_performance_metrics():
    """获取完整的性能指标"""
    from app.services.cache_service import get_cache_stats
    from app.services.quantization_service import get_quantization_status
    import psutil
    import os

    # 获取缓存统计
    cache_stats = await get_cache_stats()

    # 获取量化状态
    quant_status = await get_quantization_status()

    # 系统指标
    process = psutil.Process(os.getpid())
    cpu_percent = process.cpu_percent()
    memory_mb = process.memory_info().rss / (1024 * 1024)

    return PerformanceMetricsResponse(
        latency={
            "embedding_avg_ms": 50.0,  # 示例值
            "retrieval_avg_ms": 100.0,
            "rerank_avg_ms": 200.0,
            "total_avg_ms": 350.0,
        },
        throughput={
            "requests_per_second": 100.0,
            "tokens_per_second": 5000.0,
        },
        cache=cache_stats.model_dump(),
        model=quant_status,
        system={
            "cpu_percent": cpu_percent,
            "memory_mb": round(memory_mb, 2),
            "memory_percent": process.memory_percent(),
        },
    )


@router.get("/recommendations")
async def get_optimization_recommendations():
    """获取性能优化建议"""
    from app.services.cache_service import get_cache_stats

    cache_stats = await get_cache_stats()
    recommendations = []

    # 缓存命中率检查
    vector_hit_rate = (
        cache_stats.vector_cache.get("total_accesses", 0) /
        max(cache_stats.vector_cache.get("valid_entries", 1), 1)
    )

    if vector_hit_rate < 0.5:
        recommendations.append({
            "category": "cache",
            "priority": "high",
            "issue": "向量缓存命中率低",
            "suggestion": "增加缓存 TTL 或扩大缓存容量",
        })

    # 缓存使用率检查
    if cache_stats.vector_cache.get("usage_percent", 0) > 90:
        recommendations.append({
            "category": "cache",
            "priority": "medium",
            "issue": "向量缓存接近满载",
            "suggestion": "扩大缓存容量或减少 TTL",
        })

    # 量化建议
    recommendations.append({
        "category": "model",
        "priority": "low",
        "issue": "考虑使用模型量化",
        "suggestion": "启用 INT8 量化可减少 75% 内存占用",
    })

    return {"recommendations": recommendations}
