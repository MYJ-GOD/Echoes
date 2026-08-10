# Echoes LangGraph Service

RAG + LangGraph 工作流服务，为 Echoes 项目提供智能检索增强生成能力。

## 快速开始

### 1. 使用 Docker Compose 启动（推荐）

```bash
# 启动 Qdrant 和 LangGraph 服务
docker-compose -f docker-compose.rag.yml up -d

# 查看日志
docker-compose -f docker-compose.rag.yml logs -f

# 健康检查
curl http://localhost:8088/health
```

### 2. 本地开发

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 复制环境变量配置
cp .env.example .env

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8088
```

## API 端点

### 基础检索
| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/health/detailed` | GET | 详细健康检查（Qdrant、模型、磁盘） |
| `/search` | POST | 向量检索 |
| `/search/hybrid` | POST | 混合检索（向量 + BM25） |

### RAG 对话
| 端点 | 方法 | 说明 |
|------|------|------|
| `/rag/chat` | POST | RAG 对话（非流式） |
| `/rag/chat/stream` | POST | RAG 对话（流式，NDJSON） |

### Agent 编排（Week1-4）
| 端点 | 方法 | 说明 |
|------|------|------|
| `/agent/chat` | POST | Agent 对话（非流式）：planner → 工具链 → 人格化生成 → 记忆 |
| `/agent/chat/stream` | POST | Agent 对话（流式，NDJSON），Java 端转 SSE |

**Agent StateGraph 工作流：**

```
                    ┌─────────┐
                    │ planner │  (LLM 决策：intent + tools)
                    └────┬────┘
                         │
                    [needs_tools?]
                    ╱           ╲
              tools ╱             ╲ direct (闲聊短路)
                  ╱               ╲
          ┌──────▼────┐            ╲
          │tool_router│             ╲
          │(构造执行计划)│             ╲
          └─────┬─────┘              ╲
                │                     ╲
          ┌─────▼─────┐                ╲
          │  executor  │                 ╲
          │(顺序执行工具)│                 ╲
          └─────┬─────┘                  ╲
                │                         ╲
                └────────┬─────────────────┘
                         │
                ┌────────▼────────┐
                │response_generator│  (人格化生成/安慰话术短路)
                └────────┬─────────┘
                         │
                ┌────────▼────────┐
                │ memory_updater  │  (实体抽取 + Qdrant 写入)
                └────────┬─────────┘
                         │
                        END
```

**节点职责：**
- **planner**：LLM 分析用户意图（chat/emotional_support/memory_recall/profile_query/task），决定需要哪些工具
- **tool_router**：将工具名解析为可执行清单 `{name, args}`（体现工具选择能力）
- **executor**：按 plan 顺序执行工具，结果写入 state（情绪分析 → 记忆检索 → 画像查询 → 安慰话术）
- **response_generator**：综合情绪/记忆/画像 + 人格模式（温柔/理性/活泼）生成回复；情绪支持场景走模板话术短路（不调 LLM，快且稳）
- **memory_updater**：LLM 实体抽取 + 对话摘要写入 Qdrant `conversation_history`（长期记忆闭环）

**条件边：**
- `planner → [needs_tools?]`：有工具需求 → `tool_router`；纯闲聊 → `response_generator`（短路径）

**特性：**
- **Checkpointer（AsyncSqliteSaver）**：`thread_id` = `session_id`，同会话断点续跑
- **记忆图谱**：向量检索 + 实体链接双信号（实体命中奖励 +0.15/个，最高 +0.45）
- **容错降级**：Qdrant 未启动/bge-m3 未下载时优雅降级（payload 关键词匹配），不 crash workflow

### 可观测性
| 端点 | 方法 | 说明 |
|------|------|------|
| `/metrics` | GET | 检索性能指标（延迟、P95、Fallback 率） |
| `/retrieval-logs` | GET | 查询检索日志 |
| `/workflows` | GET | 工作流列表 |

