# RAG + LangGraph 集成实施计划

> **文档版本**: v1.0
> **创建日期**: 2026-03-01
> **预计周期**: 12 周
> **负责人**: Echoes Team

---

## 📋 计划概览

| 阶段 | 周期 | 主题 | 关键交付物 |
|------|------|------|-----------|
| **Phase 0** | Week 1-2 | 基础框架搭建 | Qdrant 部署、Python 项目骨架 |
| **Phase 1** | Week 3-4 | 知识库管理 | 知识库 CRUD、文档向量化 |
| **Phase 2** | Week 5-6 | RAG 检索核心 | 向量检索、Rerank 排序 |
| **Phase 3** | Week 7-8 | LangGraph 工作流 | 完整工作流编排、条件路由 |
| **Phase 4** | Week 9-10 | Java 集成 | SSE 封装、幂等性、端到端测试 |
| **Phase 5** | Week 11-12 | 对话历史向量化 | 历史检索、性能优化、验收 |

---

## 📅 详细实施计划

### Phase 0: 基础框架搭建 (Week 1-2)

#### 任务分解

| ID | 任务 | 详细说明 | 预计工时 | 依赖 | 负责人 |
|----|------|---------|---------|------|--------|
| 0.1 | Docker 环境准备 | 安装 Docker Desktop，配置 WSL2 后端 | 2h | - | - |
| 0.2 | Qdrant 部署 | 编写 `docker-compose.rag.yml`，启动 Qdrant 容器 | 4h | 0.1 | Backend |
| 0.3 | Qdrant 验证 | 使用 Postman/curl 测试 Qdrant API 连通性 | 2h | 0.2 | - |
| 0.4 | Python 项目初始化 | 创建 `echoes-langgraph/` 目录结构 | 2h | - | Backend |
| 0.5 | Python 依赖安装 | 编写 `requirements.txt`，安装依赖 | 4h | 0.4 | - |
| 0.6 | Embedding 集成 | 实现 `embedding_service.py`，测试 BGE-M3 | 8h | 0.5 | Backend |
| 0.7 | Qdrant 客户端 | 实现 `qdrant_service.py`，创建 Collections | 8h | 0.6 | Backend |
| 0.8 | FastAPI 骨架 | 实现 `main.py`、`config.py` | 4h | 0.4 | Backend |
| 0.9 | Java 项目初始化 | 创建 `echoes-service-rag/` 模块 | 4h | - | Backend |
| 0.10 | Java 依赖配置 | 编写 `pom.xml`，配置 Spring Boot | 4h | 0.9 | Backend |
| 0.11 | 健康检查端点 | Python `/health`、Java `/actuator/health` | 2h | 0.8, 0.10 | Backend |

#### Week 1 日程

| 时间 | 任务 | 目标 |
|------|------|------|
| Mon | 0.1, 0.2, 0.3 | Qdrant 成功部署并验证 |
| Tue | 0.4, 0.5, 0.6 | Python 项目可运行，Embedding 可生成向量 |
| Wed | 0.7 | Qdrant 可存储和查询向量 |
| Thu | 0.8, 0.9 | FastAPI 骨架完成，Java 项目创建 |
| Fri | 0.10, 0.11 | 健康检查通过，周 review |

#### Week 2 日程

| 时间 | 任务 | 目标 |
|------|------|------|
| Mon | 0.7 (续) | Qdrant Collections 配置完成 (HNSW、分片) |
| Tue | 0.6 (续) | 批量 Embedding 测试，性能基准 |
| Wed | 代码审查 | Phase 0 中期审查 |
| Thu | 文档补充 | 补充 README、配置说明 |
| Fri | Phase 0 验收 | 验收测试，问题修复 |

#### 验收标准 (Phase 0)

- [ ] Qdrant 容器正常运行，API 可访问
- [ ] Python 服务 `/health` 返回 200
- [ ] 可生成向量并存入 Qdrant
- [ ] Java 项目可编译通过
- [ ] Docker Compose 配置完整

