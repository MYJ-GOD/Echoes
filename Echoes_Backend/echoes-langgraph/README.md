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
│   ├── graph/
│   │   ├── workflow.py      # LangGraph 工作流定义
│   │   ├── nodes.py         # 节点实现
│   │   ├── state.py         # 状态定义
│   │   └── __init__.py
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
│   ├── conftest.py          # 测试配置
│   └── test_retrieval.py    # 检索测试套件
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