## 项目结构

```
echoes-langgraph/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置管理
│   ├── api/
│   │   ├── routes.py        # API 路由（含混合检索、可观测性）
│   │   └── __init__.py
│   ├── graph/               # RAG 工作流（检索增强生成）
│   │   ├── workflow.py      # LangGraph 工作流定义
│   │   ├── nodes.py         # 节点实现
│   │   ├── state.py         # 状态定义
│   │   └── __init__.py
│   ├── agent/               # Agent 编排（语音陪伴，Week1-4）
│   │   ├── workflow.py      # 五节点 StateGraph + AsyncSqliteSaver checkpointer
│   │   ├── nodes.py         # planner/tool_router/executor/generator/memory_updater
│   │   ├── tools.py         # 陪伴工具集（情绪/记忆/画像/安慰话术）
│   │   ├── memory.py        # Qdrant 长期记忆 + 实体链接记忆图谱
│   │   └── state.py         # Agent 状态定义
│   ├── services/
│   │   ├── __init__.py      # 服务导出
│   │   ├── qdrant_service.py    # Qdrant 检索（支持混合检索）
│   │   ├── embedding_service.py # Embedding 生成
│   │   ├── bm25_service.py      # BM25 关键词检索
│   │   ├── tokenizer_service.py # 分词服务
│   │   ├── rerank_service.py    # Rerank 排序（支持 MMR 多样性）
│   │   ├── llm_service.py       # LLM 文本生成
│   │   └── retrieval_logger.py  # 检索日志和评估
│   ├── models/
│   │   └── guardrail.py     # 安全护栏模型
│   └── utils/
│       ├── logger.py
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # 测试配置（checkpointer 清理 + 连接关闭）
│   ├── test_retrieval.py    # 检索测试套件
│   └── test_agent_workflow.py  # Agent workflow 集成测试（10 个，Week4）
├── pytest.ini               # pytest 配置（禁用插件，解决 event loop 挂起）
├── requirements.txt
├── Dockerfile
├── .env.example
├── README.md
└── PHASE2_SUMMARY.md        # Phase 2 实施总结
```

## 技术栈

- **FastAPI**: Web 框架
- **LangGraph**: Agent 工作流编排
- **Sentence Transformers**: Embedding 和 Rerank 模型
- **Qdrant**: 向量数据库（支持稠密 + 稀疏向量）
- **BGE-M3**: Embedding 模型（1024 维）
- **BGE-Reranker-v2-m3**: Rerank 模型

## 使用示例

### 混合检索

```bash
curl -X POST http://localhost:8088/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是 RAG?",
    "kb_ids": ["kb_001"],
    "top_k": 5,
    "alpha": 0.7,
    "use_rerank": true
  }'
```

### RAG 对话

```bash
curl -X POST http://localhost:8088/rag/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "如何部署 Qdrant?",
    "turn_id": "turn_001",
    "conversation_id": "conv_001",
    "kb_ids": ["kb_001"],
    "top_k": 3
  }'
```

### 查询检索指标

```bash
curl http://localhost:8088/metrics?days=7
```

## 开发计划

### 已完成
- [x] Phase 0.1: Qdrant 部署
- [x] Phase 0.2: Python 项目骨架
- [x] Phase 0.3: Embedding 服务集成
- [x] Phase 0.4: Qdrant 客户端和 Collections 配置
- [x] Phase 1: 知识库管理 API（Java + Python）
- [x] Phase 2: RAG 检索核心（混合检索、Rerank、可观测性）

### 进行中
- [ ] Phase 3: 工作流优化与集成
  - [ ] Query 改写优化
  - [ ] 意图分类增强
  - [ ] 对话管理
  - [ ] Java 端集成

### 规划中
- [ ] Phase 4: 性能优化与部署
  - [ ] 检索延迟优化
  - [ ] 模型量化
  - [ ] 生产环境部署

## 许可证

MIT License
