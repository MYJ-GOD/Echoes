# Echoes RAG + LangGraph 集成方案（优化版）

## 1. 方案概述

### 1.1 目标
在现有对话系统基础上，集成向量数据库和 LangGraph 框架，实现：
- **RAG（检索增强生成）**：基于用户历史对话和外部知识库的智能回答
- **LangGraph 编排**：可视化的 Agent 工作流编排
- **渐进式迁移**：不影响现有对话链路，逐步引入新能力

### 1.2 技术选型

| 组件 | 技术选型 | 理由 |
|------|---------|------|
| **向量数据库** | Qdrant | 开源、支持中文、易部署、性能优秀、HNSW 索引 |
| **Embedding 模型** | BGE-M3 | 中文语义理解优秀、支持长文本 (0-8192 tokens) |
| **LangGraph** | **Python (官方)** | 成熟稳定、生态完善、功能最全 |
| **LLM 接入** | 保持现有 Echoes-AI | 复用已有模型接入层 |
| **Rerank 模型** | BGE-Reranker-v2-m3 | 与 Embedding 同系列，相关性排序更准 |

### 1.3 LangGraph 定位说明

**重要：LangGraph 是给 LLM（大语言模型）用的，与 TTS（语音合成）无关。**

在 Echoes 项目中的分工：

```
用户提问 (文本)
    │
    ▼
┌─────────────────────────────────────────┐
│           LangGraph 工作流               │
│  ┌─────────┐    ┌─────────┐    ┌─────┐ │
│  │ 意图识别 │ →  │ 知识库  │ →  │ LLM │ │
│  │  Node   │    │ 检索     │    │生成  │ │
│  └─────────┘    └─────────┘    └─────┘ │
│                            │            │
│                            ▼            │
│                      ┌─────────┐        │
│                      │ 引用标注 │        │
│                      └─────────┘        │
└─────────────────────────────────────────┘
    │
    ▼
LLM 生成的回答 (文本)
    │
    ▼
送到 TTS 服务 → 语音输出
```

**简单来说**：
- **LangGraph** = 编排 LLM 如何处理用户问题（检索→生成→后处理）
- **TTS** = 把 LLM 生成的文本转成语音
- 两者是独立的：LangGraph 处理完后的文本输出，可以送到 TTS 合成语音，但 LangGraph 本身不负责 TTS

---

### 1.4 架构原则（与现有架构兼容）

Echoes 当前架构已是**规范的 Java+Python LLM+TTS 项目**：

```
┌─────────────────────────────────────────────────────────────┐
│            Java Spring Boot (编排层)                          │
│  - SSE 输出控制                                               │
│  - Turn 管理                                                  │
│  - 幂等性控制                                                 │
│  - seq 单点生成                                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ HTTP (JSON Stream / NDJSON)
            ┌─────────────────────────────────────────┐
            │      Python Echoes-AI (执行层)           │
            │  ┌─────────────────────────────────────┐│
            │  │         LangGraph 工作流             ││  ← 新增
            │  │  guardrail → retrieve → generate    ││
            │  └─────────────────────────────────────┘│
            │              │                          │
            │              ▼                          │
            │  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
            │  │   LLM   │  │   TTS   │  │   ASR   │ │
            │  └─────────┘  └─────────┘  └─────────┘ │
            └─────────────────────────────────────────┘
```

**关键设计决策**：

| 层级 | 职责 | 输出格式 |
|------|------|---------|
| **Python LangGraph** | 工作流编排、检索、生成 | NDJSON (每行一个 JSON 对象) |
| **Java Orchestrator** | SSE 封装、seq 生成、幂等控制 | SSE 标准事件流 |

**引入 LangGraph 后的变化**：
- **Java 层**：从「编排 LLM/TTS 调用」变为「编排 LangGraph 工作流」
- **Python 层**：从「直接调用 LLM/TTS」变为「LangGraph 编排 → LLM/TTS」
- **对外接口**：保持不变，仍是 `POST /conversation/chat-stream`
- **核心原则**：Java 单一出口、SSE 单一入口、turn_id 权威模型不变

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Gateway (Nacos)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────────┐ ┌─────────────────────┐
│  Conversation    │ │   Voice          │ │   RAG Service       │
│  Service         │ │   Service        │ │   (新增)            │
│  (已有)          │ │   (已有)         │ │                     │
│  - Turn 管理      │ │  - 音色训练      │ │  - 向量检索         │
│  - 会话管理      │ │  - 语音合成      │ │  - 知识库管理       │
│  - 消息存储      │ │  - 音频存储      │ │  - LangGraph 编排   │
└──────────────────┘ └──────────────────┘ │  - Embedding 生成   │
                              │           └─────────────────────┘
                              ▼                       │
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer                                  │
├─────────────┬─────────────┬─────────────────┬─────────────────┤
│   MySQL     │   MongoDB   │   Redis         │   Qdrant        │
│   (关系数据) │  (消息内容)  │  (缓存/状态)    │   (向量检索)     │
└─────────────┴─────────────┴─────────────────┴─────────────────┘
```

### 2.2 新增服务模块

#### Java 端：echoes-service-rag

```
echoes-service-rag/
├── src/main/java/com/echoes/rag/
│   ├── RagServiceApplication.java
│   ├── domain/
│   │   ├── knowledge/        # 知识库领域
│   │   │   ├── controller/
│   │   │   ├── service/
│   │   │   ├── repository/
│   │   │   └── entity/
│   │   ├── retrieval/        # 检索领域
│   │   │   ├── controller/
│   │   │   ├── service/
│   │   │   └── engine/       # 检索引擎、Rerank
│   │   └── workflow/         # LangGraph 工作流编排
│   │       ├── controller/
│   │       ├── service/
│   │       └── executor/     # 工作流执行器
│   ├── infrastructure/
│   │   ├── qdrant/           # Qdrant 客户端
│   │   ├── embedding/        # Embedding 服务客户端
│   │   └── langgraph/        # LangGraph 服务 HTTP 客户端
│   └── config/
└── pom.xml
```

#### Python 端：echoes-langgraph

```
echoes-langgraph/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置管理
│   ├── api/
│   │   ├── routes.py        # API 路由
│   │   └── schemas.py       # Pydantic 模型
│   ├── graph/
│   │   ├── workflow.py      # LangGraph 工作流定义
│   │   ├── nodes.py         # 节点实现
│   │   ├── state.py         # 状态定义
│   │   └── edges.py         # 条件边逻辑
│   ├── services/
│   │   ├── qdrant_service.py    # Qdrant 检索
│   │   ├── embedding_service.py # Embedding 生成
│   │   ├── rerank_service.py    # Rerank 排序
│   │   └── llm_service.py       # LLM 调用 (Echoes-AI)
│   ├── models/
│   │   └── guardrail.py     # 安全护栏模型
│   └── utils/
│       └── logger.py
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 3. 数据库设计

### 3.1 MySQL 表结构