---

### Phase 1: 知识库管理 (Week 3-4)

#### 任务分解

| ID | 任务 | 详细说明 | 预计工时 | 依赖 | 负责人 |
|----|------|---------|---------|------|--------|
| 1.1 | MySQL 表创建 | 执行 `knowledge_base` 等 6 张表 SQL | 2h | - | DBA |
| 1.2 | 实体类编写 | Java `KnowledgeBase`, `Document`, `Chunk` 实体 | 4h | 1.1 | Backend |
| 1.3 | Repository 层 | MyBatis-Plus Mapper 接口 | 4h | 1.2 | Backend |
| 1.4 | Service 层基础 | `KnowledgeBaseService` CRUD | 8h | 1.3 | Backend |
| 1.5 | Controller | `KnowledgeBaseController` REST API | 8h | 1.4 | Backend |
| 1.6 | 文档上传接口 | `DocumentController.upload()` 文件处理 | 8h | 1.4 | Backend |
| 1.7 | 文档解析器 | 实现 PDF/Markdown/Text 解析 | 8h | 1.6 | Backend |
| 1.8 | Chunking 策略 | 实现按段落/字符分块逻辑 | 8h | 1.7 | Backend |
| 1.9 | Python 索引服务 | 实现 `index_document.py` 向量化 | 8h | Phase 0 | Backend |
| 1.10 | 索引状态管理 | `Document.status` 状态机 | 4h | 1.9 | Backend |
| 1.11 | API 测试 | Postman 集合，功能验证 | 4h | 1.5, 1.10 | QA |

#### Week 3 日程

| 时间 | 任务 | 目标 |
|------|------|------|
| Mon | 1.1, 1.2, 1.3 | MySQL 表创建，实体类和 Mapper 完成 |
| Tue | 1.4, 1.5 | Service 和 Controller 完成 |
| Wed | 1.6, 1.7 | 文档上传和解析功能完成 |
| Thu | 1.8 | Chunking 策略实现 |
| Fri | 1.9 | Python 索引服务完成，周 review |

#### Week 4 日程

| 时间 | 任务 | 目标 |
|------|------|------|
| Mon | 1.10 | 索引状态机实现 |
| Tue | 1.11 | API 功能测试 |
| Wed | 代码审查 | Phase 1 中期审查 |
| Thu | Bug 修复 | 修复测试发现问题 |
| Fri | Phase 1 验收 | 验收测试，演示 |

#### 验收标准 (Phase 1)

- [ ] 可创建/更新/删除知识库
- [ ] 可上传文档（支持 PDF/Markdown/TXT）
- [ ] 文档自动分块并向量化
- [ ] Qdrant 中可查询到文档向量
- [ ] API 测试用例全部通过

---

### Phase 2: RAG 检索核心 (Week 5-6)

#### 任务分解

| ID | 任务 | 详细说明 | 预计工时 | 依赖 | 负责人 |
|----|------|---------|---------|------|--------|
| 2.1 | Python 检索 API | 实现 `/search` 接口 | 4h | Phase 1 | Backend |
| 2.2 | `search_knowledge()` | Qdrant 向量检索核心函数 | 8h | Phase 0 | Backend |
| 2.3 | 混合检索 | 向量 + BM25 关键词混合 | 8h | 2.2 | Backend |
| 2.4 | Rerank 模型集成 | BGE-Reranker 加载和推理 | 8h | Phase 0 | Backend |
| 2.5 | `rerank_chunks()` | 重排序服务实现 | 4h | 2.4 | Backend |
| 2.6 | Java 检索服务 | `RagSearchService` 调用 Python | 8h | 2.1 | Backend |
| 2.7 | 检索日志 | `rag_retrieval_log` 记录 | 4h | 2.6 | Backend |
| 2.8 | 阈值调优 | 相似度阈值、Rerank 阈值测试 | 8h | 2.5 | Backend |
| 2.9 | 检索测试集 | 构建 100+ 测试问题集 | 8h | 2.8 | QA |
| 2.10 | 准确率评估 | 测试检索准确率 >= 85% | 8h | 2.9 | QA |
| 2.11 | 性能基准 | P95 延迟 < 200ms 验证 | 4h | 2.10 | Backend |

