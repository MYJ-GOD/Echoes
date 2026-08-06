"""
Echoes LangGraph Service Configuration
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # Qdrant 配置
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""

    # Echoes-AI 服务地址
    ECHOES_AI_URL: str = "http://localhost:8000"

    # CORS 配置
    CORS_ORIGINS: list[str] = ["*"]

    # 模型配置
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"

    # 日志配置
    LOG_LEVEL: str = "INFO"

    # 向量维度
    VECTOR_SIZE: int = 1024

    # Collections 名称
    COLLECTION_KNOWLEDGE: str = "knowledge_chunks"
    COLLECTION_CONVERSATION: str = "conversation_history"

    # 检索配置
    DEFAULT_TOP_K: int = 5
    DEFAULT_THRESHOLD: float = 0.5

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