```sql
-- 知识库表
CREATE TABLE knowledge_base (
    kb_id BINARY(16) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description VARCHAR(512),
    owner_user_id BINARY(16),
    visibility ENUM('PRIVATE', 'SHARED', 'PUBLIC') DEFAULT 'PRIVATE',
    status ENUM('ACTIVE', 'INDEXING', 'DISABLED') DEFAULT 'ACTIVE',
    config JSON,
    is_deleted TINYINT DEFAULT 0,
    deleted_at DATETIME,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (kb_id),
    INDEX idx_owner (owner_user_id, deleted_at),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 知识文档表
CREATE TABLE knowledge_document (
    doc_id BINARY(16) NOT NULL,
    kb_id BINARY(16) NOT NULL,
    title VARCHAR(512) NOT NULL,
    content_type ENUM('TEXT', 'MARKDOWN', 'PDF', 'URL') DEFAULT 'TEXT',
    source_url VARCHAR(1024),
    storage_key VARCHAR(512),
    word_count INT,
    status ENUM('PENDING', 'PROCESSING', 'READY', 'FAILED') DEFAULT 'PENDING',
    metadata JSON,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (doc_id),
    INDEX idx_kb (kb_id, status)
    -- 注意：去掉外键约束，由应用层保证一致性
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 知识片段表 (Chunk)
CREATE TABLE knowledge_chunk (
    chunk_id VARCHAR(128) NOT NULL,
    doc_id BINARY(16) NOT NULL,
    kb_id BINARY(16) NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding_version VARCHAR(32),
    vector_id VARCHAR(128),  -- Qdrant 中的向量 ID
    metadata JSON,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chunk_id),
    INDEX idx_doc (doc_id, chunk_index),
    INDEX idx_kb (kb_id)
    -- 注意：去掉外键约束，由应用层保证一致性
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 对话历史向量表 (用于语义搜索历史对话)
CREATE TABLE conversation_vector (
    vector_id BINARY(16) NOT NULL,
    conversation_id BINARY(16) NOT NULL,
    turn_id VARCHAR(64),
    content TEXT NOT NULL,
    vector_id_external VARCHAR(128),  -- Qdrant 中的向量 ID
    embedding_model VARCHAR(64),
    message_type ENUM('USER', 'ASSISTANT', 'SYSTEM') DEFAULT 'USER',
    indexed TINYINT DEFAULT 0,  -- 是否已向量化
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (vector_id),
    INDEX idx_conv (conversation_id, create_time),
    INDEX idx_turn (turn_id),
    INDEX idx_indexed (indexed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- LangGraph 工作流定义表
CREATE TABLE langgraph_workflow (
    workflow_id BINARY(16) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description VARCHAR(512),
    owner_user_id BINARY(16),
    graph_definition JSON NOT NULL,  -- 工作流图定义
    nodes_config JSON,
    variables JSON,
    status ENUM('ACTIVE', 'DRAFT', 'DISABLED') DEFAULT 'DRAFT',
    version INT DEFAULT 1,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (workflow_id),
    INDEX idx_owner (owner_user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 工作流执行记录表 (支持幂等性)
CREATE TABLE workflow_execution (
    execution_id BINARY(16) NOT NULL,
    workflow_id BINARY(16) NOT NULL,
    conversation_id BINARY(16),
    turn_id VARCHAR(64) NOT NULL,  -- 用于幂等性
    status ENUM('RUNNING', 'COMPLETED', 'FAILED', 'TIMEOUT') DEFAULT 'RUNNING',
    input_data JSON,
    output_data JSON,
    node_logs JSON,
    error_message VARCHAR(1024),
    start_time DATETIME,
    end_time DATETIME,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (execution_id),
    UNIQUE INDEX idx_turn (turn_id),  -- 幂等性关键索引
    INDEX idx_workflow (workflow_id, create_time),
    INDEX idx_conv (conversation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- RAG 检索日志表 (用于可观测性)
CREATE TABLE rag_retrieval_log (
    log_id BINARY(16) NOT NULL,
    turn_id VARCHAR(64) NOT NULL,
    query_text TEXT NOT NULL,
    rewritten_query TEXT,
    intent_category VARCHAR(64),
    kb_ids JSON,
    retrieved_count INT,
    final_used_count INT,
    rerank_enabled TINYINT DEFAULT 0,
    retrieval_latency_ms INT,
    total_latency_ms INT,
    success TINYINT DEFAULT 1,
    error_message VARCHAR(512),
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (log_id),
    INDEX idx_turn (turn_id),
    INDEX idx_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 3.2 Qdrant Collection 设计

```python
# app/services/qdrant_service.py

from qdrant_client.http import models
from qdrant_client import QdrantClient

# Collections 定义
COLLECTION_KNOWLEDGE = "knowledge_chunks"
COLLECTION_CONVERSATION = "conversation_history"
COLLECTION_USER_PROFILE = "user_profiles"

# 向量维度 (BGE-M3 输出 1024 维)
VECTOR_SIZE = 1024

def create_collections(client: QdrantClient):
    """创建 Qdrant Collections（首次启动时执行）"""

    collections_config = {
        COLLECTION_KNOWLEDGE: {
            "vectors": models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
                hnsw_config=models.HnswConfigDiff(
                    m=16,           # 每个节点的出边数
                    ef_construct=100,  # 构建时的搜索深度
                )
            ),
            "shard_number": 2,      # 分片数（根据数据量调整）
            "replication_factor": 2, # 副本数
            "optimizers_config": models.OptimizersConfigDiff(
                deleted_threshold=0.2,  # 删除阈值
                vacuum_min_vector_number=1000,
            ),
            "payload_index": [
                models.PayloadIndexParams(
                    field_name="kb_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                ),
                models.PayloadIndexParams(
                    field_name="doc_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                ),
            ]
        },

        COLLECTION_CONVERSATION: {
            "vectors": models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                )
            ),
            "shard_number": 1,
            "replication_factor": 1,
            "payload_index": [
                models.PayloadIndexParams(
                    field_name="conversation_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                ),
                models.PayloadIndexParams(
                    field_name="message_type",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                ),
            ]
        }
    }

    for collection_name, config in collections_config.items():
        if not client.collection_exists(collection_name):
            client.create_collection(
                collection_name=collection_name,
                vectors_config=config["vectors"],
                shard_number=config.get("shard_number", 1),
                replication_factor=config.get("replication_factor", 1),
                optimizers_config=config.get("optimizers_config"),
            )

            # 创建 payload 索引
            for idx_config in config.get("payload_index", []):
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=idx_config.field_name,
                    field_schema=idx_config.field_schema,
                )
```

---

## 4. 核心功能设计

### 4.1 RAG 检索流程（优化版）

```
用户提问
    │
    ▼
┌─────────────────┐
│  Guardrail      │  ← 新增：安全护栏
│  - 敏感词过滤   │
│  - 意图合法性   │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Query 理解     │
│  - 意图识别     │
│  - 关键词提取   │
│  - 改写/扩展    │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  向量检索       │
│  - Embedding    │
│  - Qdrant 搜索  │
│  - 混合检索     │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  重排序         │
│  - Rerank 模型  │
│  - 相关性打分   │
└─────────────────┘
    │
    ├─────────────┐
    │             │
    ▼             ▼
┌─────────────┐ ┌─────────────┐
│ 有相关结果   │ │ 无相关结果   │  ← 新增：分支逻辑
│ (走 RAG)    │ │ (降级纯生成) │
└─────────────┘ └─────────────┘
    │             │
    └──────┬──────┘
           ▼