#### Week 5 日程

| 时间 | 任务 | 目标 |
|------|------|------|
| Mon | 2.1, 2.2 | Python 检索 API 完成 |
| Tue | 2.3 | 混合检索实现 |
| Wed | 2.4, 2.5 | Rerank 集成完成 |
| Thu | 2.6 | Java 检索服务完成 |
| Fri | 2.7 | 检索日志记录完成 |

#### Week 6 日程

| 时间 | 任务 | 目标 |
|------|------|------|
| Mon | 2.8 | 阈值调优 |
| Tue | 2.9 | 构建测试集 |
| Wed | 2.10 | 准确率评估 |
| Thu | 2.11 | 性能基准测试 |
| Fri | Phase 2 验收 | 验收测试，报告 |

#### 验收标准 (Phase 2)

- [ ] 检索 API 可正常调用
- [ ] 检索 P95 延迟 < 200ms
- [ ] 检索准确率 >= 85% (100 题测试)
- [ ] Rerank 可正确提升相关性
- [ ] 检索日志完整记录

---

### Phase 3: LangGraph 工作流 (Week 7-8)

#### 任务分解

| ID | 任务 | 详细说明 | 预计工时 | 依赖 | 负责人 |
|----|------|---------|---------|------|--------|
| 3.1 | `State` 定义 | TypedDict 状态结构 | 4h | Phase 2 | Backend |
| 3.2 | Guardrail 节点 | 安全护栏，敏感词过滤 | 8h | 3.1 | Backend |
| 3.3 | Query 改写节点 | 拼写纠错、指代消解 | 8h | 3.1 | Backend |
| 3.4 | 意图分类节点 | knowledge_query/chat/task 分类 | 8h | 3.1 | Backend |
| 3.5 | 检索节点 | 集成 Phase 2 检索 | 4h | 3.1, Phase 2 | Backend |
| 3.6 | Rerank 节点 | 集成 Phase 2 Rerank | 4h | 3.5 | Backend |
| 3.7 | 条件路由 | `should_use_rag()` 分支逻辑 | 8h | 3.6 | Backend |
| 3.8 | RAG 生成节点 | `generate_rag_node()` 调用 LLM | 8h | 3.7 | Backend |
| 3.9 | 降级生成节点 | `generate_fallback_node()` | 4h | 3.7 | Backend |
| 3.10 | 引用标注节点 | `citation_node()` 添加引用 | 8h | 3.8 | Backend |
| 3.11 | 工作流图构建 | `build_rag_workflow()` | 8h | 3.2-3.10 | Backend |
| 3.12 | 流式执行 | `astream()` 流式输出 | 8h | 3.11 | Backend |
| 3.13 | 单元测试 | 各节点独立测试 | 8h | 3.12 | QA |

#### Week 7 日程

| 时间 | 任务 | 目标 |
|------|------|------|
| Mon | 3.1, 3.2, 3.3 | State、Guardrail、Query 改写完成 |
| Tue | 3.4, 3.5 | 意图分类、检索节点完成 |
| Wed | 3.6, 3.7 | Rerank 节点、条件路由完成 |
| Thu | 3.8, 3.9 | RAG 生成、降级生成完成 |
| Fri | 3.10 | 引用标注完成，周 review |

#### Week 8 日程

| 时间 | 任务 | 目标 |
|------|------|------|
| Mon | 3.11 | 工作流图构建完成 |
| Tue | 3.12 | 流式执行完成 |
| Wed | 3.13 | 单元测试 |
| Thu | 代码审查 | Phase 3 中期审查 |
| Fri | Phase 3 验收 | 验收测试，演示 |

#### 验收标准 (Phase 3)

