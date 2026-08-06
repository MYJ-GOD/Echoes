"""
FastAPI 应用主入口

Phase 4 优化：
- 缓存服务集成
- 模型量化支持
- 性能监控 API
- 生产部署配置
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.routes import router as rag_router
from app.api.optimization_routes import router as optimization_router

# 配置日志
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("Starting Echoes LangGraph Service...")

    # 初始化 Qdrant Collections
    from app.services.qdrant_service import init_qdrant_collections
    await init_qdrant_collections()
    logger.info("Qdrant collections initialized")

    # 初始化缓存（预热）
    from app.services.cache_service import get_vector_cache, get_retrieval_cache
    get_vector_cache()
    get_retrieval_cache()
    logger.info("Caches initialized")

    yield

    # 关闭时执行
    logger.info("Shutting down Echoes LangGraph Service...")


app = FastAPI(
    title="Echoes LangGraph Service",
    description="RAG + LangGraph Workflow Service for Echoes",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_request(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    latency_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"{request.method} {request.url.path} - "
        f"status={response.status_code} latency={latency_ms}ms"
    )
    return response


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
        },
    )


# 注册路由
app.include_router(rag_router, prefix="/api/v1")
app.include_router(optimization_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "echoes-langgraph"}


@app.get("/ready", tags=["Health"])
async def ready_check():
    """就绪检查 - 检查依赖服务是否可用"""
    from app.services.qdrant_service import check_qdrant_health
    try:
        is_healthy = await check_qdrant_health()
        if is_healthy:
            return {"status": "ready", "dependencies": {"qdrant": "ok"}}
        else:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "dependencies": {"qdrant": "unhealthy"}},
            )
    except Exception as e:
        logger.error(f"Ready check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "dependencies": {"qdrant": "error"}},
        )