┌─────────────────┐
│  LLM 生成       │
│  - Echoes-AI  │
│  - 流式返回     │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  结果增强       │
│  - 引用标注     │
│  - 溯源链接     │
└─────────────────┘
```

### 4.2 LangGraph 工作流节点（完整版）

```python
# app/graph/nodes.py

from typing import TypedDict, List, Optional, Literal
from pydantic import BaseModel

# ============== 状态定义 ==============

class State(TypedDict, total=False):
    """工作流状态"""
    # 输入
    query: str
    turn_id: str
    conversation_id: str
    kb_ids: List[str]
    top_k: int

    # Guardrail
    guardrail_passed: bool
    guardrail_message: str

    # Query 改写
    rewritten_query: str
    query_intent: str

    # 检索
    retrieved_chunks: List[dict]
    retrieval_count: int

    # Rerank
    reranked_chunks: List[dict]

    # 路由决策
    should_use_rag: bool
    fallback_reason: str

    # 生成
    response: str
    response_chunks: List[str]  # 流式输出用

    # 增强
    citations: List[dict]

    # 元数据
    error: Optional[str]
    latency_ms: int


# ============== Guardrail 节点 ==============

class GuardrailResult(BaseModel):
    passed: bool
    message: str = ""
    block_reason: str = ""

async def guardrail_node(state: State) -> State:
    """
    Guardrail 节点 - 安全护栏
    - 检测敏感/违规内容
    - 拦截恶意查询
    """
    from models.guardrail import check_guardrail

    result: GuardrailResult = await check_guardrail(state["query"])

    if not result.passed:
        return {
            "guardrail_passed": False,
            "guardrail_message": result.message,
            "should_use_rag": False,
            "response": result.message,  # 直接返回提示
        }

    return {"guardrail_passed": True}


# ============== Query 改写节点 ==============

async def query_rewrite_node(state: State) -> State:
    """
    Query 改写节点 - 优化用户查询
    - 拼写纠错
    - 查询扩展
    - 指代消解
    """
    from services.llm_service import rewrite_query

    query = state["query"]
    rewritten = await rewrite_query(query)

    return {
        "rewritten_query": rewritten,
    }


# ============== 意图分类节点 ==============

INTENT_CATEGORIES = Literal["knowledge_query", "chat", "task", "other"]

async def intent_classification_node(state: State) -> State:
    """
    意图分类节点 - 识别用户意图
    - knowledge_query: 知识查询类问题
    - chat: 闲聊
    - task: 任务执行
    - other: 其他
    """
    from services.llm_service import classify_intent

    query = state.get("rewritten_query") or state["query"]
    intent = await classify_intent(query)

    return {
        "query_intent": intent,
    }


# ============== 检索节点 ==============

async def retrieval_node(state: State) -> State:
    """
    检索节点 - 从向量库检索相关内容
    """
    from services.qdrant_service import search_knowledge

    query = state.get("rewritten_query") or state["query"]
    kb_ids = state.get("kb_ids", [])
    top_k = state.get("top_k", 5)

    chunks = await search_knowledge(
        query=query,
        kb_ids=kb_ids,
        top_k=top_k,
        threshold=0.5,  # 最低相似度阈值
    )

    return {
        "retrieved_chunks": chunks,
        "retrieval_count": len(chunks),
    }


# ============== 重排序节点 ==============

async def rerank_node(state: State) -> State:
    """
    重排序节点 - 对检索结果重新排序
    """
    from services.rerank_service import rerank_chunks

    query = state.get("rewritten_query") or state["query"]
    chunks = state.get("retrieved_chunks", [])

    if not chunks:
        return {"reranked_chunks": []}

    reranked = await rerank_chunks(query, chunks, top_k=3)

    return {
        "reranked_chunks": reranked,
    }


# ============== 路由决策函数 ==============

def should_use_rag(state: State) -> Literal["rag_path", "fallback_path"]:
    """
    条件路由 - 决定是否使用 RAG
    """
    # 检索结果为空 → 降级
    if not state.get("reranked_chunks"):
        return "fallback_path"

    # 意图为闲聊 → 不需要 RAG
    if state.get("query_intent") == "chat":
        return "fallback_path"

    # Guardrail 未通过 → 直接返回
    if not state.get("guardrail_passed", True):
        return "fallback_path"

    return "rag_path"


# ============== 回答生成节点 ==============

async def generate_rag_node(state: State) -> State:
    """
    RAG 生成节点 - 基于检索结果生成回答
    """
    from services.llm_service import generate_with_context

    context = state.get("reranked_chunks", [])
    query = state.get("rewritten_query") or state["query"]

    response_chunks = await generate_with_context(
        context=context,
        query=query,
        stream=True,
    )

    return {
        "response_chunks": response_chunks,
    }


async def generate_fallback_node(state: State) -> State:
    """
    降级生成节点 - 纯 LLM 生成（无检索结果时）
    """
    from services.llm_service import generate_plain

    query = state.get("rewritten_query") or state["query"]

    response_chunks = await generate_plain(
        query=query,
        stream=True,
    )

    fallback_reason = state.get("fallback_reason", "no_retrieval_results")

    return {
        "response_chunks": response_chunks,
        "fallback_reason": fallback_reason,
    }


# ============== 引用标注节点 ==============

async def citation_node(state: State) -> State:
    """
    引用标注节点 - 添加引用来源
    """
    from services.llm_service import add_citations

    response = "".join(state.get("response_chunks", []))
    chunks = state.get("reranked_chunks", [])

    if not chunks:
        return {"citations": []}

    citations = await add_citations(response, chunks)

    return {
        "citations": citations,
    }
```

### 4.3 LangGraph 工作流图（完整版）

```python
# app/graph/workflow.py

from langgraph.graph import StateGraph, END
from .nodes import (
    State,
    guardrail_node,
    query_rewrite_node,
    intent_classification_node,
    retrieval_node,
    rerank_node,
    should_use_rag,
    generate_rag_node,
    generate_fallback_node,
    citation_node,
)

def build_rag_workflow() -> StateGraph:
    """构建 RAG 工作流"""

    workflow = StateGraph(State)

    # ============== 添加节点 ==============
    workflow.add_node("guardrail", guardrail_node)
    workflow.add_node("query_rewrite", query_rewrite_node)
    workflow.add_node("intent_classify", intent_classification_node)
    workflow.add_node("retrieve", retrieval_node)
    workflow.add_node("rerank", rerank_node)
    workflow.add_node("generate_rag", generate_rag_node)
    workflow.add_node("generate_fallback", generate_fallback_node)
    workflow.add_node("cite", citation_node)

    # ============== 定义边 ==============
    # 入口 → Guardrail
    workflow.set_entry_point("guardrail")

    # Guardrail → Query Rewrite（无论是否通过都继续，节点内部处理拦截）
    workflow.add_edge("guardrail", "query_rewrite")

    # Query Rewrite → Intent Classify
    workflow.add_edge("query_rewrite", "intent_classify")

    # Intent Classify → Retrieve
    workflow.add_edge("intent_classify", "retrieve")

    # Retrieve → Rerank
    workflow.add_edge("retrieve", "rerank")

    # Rerank → 条件路由
    workflow.add_conditional_edges(
        "rerank",
        should_use_rag,
        {
            "rag_path": "generate_rag",
            "fallback_path": "generate_fallback",
        }
    )

    # 生成 → 引用标注
    workflow.add_edge("generate_rag", "cite")
    workflow.add_edge("generate_fallback", "cite")

    # 引用标注 → 结束
    workflow.add_edge("cite", END)

    return workflow