- [ ] 工作流可完整执行
- [ ] Guardrail 可拦截违规查询
- [ ] 检索为空时正确降级到纯生成
- [ ] 流式输出正常（NDJSON 格式）
- [ ] 单元测试覆盖率 >= 80%

---

### Phase 4: Java 集成 (Week 9-10)

#### 任务分解

| ID | 任务 | 详细说明 | 预计工时 | 依赖 | 负责人 |
|----|------|---------|---------|------|--------|
| 4.1 | `LangGraphClient` | WebClient HTTP 客户端 | 8h | Phase 3 | Backend |
| 4.2 | NDJSON 解析器 | 解析 Python 返回的流 | 8h | 4.1 | Backend |
| 4.3 | `SeqGenerator` | Java 单点生成 seq | 4h | - | Backend |
| 4.4 | SSE 封装器 | `SseEnvelope` 事件封装 | 8h | 4.2, 4.3 | Backend |
| 4.5 | `RagStreamService` | 流式对话服务 | 8h | 4.4 | Backend |
| 4.6 | `TurnService` | Turn 管理、幂等性检查 | 8h | 4.5 | Backend |
| 4.7 | 幂等性实现 | `workflow_execution` 唯一索引 | 4h | 4.6 | Backend |
| 4.8 | 重放逻辑 | 已完成 Turn 的 REPLAY | 8h | 4.7 | Backend |
| 4.9 | `RagController` | 对接 `/conversation/chat-stream` | 8h | 4.5 | Backend |
| 4.10 | 端到端测试 | 完整链路测试 | 8h | 4.9 | QA |
| 4.11 | 错误处理 | 超时、重试、熔断 | 8h | 4.10 | Backend |
| 4.12 | 可观测性 | TraceID 透传、指标收集 | 8h | 4.11 | Backend |

#### Week 9 日程

| 时间 | 任务 | 目标 |
|------|------|------|
| Mon | 4.1, 4.2 | HTTP 客户端、NDJSON 解析完成 |
| Tue | 4.3, 4.4 | Seq 生成器、SSE 封装完成 |
| Wed | 4.5 | RagStreamService 完成 |
| Thu | 4.6, 4.7 | TurnService、幂等性完成 |
| Fri | 4.8 | 重放逻辑完成，周 review |

#### Week 10 日程

| 时间 | 任务 | 目标 |
|------|------|------|
| Mon | 4.9 | RagController 完成 |
| Tue | 4.10 | 端到端测试 |
| Wed | 4.11 | 错误处理完善 |
| Thu | 4.12 | 可观测性集成 |
| Fri | Phase 4 验收 | 验收测试，演示 |

#### 验收标准 (Phase 4)

- [ ] `/conversation/chat-stream` 可正常调用 RAG 工作流
- [ ] SSE 事件格式符合架构文档
- [ ] 同 `turn_id` 请求可正确重放
- [ ] 前端可正常接收流式消息
- [ ] 错误场景有合理降级

---

### Phase 5: 对话历史向量化 (Week 11-12)

#### 任务分解

| ID | 任务 | 详细说明 | 预计工时 | 依赖 | 负责人 |
|----|------|---------|---------|------|--------|
| 5.1 | `conversation_vector` 表 | 确认表结构 | 2h | - | DBA |
| 5.2 | 向量化触发器 | Turn 完成后异步触发 | 8h | Phase 4 | Backend |
| 5.3 | `@Async` 配置 | Spring 异步任务配置 | 4h | 5.2 | Backend |
| 5.4 | 历史检索 API | 按 conversation_id 检索 | 8h | 5.3 | Backend |
| 5.5 | 用户画像 (可选) | `user_profiles` 构建 | 16h | - | Backend |
| 5.6 | 长期记忆管理 | 记忆存储和检索策略 | 8h | 5.5 | Backend |
| 5.7 | 批量向量化 | 历史数据批量处理 | 8h | 5.2 | Backend |
| 5.8 | 缓存策略 | Redis 缓存检索结果 | 8h | 5.4 | Backend |
| 5.9 | 压力测试 | 100+ 并发检索测试 | 8h | 5.8 | QA |
| 5.10 | 性能优化 | 根据测试结果优化 | 8h | 5.9 | Backend |
| 5.11 | API 文档 | Swagger/OpenAPI 文档 | 8h | - | Backend |
| 5.12 | 运维文档 | 部署、监控、告警手册 | 8h | - | Backend |
| 5.13 | 最终验收 | 全功能验收测试 | 8h | All | Team |

