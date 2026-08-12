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

    # LLM 通道（OpenAI 兼容端点；DeepSeek / DashScope 通用，改 .env 即可切换）
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_API_KEY: str = ""              # 从环境变量 / echoes-langgraph/.env 读
    LLM_MODEL: str = "deepseek-v4-flash"
    LLM_TIMEOUT_SECONDS: int = 60

    # Agent 人格模式（温柔/理性/活泼；Nacos 侧 agent.personality_mode 同步）
    AGENT_PERSONALITY_MODE: str = "温柔"

    # Agent ReAct 循环最大迭代次数（防止无限循环）
    AGENT_MAX_ITERATIONS: int = 3

    # MongoDB 双写配置（备份原始 JSON + 静态画像持久化）
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "echoes"
    MONGODB_COLLECTION_MEMORY: str = "conversation_memory"     # 对话记忆备份
    MONGODB_COLLECTION_STATIC_PROFILE: str = "user_static_profile"  # 静态画像

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
    COLLECTION_PROFILE: str = "user_profile"

    # 检索配置
    DEFAULT_TOP_K: int = 5
    DEFAULT_THRESHOLD: float = 0.5

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