# 编译工作流
rag_workflow = build_rag_workflow().compile()
```

---

## 5. 接口设计

### 5.1 数据流协议（关键修正）

**Python → Java 数据格式：NDJSON（非 SSE）**

```python
# Python 端输出格式（每行一个 JSON 对象）
{"type": "query_rewrite", "rewritten_query": "...", "seq": 0}
{"type": "intent", "intent": "knowledge_query", "seq": 1}
{"type": "retrieval", "count": 5, "latency_ms": 120, "seq": 2}
{"type": "message.delta", "content": "根据", "seq": 3}
{"type": "message.delta", "content": "知识库", "seq": 4}
{"type": "citation", "citations": [...], "seq": 5}
{"type": "end", "status": "SUCCESS", "usage": {...}, "seq": 6}
```

**Java 端输出格式：SSE 标准事件**

```
event: message
data: {"type": "message.delta", "content": "根据", "seq": 3}

event: message
data: {"type": "message.delta", "content": "知识库", "seq": 4}

event: citation
data: {"type": "citation", "citations": [...], "seq": 5}

event: end
data: {"type": "end", "status": "SUCCESS", "seq": 6}
```

### 5.2 知识库管理 API

```yaml
POST /api/rag/knowledge-bases
  创建知识库
  Request:
    name: string
    description: string
    visibility: PRIVATE|SHARED|PUBLIC
    config: object

GET /api/rag/knowledge-bases
  查询知识库列表

GET /api/rag/knowledge-bases/{kbId}
  获取知识库详情

PUT /api/rag/knowledge-bases/{kbId}
  更新知识库

DELETE /api/rag/knowledge-bases/{kbId}
  删除知识库

POST /api/rag/knowledge-bases/{kbId}/documents
  上传文档到知识库
  Request: multipart/form-data
    file: file
    title: string
    contentType: TEXT|MARKDOWN|PDF|URL

GET /api/rag/knowledge-bases/{kbId}/documents
  查询文档列表

DELETE /api/rag/knowledge-bases/{kbId}/documents/{docId}
  删除文档

GET /api/rag/knowledge-bases/{kbId}/documents/{docId}/chunks
  查询文档片段列表

POST /api/rag/knowledge-bases/{kbId}/documents/{docId}/reindex
  重新索引文档
```

### 5.3 RAG 对话 API（核心）

```yaml
POST /conversation/chat-stream
  RAG 对话 (流式) - 与现有接口统一
  Headers:
    X-USER-ID: string (required)
    X-TRACE-ID: string
    X-TURN-ID: string (required, 幂等性关键)
    X-CONVERSATION-ID: string

  Request:
    conversationId: string
    turnId: string  # 与 header 一致，用于幂等
    message: string
    kbIds: string[] (optional, 不传则搜索全部)
    topK: number (default: 5)
    forceNewTurn: boolean (default: false)

  Response: SSE Stream
    event: message
    data: {"type": "message.delta", "content": "...", "seq": 1}

    event: message
    data: {"type": "message.final", "content": "...", "seq": 2}

    event: citation
    data: {"type": "citation", "data": {...}, "seq": 3}

    event: end
    data: {
      "type": "end",
      "status": "SUCCESS|FAILED|CANCELLED",
      "usage": { "input_tokens": 0, "output_tokens": 0 },
      "latency_ms": 0,
      "rag_info": {
        "retrieval_count": 5,
        "rerank_enabled": true,
        "fallback_reason": null
      }
    }
```

### 5.4 LangGraph 工作流 API

```yaml
GET /api/rag/workflows
  查询工作流列表

POST /api/rag/workflows
  创建工作流
  Request:
    name: string
    description: string
    graphDefinition: object
    nodesConfig: object

GET /api/rag/workflows/{workflowId}
  获取工作流详情

PUT /api/rag/workflows/{workflowId}
  更新工作流

POST /api/rag/workflows/{workflowId}/execute
  执行工作流 (非流式)
  Request:
    query: string
    context: object
  Response: object

GET /api/rag/workflows/{workflowId}/executions
  查询工作流执行记录
```

---

## 6. Python LangGraph 服务实现

### 6.1 FastAPI 入口

```python
# app/main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as rag_router
from config import settings
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Echoes LangGraph Service",
    description="RAG + LangGraph Workflow Service for Echoes",
    version="1.0.0",
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
    import time
    start_time = time.time()
    response = await call_next(request)
    latency_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"{request.method} {request.url.path} - "
        f"status={response.status_code} latency={latency_ms}ms"
    )
    return response

app.include_router(rag_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "echoes-langgraph"}

@app.get("/ready")
def ready_check():
    # 检查依赖服务是否可用
    return {"status": "ready"}
```

### 6.2 API 路由实现

```python
# app/api/routes.py

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, AsyncGenerator
import json
import time

from graph.workflow import rag_workflow
from services.qdrant_service import search_knowledge
from services.embedding_service import generate_embedding

router = APIRouter()

# ============== 请求/响应模型 ==============

class RAGRequest(BaseModel):
    query: str
    turn_id: str
    conversation_id: str
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

# ============== 健康检查 ==============

@router.get("/health")
def health_check():
    return {"status": "healthy"}

# ============== 向量检索 ==============

@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """向量检索 API（非流式）"""
    start_time = time.time()

    try:
        results = await search_knowledge(
            query=request.query,
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

# ============== RAG 对话（核心） ==============

@router.post("/rag/chat")
async def chat(request: RAGRequest) -> RAGResponse:
    """RAG 对话（非流式）"""
    start_time = time.time()

    try:
        # 执行工作流
        result = await rag_workflow.ainvoke({
            "query": request.query,
            "turn_id": request.turn_id,
            "conversation_id": request.conversation_id,
            "kb_ids": request.kb_ids or [],
            "top_k": request.top_k,
        })

        latency_ms = int((time.time() - start_time) * 1000)

        # 组装响应
        response_text = "".join(result.get("response_chunks", []))

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
    seq = 0

    async def generate() -> AsyncGenerator[str, None]:
        nonlocal seq

        try:
            # 使用 astream 流式执行
            async for event in rag_workflow.astream(
                {
                    "query": request.query,
                    "turn_id": request.turn_id,
                    "conversation_id": request.conversation_id,
                    "kb_ids": request.kb_ids or [],
                    "top_k": request.top_k,
                },
                stream_mode="values",  # 输出状态变化
            ):
                # 根据节点类型输出不同事件
                if "rewritten_query" in event and event["rewritten_query"]:
                    yield json.dumps({
                        "type": "query_rewrite",
                        "rewritten_query": event["rewritten_query"],
                        "seq": seq,
                    }) + "\n"
                    seq += 1

                if "query_intent" in event and event["query_intent"]:
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

                if "response_chunks" in event and event["response_chunks"]:
                    # 流式输出文本
                    for chunk in event["response_chunks"]:
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
                if "response" in event and "end" not in str(event):
                    yield json.dumps({
                        "type": "end",
                        "status": "SUCCESS",
                        "fallback_reason": event.get("fallback_reason"),
                        "seq": seq,
                    }) + "\n"

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
            "X-Trace-ID": request.conversation_id,
        }
    )