#### Week 11 日程

| 时间 | 任务 | 目标 |
|------|------|------|
| Mon | 5.2, 5.3 | 向量化触发器完成 |
| Tue | 5.4 | 历史检索 API 完成 |
| Wed | 5.7, 5.8 | 批量处理、缓存策略 |
| Thu | 5.9 | 压力测试 |
| Fri | 5.10 | 性能优化，周 review |

#### Week 12 日程

| 时间 | 任务 | 目标 |
|------|------|------|
| Mon | 5.11 | API 文档完成 |
| Tue | 5.12 | 运维文档完成 |
| Wed | 5.13 | 最终验收测试 |
| Thu | Bug 修复 | 修复验收问题 |
| Fri | 项目总结 | 复盘、上线准备 |

#### 验收标准 (Phase 5)

- [ ] 历史对话可语义检索
- [ ] 支持 100+ 并发检索
- [ ] API 文档完整 (Swagger)
- [ ] 运维文档完善
- [ ] 最终验收测试通过

---

## 📊 里程碑

| 里程碑 | 时间点 | 验收条件 |
|--------|--------|---------|
| **M0** | Week 2 结束 | Phase 0 完成，基础框架就绪 |
| **M1** | Week 4 结束 | Phase 1 完成，知识库可上传 |
| **M2** | Week 6 结束 | Phase 2 完成，检索准确率达标 |
| **M3** | Week 8 结束 | Phase 3 完成，工作流可执行 |
| **M4** | Week 10 结束 | Phase 4 完成，端到端可运行 |
| **M5** | Week 12 结束 | Phase 5 完成，项目验收 |

---

## 🎯 关键路径

```
Phase 0 (基础) → Phase 1 (知识库) → Phase 2 (检索) → Phase 3 (工作流) → Phase 4 (集成) → Phase 5 (验收)
                     ↓                    ↓              ↓
                  MySQL 表              Rerank 模型     SSE 封装
                     ↓                    ↓              ↓
                  文档上传               检索 API       幂等性
```

**关键路径任务**（延期会影响整体进度）：
1. Phase 0: Qdrant 部署 + Embedding 集成
2. Phase 1: 文档上传 + 向量化
3. Phase 2: 检索 API + Rerank
4. Phase 3: 工作流编排 + 流式执行
5. Phase 4: SSE 封装 + 幂等性

---

## ⚠️ 风险与应对

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| 人员变动 | 延期 | 中 | 任务文档化，多人 review |
| 技术难点 | 延期 | 中 | 预留 buffer，及时升级问题 |
| 需求变更 | 返工 | 中 | 变更评审，版本管理 |
| 环境问题 | 延期 | 低 | 提前准备开发/测试环境 |
| 第三方依赖 | 阻塞 | 低 | 提前调研，准备备选方案 |

---

## 📈 进度追踪

### 每日站会

- 时间：每天 10:00
- 内容：
  - 昨天完成了什么
  - 今天计划做什么
  - 有什么阻碍

### 周报模板

```markdown
## Week X 周报

### 本周完成
- [任务 X.X] 100% - 说明

### 进行中
- [任务 X.X] 50% - 说明

### 风险/问题
- 无 / 描述

### 下周计划
- [任务 X.X] - 说明
```

---

## 📁 交付物清单

