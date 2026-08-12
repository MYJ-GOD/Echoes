"""
API 路由定义（已移除 RAG 端点，仅保留 health check）
"""
import logging
from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "echoes-langgraph",
        "message": "RAG endpoints removed, use /agent/* for agent workflow"
    }