# ============== 工作流管理 ==============

@router.get("/workflows")
async def list_workflows():
    """查询工作流列表"""
    return {"workflows": []}

@router.post("/workflows")
async def create_workflow():
    """创建工作流"""
    # TODO: 实现
    return {"status": "ok"}
```

### 6.3 服务层实现

```python
# app/services/qdrant_service.py

from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http import models
from app.config import settings
from typing import List, Optional, Dict, Any
import numpy as np

# 初始化客户端
qdrant_client: Optional[QdrantClient] = None
qdrant_async_client: Optional[AsyncQdrantClient] = None

def get_client() -> QdrantClient:
    global qdrant_client
    if qdrant_client is None:
        qdrant_client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )
    return qdrant_client

def get_async_client() -> AsyncQdrantClient:
    global qdrant_async_client
    if qdrant_async_client is None:
        qdrant_async_client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )
    return qdrant_async_client

async def search_knowledge(
    query: str,
    query_vector: List[float],
    kb_ids: Optional[List[str]] = None,
    top_k: int = 5,
    threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    检索知识库

    Args:
        query: 原始查询文本
        query_vector: 查询向量
        kb_ids: 知识库 ID 列表（None 表示搜索全部）
        top_k: 返回数量
        threshold: 最低相似度阈值

    Returns:
        检索结果列表
    """
    client = get_async_client()

    # 构建过滤条件
    must_conditions = []
    if kb_ids:
        must_conditions.append(
            models.FieldCondition(
                key="kb_id",
                match=models.MatchAny(any=kb_ids),
            )
        )

    results = await client.search(
        collection_name="knowledge_chunks",
        query_vector=query_vector,
        query_filter=models.Filter(must=must_conditions) if must_conditions else None,
        limit=top_k,
        score_threshold=threshold,
        with_payload=True,
    )

    return [
        {
            "chunk_id": hit.payload.get("chunk_id"),
            "doc_id": hit.payload.get("doc_id"),
            "kb_id": hit.payload.get("kb_id"),
            "content": hit.payload.get("content"),
            "score": hit.score,
            "document": {
                "title": hit.payload.get("title"),
                "source_url": hit.payload.get("source_url"),
            },
        }
        for hit in results
    ]

async def upsert_chunks(
    chunks: List[Dict[str, Any]],
    vectors: List[List[float]],
):
    """
    向量化存储文档片段

    Args:
        chunks: 文档片段列表
        vectors: 对应的向量列表
    """
    client = get_async_client()

    points = [
        models.PointStruct(
            id=i,
            vector=vector,
            payload={
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "kb_id": chunk["kb_id"],
                "content": chunk["content"],
                "chunk_index": chunk["chunk_index"],
                "metadata": chunk.get("metadata", {}),
            },
        )
        for i, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]

    await client.upsert(
        collection_name="knowledge_chunks",
        points=points,
    )
```

```python
# app/services/embedding_service.py

from typing import List
from sentence_transformers import SentenceTransformer
import numpy as np

# 全局模型实例（避免重复加载）
_model: SentenceTransformer = None

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer('BAAI/bge-m3')
    return _model

async def generate_embedding(text: str) -> List[float]:
    """
    生成文本向量

    Args:
        text: 输入文本

    Returns:
        1024 维向量
    """
    model = get_embedding_model()
    embedding = model.encode(
        text,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embedding.tolist()

async def generate_embeddings_batch(
    texts: List[str],
    batch_size: int = 32,
) -> List[List[float]]:
    """批量生成向量"""
    model = get_embedding_model()
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=batch_size,
        show_progress_bar=True,
    )
    return embeddings.tolist()
```

```python
# app/services/rerank_service.py

from typing import List, Dict, Any
from sentence_transformers import CrossEncoder
import numpy as np

# 全局 Rerank 模型
_rerank_model: CrossEncoder = None

def get_rerank_model() -> CrossEncoder:
    global _rerank_model
    if _rerank_model is None:
        _rerank_model = CrossEncoder('BAAI/bge-reranker-v2-m3')
    return _rerank_model

async def rerank_chunks(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    对检索结果重排序

    Args:
        query: 查询文本
        chunks: 检索结果列表
        top_k: 返回前 N 个

    Returns:
        重排序后的结果
    """
    if not chunks:
        return []

    model = get_rerank_model()

    # 构建 (query, passage) 对
    pairs = [(query, chunk["content"]) for chunk in chunks]

    # 计算相关性分数
    scores = model.predict(pairs)

    # 附加分数到 chunk
    for i, chunk in enumerate(chunks):
        chunk["rerank_score"] = float(scores[i])

    # 按 rerank_score 排序
    sorted_chunks = sorted(
        chunks,
        key=lambda x: x["rerank_score"],
        reverse=True,
    )

    return sorted_chunks[:top_k]
```

```python
# app/services/llm_service.py

from typing import List, Dict, Any, AsyncGenerator
import httpx
from app.config import settings

# Echoes-AI 服务地址
ECHOES_AI_URL = settings.ECHOES_AI_URL

async def rewrite_query(query: str) -> str:
    """
    Query 改写
    - 拼写纠错
    - 指代消解
    - 查询扩展
    """
    # 调用 Echoes-AI 服务
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ECHOES_AI_URL}/api/rewrite",
            json={"query": query},
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()["rewritten_query"]

async def classify_intent(query: str) -> str:
    """
    意图分类
    返回：knowledge_query | chat | task | other
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ECHOES_AI_URL}/api/classify",
            json={"query": query},
            timeout=5.0,
        )
        response.raise_for_status()
        return response.json()["intent"]

async def generate_with_context(
    context: List[Dict[str, Any]],
    query: str,
    stream: bool = True,
) -> List[str]:
    """
    基于上下文生成回答

    Returns:
        文本块列表（流式模式下为生成顺序的 chunk）
    """
    # 构建 RAG Prompt
    context_text = "\n\n".join([
        f"[{i+1}] {chunk['content']}"
        for i, chunk in enumerate(context)
    ])

    prompt = f"""基于以下知识库内容回答问题。如果知识库内容与问题无关，请说明你不知道。

知识库内容：
{context_text}

问题：{query}

回答："""

    async with httpx.AsyncClient(timeout=60.0) as client:
        if stream:
            # 流式调用
            async with client.stream(
                "POST",
                f"{ECHOES_AI_URL}/api/generate",
                json={"prompt": prompt, "stream": True},
            ) as response:
                response.raise_for_status()
                chunks = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        import json
                        chunk_data = json.loads(data)
                        if "content" in chunk_data:
                            chunks.append(chunk_data["content"])
                return chunks
        else:
            response = await client.post(
                f"{ECHOES_AI_URL}/api/generate",
                json={"prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            return [response.json()["text"]]

async def generate_plain(query: str, stream: bool = True) -> List[str]:
    """
    纯 LLM 生成（无检索结果时的降级）
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        if stream:
            async with client.stream(
                "POST",
                f"{ECHOES_AI_URL}/api/generate",
                json={"prompt": query, "stream": True},
            ) as response:
                response.raise_for_status()
                chunks = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        import json
                        chunk_data = json.loads(data)
                        if "content" in chunk_data:
                            chunks.append(chunk_data["content"])
                return chunks
        else:
            response = await client.post(
                f"{ECHOES_AI_URL}/api/generate",
                json={"prompt": query, "stream": False},
            )
            response.raise_for_status()
            return [response.json()["text"]]