| 类型 | 文件/目录 | 说明 |
|------|----------|------|
| **Java** | `echoes-service-rag/` | RAG 服务 Java 模块 |
| **Python** | `echoes-langgraph/` | LangGraph 服务 |
| **SQL** | `echoes_Backend/init/rag_schema.sql` | 数据库脚本 |
| **Docker** | `docker-compose.rag.yml` | 容器编排 |
| **API 文档** | `docs/rag-api.md` | Swagger 文档 |
| **运维文档** | `docs/rag-ops.md` | 部署、监控手册 |

---

## ✅ 检查清单

### Phase 0 检查清单

- [ ] Docker Desktop 已安装
- [ ] Qdrant 容器可访问 (http://localhost:6333)
- [ ] Python 3.11 环境已准备
- [ ] `requirements.txt` 依赖安装完成
- [ ] Embedding 可生成 1024 维向量
- [ ] Qdrant Collection 已创建
- [ ] Java 项目可编译
- [ ] `/health` 端点可访问

### Phase 1 检查清单

- [ ] MySQL 6 张表已创建
- [ ] MyBatis-Plus Mapper 可正常查询
- [ ] 知识库 API 可创建/更新/删除
- [ ] 文档上传接口可接收文件
- [ ] PDF/Markdown/TXT可解析
- [ ] Chunking 策略可按段落分块
- [ ] Python 索引服务可向量化
- [ ] Qdrant 可查询到向量

### Phase 2 检查清单

- [ ] Python `/search` API 可调用
- [ ] 向量检索可返回相似结果
- [ ] 混合检索 (向量 + 关键词) 可用
- [ ] Rerank 模型可加载
- [ ] 重排序可提升相关性
- [ ] Java 检索服务可调用 Python
- [ ] 检索日志可记录
- [ ] 准确率 >= 85% (100 题测试)
- [ ] P95 延迟 < 200ms

### Phase 3 检查清单

- [ ] `State` TypedDict 已定义
- [ ] Guardrail 节点可拦截违规
- [ ] Query 改写节点可优化查询
- [ ] 意图分类节点可识别意图
- [ ] 检索节点可调用检索服务
- [ ] Rerank 节点可重排序
- [ ] 条件路由可正确分支
- [ ] RAG 生成节点可调用 LLM
- [ ] 降级生成节点可用
- [ ] 引用标注节点可添加引用
- [ ] 工作流图可编译
- [ ] `astream()` 可流式输出
- [ ] 单元测试覆盖率 >= 80%

### Phase 4 检查清单

- [ ] `LangGraphClient` 可调用 Python
- [ ] NDJSON 解析器可解析流
- [ ] `SeqGenerator` 可生成唯一 seq
- [ ] SSE 封装器可封装事件
- [ ] `RagStreamService` 可流式对话
- [ ] `TurnService` 可管理 Turn
- [ ] `workflow_execution` 有唯一索引
- [ ] 已完成 Turn 可重放
- [ ] `RagController` 可处理请求
- [ ] 端到端测试通过
- [ ] 错误场景有降级
- [ ] TraceID 可透传

### Phase 5 检查清单

- [ ] `conversation_vector` 表已创建
- [ ] Turn 完成后可异步触发向量化
- [ ] 历史检索 API 可调用
- [ ] 批量向量化可处理历史数据
- [ ] Redis 缓存检索结果
- [ ] 压力测试通过 (100+ 并发)
- [ ] API 文档完整 (Swagger)
- [ ] 运维文档完善
- [ ] 最终验收测试通过

---

## 📞 联系方式

| 角色 | 职责 | 联系方式 |
|------|------|---------|
| 项目经理 | 进度追踪、资源协调 | - |
| 技术负责人 | 技术决策、代码审查 | - |
| Backend | 功能开发 | - |
| QA | 测试验收 | - |
| DBA | 数据库支持 | - |

---

**备注**:
- 所有任务使用 Git 分支管理，功能完成后 merge 到 `develop`
- 每周五进行代码审查
- 使用 Jira/禅道等工具追踪任务状态