async def add_citations(
    response: str,
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    添加引用标注
    """
    citations = []
    for i, chunk in enumerate(chunks):
        citations.append({
            "index": i + 1,
            "document": chunk.get("document", {}),
            "chunk_id": chunk["chunk_id"],
            "score": chunk.get("rerank_score", chunk.get("score", 0)),
        })
    return citations
```

---

## 7. Java 端集成实现

### 7.1 HTTP 客户端配置

```java
// echoes-service-rag/src/main/java/com/echoes/rag/infrastructure/langgraph/LangGraphClient.java

package com.echoes.rag.infrastructure.langgraph;

import com.echoes.rag.config.RagProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class LangGraphClient {

    private final WebClient.Builder webClientBuilder;
    private final RagProperties ragProperties;
    private final ObjectMapper objectMapper;

    /**
     * 流式调用 LangGraph 工作流
     * 返回 NDJSON 格式的 Flux
     */
    public Flux<JsonNode> streamWorkflow(RagWorkflowRequest request) {
        return webClientBuilder.build()
            .post()
            .uri(ragProperties.getLanggraphUrl() + "/api/v1/rag/chat/stream")
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(request)
            .retrieve()
            .bodyToFlux(String.class)
            .map(this::parseNdjsonLine)
            .doOnError(error -> log.error("LangGraph stream error", error));
    }

    /**
     * 非流式调用
     */
    public Mono<RagWorkflowResponse> executeWorkflow(RagWorkflowRequest request) {
        return webClientBuilder.build()
            .post()
            .uri(ragProperties.getLanggraphUrl() + "/api/v1/rag/chat")
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(request)
            .retrieve()
            .bodyToMono(RagWorkflowResponse.class);
    }

    private JsonNode parseNdjsonLine(String line) {
        try {
            return objectMapper.readTree(line);
        } catch (Exception e) {
            log.warn("Failed to parse NDJSON line: {}", line, e);
            return null;
        }
    }
}
```

### 7.2 SSE 封装器

```java
// echoes-service-rag/src/main/java/com/echoes/rag/infrastructure/langgraph/SseEnvelope.java

package com.echoes.rag.infrastructure.langgraph;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Builder;
import lombok.Data;

/**
 * SSE 事件封装
 * Java 端负责将 Python 的 NDJSON 转为标准 SSE 事件
 */
@Data
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class SseEnvelope {
    private String type;
    private String content;
    private Integer seq;
    private String status;
    private Object data;
    private Usage usage;
    private RagInfo ragInfo;

    @Data
    @Builder
    public static class Usage {
        private Integer inputTokens;
        private Integer outputTokens;
    }

    @Data
    @Builder
    public static class RagInfo {
        private Integer retrievalCount;
        private Boolean rerankEnabled;
        private String fallbackReason;
    }
}
```

```java
// echoes-service-rag/src/main/java/com/echoes/rag/service/RagStreamService.java

package com.echoes.rag.service;

import com.echoes.rag.infrastructure.langgraph.LangGraphClient;
import com.echoes.rag.infrastructure.langgraph.RagWorkflowRequest;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.concurrent.atomic.AtomicLong;

@Slf4j
@Service
@RequiredArgsConstructor
public class RagStreamService {

    private final LangGraphClient langGraphClient;
    private final ObjectMapper objectMapper;
    private final SeqGenerator seqGenerator;

    /**
     * 流式对话 - 封装 SSE 事件
     */
    public SseEmitter streamConversation(RagWorkflowRequest request, String userId) {
        SseEmitter emitter = new SseEmitter(120_000L); // 2 分钟超时
        AtomicLong seq = new AtomicLong(0);

        // 监听 LangGraph 流
        langGraphClient.streamWorkflow(request)
            .doOnSubscribe(subscription -> log.info("Start streaming for turnId={}", request.getTurnId()))
            .doOnComplete(() -> {
                try {
                    sendSseEvent(emitter, "end", createEndEvent(seq.get()), seq.getAndIncrement());
                    emitter.complete();
                    log.info("Stream completed for turnId={}", request.getTurnId());
                } catch (IOException e) {
                    log.error("Failed to send end event", e);
                }
            })
            .doOnError(error -> {
                try {
                    sendSseEvent(emitter, "error", createErrorEvent(error), seq.get());
                    emitter.completeWithError(error);
                    log.error("Stream error for turnId={}", request.getTurnId(), error);
                } catch (IOException e) {
                    log.error("Failed to send error event", e);
                }
            })
            .subscribe(node -> {
                try {
                    handleWorkflowEvent(emitter, node, seq);
                } catch (IOException e) {
                    log.error("Failed to handle event", e);
                }
            });

        // 监听客户端断开
        emitter.onTimeout(() -> {
            log.info("SSE timeout for turnId={}", request.getTurnId());
            emitter.complete();
        });
        emitter.onCompletion(() -> log.info("SSE completed for turnId={}", request.getTurnId()));
        emitter.onErrorCompletion(ex -> log.error("SSE error for turnId={}", request.getTurnId(), ex));

        return emitter;
    }

    private void handleWorkflowEvent(SseEmitter emitter, JsonNode node, AtomicLong seq) throws IOException {
        String type = node.has("type") ? node.get("type").asText() : "unknown";

        switch (type) {
            case "message.delta" -> sendSseEvent(emitter, "message", node, seq.getAndIncrement());
            case "citation" -> sendSseEvent(emitter, "citation", node, seq.getAndIncrement());
            case "end" -> {
                sendSseEvent(emitter, "end", createEndEvent(node, seq.get()), seq.getAndIncrement());
                emitter.complete();
            }
            case "error" -> {
                sendSseEvent(emitter, "error", node, seq.get());
                emitter.completeWithError(new RuntimeException(node.get("message").asText()));
            }
            case "query_rewrite", "intent", "retrieval" -> {
                // 可选：透传中间事件给前端（用于 loading 状态展示）
                sendSseEvent(emitter, type, node, seq.getAndIncrement());
            }
            default -> log.warn("Unknown event type: {}", type);
        }
    }

    private void sendSseEvent(SseEmitter emitter, String eventName, Object data, long seq) throws IOException {
        SseEmitter.SseEventBuilder event = SseEmitter.event()
            .name(eventName)
            .data(data)
            .id(String.valueOf(seq));
        emitter.send(event);
    }

    private JsonNode createEndEvent(long seq) {
        return objectMapper.createObjectNode()
            .put("type", "end")
            .put("status", "SUCCESS")
            .put("seq", seq);
    }

    private JsonNode createEndEvent(JsonNode node, long seq) {
        return objectMapper.createObjectNode()
            .put("type", "end")
            .put("status", node.has("status") ? node.get("status").asText() : "SUCCESS")
            .put("fallback_reason", node.has("fallback_reason") ? node.get("fallback_reason").asText(null))
            .put("seq", seq);
    }

    private JsonNode createErrorEvent(Throwable error) {
        return objectMapper.createObjectNode()
            .put("type", "error")
            .put("code", "WORKFLOW_ERROR")
            .put("message", error.getMessage())
            .put("retryable", true);
    }
}
```

### 7.3 Controller 实现

```java
// echoes-service-rag/src/main/java/com/echoes/rag/controller/RagController.java

package com.echoes.rag.controller;

import com.echoes.rag.infrastructure.langgraph.RagWorkflowRequest;
import com.echoes.rag.service.RagStreamService;
import com.echoes.rag.service.TurnService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/conversation")
@RequiredArgsConstructor
public class RagController {

    private final RagStreamService ragStreamService;
    private final TurnService turnService;

    /**
     * RAG 对话流式接口
     * 与现有 /conversation/chat-stream 统一
     */
    @PostMapping(value = "/chat-stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chatStream(
        @RequestHeader("X-USER-ID") String userId,
        @RequestHeader("X-TURN-ID") String turnId,
        @RequestHeader(value = "X-TRACE-ID", required = false) String traceId,
        @RequestHeader(value = "X-CONVERSATION-ID", required = false) String conversationId,
        @RequestBody Map<String, Object> requestBody
    ) {
        // 幂等性检查
        if (turnService.isTurnCompleted(conversationId, turnId)) {
            log.info("Replay completed turn: conversationId={}, turnId={}", conversationId, turnId);
            return turnService.replayTurn(conversationId, turnId, userId);
        }

        // 构建 RAG 请求
        RagWorkflowRequest request = RagWorkflowRequest.builder()
            .query((String) requestBody.get("message"))
            .turnId(turnId)
            .conversationId(conversationId)
            .kbIds((java.util.List<String>) requestBody.get("kbIds"))
            .topK(requestBody.get("topK") != null ?
                   Integer.parseInt(requestBody.get("topK").toString()) : 5)
            .build();

        // 记录 Turn 开始
        turnService.startTurn(conversationId, turnId, userId, request);

        // 流式对话
        return ragStreamService.streamConversation(request, userId);
    }
}
```

---

## 8. 实施计划

### Phase 0: 基础框架搭建 (Week 1-2)

**目标**: 完成 Python LangGraph 服务基础框架和 Qdrant 部署

| 任务 | 详细说明 | 交付物 | 优先级 |
|------|---------|--------|--------|
| **0.1** 部署 Qdrant | Docker 部署，配置 HNSW 索引、分片策略 | `docker-compose.rag.yml` | P0 |
| **0.2** 创建 Python 项目 | 初始化 echoes-langgraph 项目结构 | 项目骨架 | P0 |
| **0.3** 集成 Embedding | BGE-M3 模型集成，实现向量生成服务 | `embedding_service.py` | P0 |
| **0.4** Qdrant 客户端 | 实现 Collections 创建、索引管理 | `qdrant_service.py` | P0 |
| **0.5** 创建 Java 项目 | 初始化 echoes-service-rag 模块 | 项目骨架 | P0 |
| **0.6** 健康检查 | 实现 /health 和 /ready 端点 | 可运行的服务 | P0 |

**验收标准**:
- [ ] Qdrant 成功部署并可访问
- [ ] Python 服务可生成向量并存储到 Qdrant
- [ ] Java 项目可编译通过

---

### Phase 1: 知识库管理 (Week 3-4)

**目标**: 实现知识库 CRUD 和文档向量化

| 任务 | 详细说明 | 交付物 | 优先级 |
|------|---------|--------|--------|
| **1.1** MySQL 表结构 | 执行 SQL 创建知识相关表 | 数据库表 | P0 |
| **1.2** 知识库 CRUD | Java 端实现知识库增删改查 API | `KnowledgeBaseController` | P0 |
| **1.3** 文档上传 | 实现文档上传、解析、存储 | `DocumentController` | P0 |
| **1.4** 文档分块 | 实现 Chunking 策略（按段落/字符） | `ChunkingStrategy.java` | P0 |
| **1.5** 向量索引 | Python 端实现文档向量化并存入 Qdrant | `index_document.py` | P0 |
| **1.6** 索引状态管理 | 实现文档索引状态追踪 | `Document.status` | P1 |

**验收标准**:
- [ ] 可创建/删除知识库
- [ ] 可上传文档并自动向量化
- [ ] Qdrant 中可查询到向量

---

### Phase 2: RAG 检索核心 (Week 5-6)

**目标**: 实现向量检索和 Rerank 能力

| 任务 | 详细说明 | 交付物 | 优先级 |
|------|---------|--------|--------|
| **2.1** 向量检索 API | Python 端实现 `/search` 接口 | `search_knowledge()` | P0 |
| **2.2** 混合检索 | 支持向量 + 关键词混合检索 | 混合检索引擎 | P1 |
| **2.3** Rerank 集成 | BGE-Reranker 集成，实现重排序 | `rerank_service.py` | P0 |
| **2.4** 检索 Java 封装 | Java 端调用 Python 检索服务 | `RagSearchService` | P0 |
| **2.5** 检索日志 | 实现 `rag_retrieval_log` 记录 | 可观测性 | P1 |
| **2.6** 检索测试 | 准确率测试，阈值调优 | 测试报告 | P1 |

**验收标准**:
- [ ] 检索 P95 延迟 < 200ms
- [ ] 检索结果相关性 >= 85%
- [ ] Rerank 可正确排序

---

### Phase 3: LangGraph 工作流 (Week 7-8)

**目标**: 实现完整的工作流编排

| 任务 | 详细说明 | 交付物 | 优先级 |
|------|---------|--------|--------|
| **3.1** 状态定义 | 实现 `State` TypedDict | `state.py` | P0 |
| **3.2** Guardrail 节点 | 实现安全护栏节点 | `guardrail_node()` | P0 |
| **3.3** Query 改写节点 | 实现查询改写 | `query_rewrite_node()` | P0 |
| **3.4** 意图分类节点 | 实现意图识别 | `intent_classification_node()` | P0 |
| **3.5** 检索节点 | 集成 Phase 2 的检索能力 | `retrieval_node()` | P0 |
| **3.6** 条件路由 | 实现 `should_use_rag()` 分支逻辑 | `edges.py` | P0 |
| **3.7** 生成节点 | RAG 生成和降级生成 | `generate_*.py` | P0 |
| **3.8** 引用标注 | 实现引用来源标注 | `citation_node()` | P1 |
| **3.9** 工作流编译 | 完整工作流编译测试 | `workflow.compile()` | P0 |

**验收标准**:
- [ ] 工作流可完整执行
- [ ] 检索为空时正确降级
- [ ] Guardrail 可拦截违规查询

---

### Phase 4: Java 集成 (Week 9-10)

**目标**: Java 端集成 LangGraph 调用，完成 SSE 封装

| 任务 | 详细说明 | 交付物 | 优先级 |
|------|---------|--------|--------|
| **4.1** HTTP 客户端 | WebClient 配置，调用 Python 服务 | `LangGraphClient.java` | P0 |
| **4.2** NDJSON 解析 | 解析 Python 返回的 NDJSON 流 | Flux 处理器 | P0 |
| **4.3** SSE 封装 | 将 NDJSON 转为标准 SSE 事件 | `RagStreamService` | P0 |
| **4.4** seq 生成器 | Java 单点生成 seq | `SeqGenerator` | P0 |
| **4.5** 幂等性实现 | `workflow_execution` 唯一索引，Turn 重放 | `TurnService` | P0 |
| **4.6** 控制器集成 | 对接现有 `/conversation/chat-stream` | `RagController` | P0 |
| **4.7** 端到端测试 | 完整链路测试 | 测试用例 | P0 |

**验收标准**:
- [ ] SSE 事件格式符合架构文档
- [ ] 同 `turn_id` 请求可正确重放
- [ ] 前端可正常接收流式消息

---

### Phase 5: 对话历史向量化 (Week 11-12)

**目标**: 实现历史对话语义检索

| 任务 | 详细说明 | 交付物 | 优先级 |
|------|---------|--------|--------|
| **5.1** 向量化触发 | Turn 完成后异步触发向量化 | `@Async` 任务 | P0 |
| **5.2** 历史检索 | 支持按 conversation_id 检索历史 | 历史检索 API | P0 |
| **5.3** 用户画像 | (可选) 构建用户画像向量 | `user_profiles` | P2 |
| **5.4** 长期记忆 | 管理长期记忆的存储和检索 | 记忆管理 | P1 |
| **5.5** 性能优化 | 批量向量化、缓存策略 | 优化方案 | P1 |
| **5.6** 压力测试 | 100+ 并发检索测试 | 测试报告 | P0 |
| **5.7** 文档完善 | API 文档、运维文档 | 文档 | P0 |

**验收标准**:
- [ ] 历史对话可语义检索
- [ ] 支持 100+ 并发
- [ ] 文档完整

---

## 9. 技术依赖

### 9.1 Java 端 (echoes-service-rag/pom.xml)

```xml
<dependencies>
    <!-- Spring Boot -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>

    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-webflux</artifactId>
    </dependency>

    <!-- Qdrant Client (可选，Java 端直接访问时使用) -->
    <dependency>
        <groupId>io.qdrant</groupId>
        <artifactId>client</artifactId>
        <version>1.9.0</version>
    </dependency>

    <!-- MyBatis Plus -->
    <dependency>
        <groupId>com.baomidou</groupId>
        <artifactId>mybatis-plus-spring-boot3-starter</artifactId>
        <version>3.5.5</version>
    </dependency>

    <!-- Nacos Discovery -->
    <dependency>
        <groupId>com.alibaba.cloud</groupId>
        <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
    </dependency>

    <!-- OpenFeign (可选) -->
    <dependency>
        <groupId>org.springframework.cloud</groupId>
        <artifactId>spring-cloud-starter-openfeign</artifactId>
    </dependency>

    <!-- Lombok -->
    <dependency>
        <groupId>org.projectlombok</groupId>
        <artifactId>lombok</artifactId>
        <optional>true</optional>
    </dependency>

    <!-- Test -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-test</artifactId>
        <scope>test</scope>
    </dependency>
</dependencies>
```

### 9.2 Python 端 (echoes-langgraph/requirements.txt)

```txt
# LangGraph & LangChain
langgraph>=0.2.0
langchain>=0.3.0
langchain-community>=0.3.0

# Embedding & Rerank
sentence-transformers>=2.7.0  # BGE-M3 和 Reranker

# FastAPI
fastapi>=0.109.0
uvicorn>=0.27.0
python-multipart>=0.0.6

# Qdrant Client
qdrant-client>=1.7.0

# HTTP Client
httpx>=0.27.0

# 工具库
pydantic>=2.0.0
python-dotenv>=1.0.0
numpy>=1.24.0

# 日志
structlog>=24.0.0

# 测试
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

---

## 10. 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| Embedding 效果不佳 | 检索准确率低 | 中 | 多模型对比，支持热切换；添加 Rerank |
| Qdrant 性能瓶颈 | 检索延迟高 | 低 | HNSW 索引，分片策略，结果缓存 |
| SSE 链路不稳定 | 流式中断 | 中 | Java 端重试，断线续传机制 |
| LangGraph 学习曲线 | 开发效率低 | 中 | 提前培训，参考官方示例 |
| 向量数据一致性 | 检索结果不完整 | 中 | 异步索引 + 补偿任务 |
| Python 服务故障 | 链路中断 | 低 | 降级到纯 LLM，熔断机制 |

---

## 11. 验收标准

### 11.1 功能验收

- [ ] 知识库 CRUD 功能完整
- [ ] 文档上传/解析/索引正常
- [ ] 向量检索准确率 >= 85%
- [ ] RAG 对话返回引用来源
- [ ] LangGraph 工作流可执行
- [ ] 检索为空时正确降级
- [ ] Guardrail 可拦截违规查询

### 11.2 性能验收

- [ ] 检索 P95 延迟 < 200ms
- [ ] 单文档索引时间 < 5s/千字
- [ ] 支持 100+ 并发检索
- [ ] 向量库支持 1000 万 + 向量
- [ ] 首包时延 P95 < 2000ms

### 11.3 质量验收

- [ ] 单元测试覆盖率 >= 80%
- [ ] 接口文档完整 (Swagger/OpenAPI)
- [ ] 运维文档完善 (部署、监控、告警)
- [ ] 通过安全扫描
- [ ] 代码审查通过

---

## 12. 附录

### 12.1 Docker Compose 配置

```yaml
# docker-compose.rag.yml
version: '3.8'

services:
  # Qdrant 向量数据库
  qdrant:
    image: qdrant/qdrant:latest
    container_name: echoes-qdrant
    ports:
      - "6333:6333"  # REST API
      - "6334:6334"  # gRPC
    volumes:
      - ./qdrant_storage:/qdrant/storage
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334
    restart: unless-stopped
    networks:
      - echoes-network

  # Python LangGraph 服务
  langgraph-service:
    build:
      context: ../echoes-langgraph
      dockerfile: Dockerfile
    container_name: echoes-langgraph
    ports:
      - "8088:8088"
    environment:
      - QDRANT_URL=http://qdrant:6333
      - ECHOES_AI_URL=http://host.docker.internal:8000
    depends_on:
      - qdrant
    restart: unless-stopped
    networks:
      - echoes-network
    extra_hosts:
      - "host.docker.internal:host-gateway"

  # 可选：本地 Embedding 服务（独立部署时）
  embedding-service:
    image: shaowenchen/text2vec:latest
    container_name: echoes-embedding
    ports:
      - "8000:8000"
    volumes:
      - ./models:/app/models
    restart: unless-stopped
    networks:
      - echoes-network

networks:
  echoes-network:
    driver: bridge
```

### 12.2 Python Dockerfile

```dockerfile
# echoes-langgraph/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8088

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088"]
```

### 12.3 配置文件示例

```yaml
# echoes-langgraph/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    ECHOES_AI_URL: str = "http://localhost:8000"
    CORS_ORIGINS: list[str] = ["*"]
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

**文档版本**: v2.0 (优化版)
**创建日期**: 2026-02-28
**更新日期**: 2026-03-01
**负责人**: Echoes Team
