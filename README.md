# Echoes — 语音 AI 对话系统

Echoes 是一个端到端的语音 AI 对话系统，集成声音克隆、语音合成（TTS）、自动语音识别（ASR）、大模型对话与记忆检索能力。后端采用 Java Spring Cloud 微服务架构，AI 侧为 Python 服务（LangGraph Agent + CosyVoice2），前端基于 Vue 3 实现。

---

## 核心特性

- **语音对话**：SSE 流式对话 + 实时 TTS 语音合成 + ASR 语音识别
- **声音克隆**：基于 CosyVoice2 的声音克隆，支持多声音资产管理
- **Agent 对话系统**：ReAct 循环 + 记忆检索质量工程 + LLM-judge Grounding
- **记忆管理**：Qdrant 向量检索 + MongoDB 双写，静态/动态画像分离
- **多轮会话管理**：`turn_id` 幂等设计，SSE 事件序列号规范
- **微服务架构**：网关统一入口，内部服务通过 `X-INTERNAL` 鉴权

---

## 技术架构

### 服务拓扑

```
外部客户端 → Gateway (18080) → Java 微服务 → Python AI 服务（内网）
```

| 服务 | 语言 | 端口 | 职责 |
|---|---|---|---|
| `echoes-service-gateway` | Java | 18080 | Spring Cloud Gateway，唯一外部入口 |
| `echoes-service-user` | Java | 18081 | 认证、JWT、用户管理 |
| `echoes-service-conversation` | Java | 18082 | SSE 编排、会话/回合管理 |
| `echoes-service-voice` | Java | 18083 | 声音资产 CRUD、TTS 任务分发 |
| `echoes-service-admin` | Java | 18084 | 管理操作 |
| `echoes-service-rag` | Java | 18086 | Agent 代理（转发到 LangGraph） |
| `Echoes-AI` | Python | 8000 | CosyVoice2 TTS / ASR 执行 |
| `echoes-langgraph` | Python | 8088 | LangGraph Agent 服务 |

### Agent 对话链路（echoes-langgraph）

完整执行流程（按调用顺序）：

```
[1] Guardrail（安全门禁）
    ↓ 关键词黑名单 + System Prompt 双重过滤
    ↓ 命中红线 → 直接拦截，返回安全兜底回复

[2] ReAct Agent 主循环
    ↓ planner（Thought）: 单步决策 next_tool + is_sufficient
    ↓ executor（Action）: 调用工具，记录 observation
    ↓ should_continue: 信息不足 → 回 planner（循环）
    ↓                  信息充足/超限 → response_generator
    ↓ 最大迭代次数（max_iterations=3）防止无限循环

[3] 工具集（Agent 可调用）
    - search_memory: 检索历史记忆（执行下面 [4] 的完整 RAG 链路）
    - update_user_state: 更新用户画像
    - analyze_emotion: 情绪分析
    - web_search: 外部搜索（DuckDuckGo）
    - get_user_profile / generate_comfort_response

[4] search_memory 内部 RAG 链路（记忆检索质量工程）
    ↓ Query Rewrite: 指代消解（qwen-turbo），提升召回率
    ↓ 粗召回: Query 向量化 → Qdrant HNSW 检索 TopK=30
    ↓ 精排: BGE-reranker Cross-Encoder 对候选重新打分
    ↓ Threshold 门禁: rerank_score < 0.5 → 返回空（不注入低质量记忆）
    ↓ 实体链接增强: 命中实体的记忆加分

[5] response_generator（人格化生成）
    ↓ System Prompt 人设锚点: 静态画像（MongoDB）锁死顶层，防止人格漂移
    ↓ 动态上下文: Qdrant user_profile（短期状态，走滑动窗口）
    ↓ LLM 生成回复（temperature=0.7）

[6] Grounding + 流式推送
    ↓ LLM-judge: 检查回复是否有记忆/搜索结果支撑（faithfulness）
    ↓ SSE 四事件流式推送（NDJSON → Java 端转 SSE）:
        - message.delta: 文本回复
        - emotion: 情绪标签
        - citation: 引用来源（检索到的记忆）
        - audio: 语音占位（TTS 由 Java 侧生成）

[7] memory_updater（存储侧）
    ↓ 双写: Qdrant（向量检索）+ MongoDB（原始 JSON 备份）
    ↓ 静态画像: 长期不变的用户设定 → MongoDB，锁死在 System Prompt
    ↓ 动态上下文: 短期状态 → Qdrant user_profile，滑动窗口
```

---

## 关键约定

详见 `docs/Echoes_Architecture.md`：

- **唯一对外流式接口**: `POST /conversation/chat-stream`
- **Python 职责边界**: 只做 LLM/TTS/ASR 执行，不向外暴露 SSE，不做路由决策
- **幂等性**: `turn_id` 由客户端生成（UUIDv7/ULID/Snowflake），重试时保持不变
- **内部鉴权**: 服务间调用必须携带 `X-INTERNAL=1`，网关硬性拦截 `/internal/**` 与 `/voice/**`
- **声音绑定**: 绑定 `voiceAssetId` 的会话必须使用该声音，禁止静默回退默认音色（否则返回 `VOICE_NOT_AVAILABLE`）

---

## 目录结构

```
Echoes/
├── Echoes_Backend/
│   ├── Echoes-AI/                # CosyVoice2 TTS/ASR 服务（Python）
│   ├── echoes-langgraph/         # LangGraph Agent 服务（Python）
│   ├── echoes-service-gateway/   # Spring Cloud Gateway
│   ├── echoes-service-user/      # 认证、JWT、用户管理
│   ├── echoes-service-conversation/  # SSE 编排、会话管理
│   ├── echoes-service-voice/     # 声音资产管理、TTS 分发
│   ├── echoes-service-admin/     # 管理操作
│   ├── echoes-service-rag/       # Agent 代理
│   ├── echoes-common/            # 公共模块
│   ├── init/nacos-yaml/          # Nacos 配置中心模板（密钥为占位符）
│   ├── docs/                     # 架构与方案文档
│   └── third_party/              # 第三方源码（CosyVoice，需自行 clone）
├── Echoes_Frontend/              # Vue 3 + Vite 前端
├── models/                       # 本地模型权重与声音数据（不入仓）
└── docs/                         # 项目文档
```

---

## 快速开始

### 前置准备

#### 1. 下载模型权重（必做）

CosyVoice2 权重和 `third_party/CosyVoice` 源码不入仓，请先按 **[models/README.md](models/README.md)** 下载。

#### 2. 配置密钥

所有 Java 服务从 **Nacos** 加载配置，模板位于 `Echoes_Backend/init/nacos-yaml/`。  
密钥通过环境变量注入，仓库中仅保留占位符。

| 环境变量 | 说明 |
|---|---|
| `DASHSCOPE_API_KEY` | 阿里云百炼大模型 API Key（对话模型） |
| `ALIYUN_ACCESS_KEY_ID` / `ALIYUN_ACCESS_KEY_SECRET` | 阿里云 OSS（声音文件存储） |
| `JWT_USER_SECRET_KEY` / `JWT_ADMIN_SECRET_KEY` | JWT 签名密钥（至少 32 字符） |
| `VOICE_CALLBACK_API_KEY` | 内部回调密钥 |
| `DB_PASSWORD` / `MONGODB_PASSWORD` | 数据库密码 |

部署时请复制 `init/nacos-yaml/.env.example` 为 `.env` 并填入真实值。  
**切勿将真实密钥提交到仓库。**

---

### 启动流程

#### 1. 启动基础设施

```bash
cd Echoes_Backend
docker-compose up -d mysql redis mongodb nacos qdrant
# 完整（含 LangGraph）：docker-compose up -d
```

- Nacos 控制台: http://localhost:8848/nacos（默认 `nacos/nacos`）
- Qdrant: http://localhost:6333
- MongoDB: `localhost:27017`（认证: `root/root`）

#### 2. 启动 Java 后端

```bash
cd Echoes_Backend
mvn clean package -DskipTests
# 依次启动各服务（或用 IDE 运行）
mvn spring-boot:run -pl echoes-service-gateway
mvn spring-boot:run -pl echoes-service-user
mvn spring-boot:run -pl echoes-service-conversation
mvn spring-boot:run -pl echoes-service-voice
mvn spring-boot:run -pl echoes-service-admin
mvn spring-boot:run -pl echoes-service-rag
```

#### 3. 启动 Echoes-AI（TTS/ASR）

```bash
cd Echoes_Backend/Echoes-AI
# Windows 一键启动（配置 conda 环境）
./run_echoes_ai.bat

# 或手动启动
conda activate cosyvoice2
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### 4. 启动 LangGraph Agent 服务

```bash
cd Echoes_Backend/echoes-langgraph

# 创建虚拟环境（首次）
python -m venv venv
venv/Scripts/activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置 .env（见 echoes-langgraph/.env.example）
# 至少需要配置：
#   LLM_API_KEY=<DeepSeek API Key>
#   LLM_BASE_URL=https://api.deepseek.com
#   LLM_MODEL=deepseek-chat

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8088
```

**首次启动注意**：
- `bge-m3` embedding 模型（约 2.2GB）会自动下载到 HuggingFace 缓存
- `bge-reranker-v2-m3` rerank 模型在首次调用检索时下载
- 如遇 HF 网络问题，设置镜像：`export HF_ENDPOINT=https://hf-mirror.com`

#### 5. 启动前端

```bash
cd Echoes_Frontend
pnpm install
pnpm dev   # http://localhost:5173，/api 代理到 18080
```

---

## 技术选型

### 后端（Java）
- **框架**: Spring Boot 2.7, Spring Cloud 2021
- **注册中心**: Nacos 2.2.3
- **网关**: Spring Cloud Gateway
- **数据库**: MySQL 8.0, MongoDB 7.0
- **缓存**: Redis 7
- **对象存储**: 阿里云 OSS
- **LLM**: 阿里云百炼 DashScope

### AI 侧（Python）
- **Agent 框架**: LangGraph（真 ReAct 循环，非伪 ReAct）
- **向量数据库**: Qdrant 1.17+（HNSW 索引）
- **Embedding**: BAAI/bge-m3（2048 维）
- **Rerank**: BAAI/bge-reranker-v2-m3（Cross-Encoder）
- **LLM**: DeepSeek（deepseek-chat），OpenAI 兼容接口
- **TTS**: CosyVoice2（声音克隆 + 语音合成）
- **ASR**: Paraformer（阿里达摩院）

### 前端
- Vue 3 + Vite + Pinia + Vue Router
- Axios（HTTP 客户端）
- SSE 流式对话

---

## 记忆检索质量工程

完整链路（已生产验证）：

1. **Query Rewrite**（指代消解）
   - 用轻量 LLM（qwen-turbo）补全省略、消解指代
   - 对话连续时收益显著（"它怎么样" → "美式咖啡怎么样"）

2. **粗召回**（高召回优先）
   - Qdrant HNSW 向量检索，TopK=30
   - 保证高召回率，后续精排校准精度

3. **BGE-Rerank 精排**（Cross-Encoder）
   - BAAI/bge-reranker-v2-m3 对 30 条候选重新打分
   - 用双塔交互模型（慢但准）替换向量余弦相似度（快但粗）

4. **Threshold 门禁**（质量控制）
   - 最高 rerank_score < 0.5 → 返回空结果
   - 防止低质量记忆污染 LLM 上下文
   - 当前阈值 0.5 基于实测校准（真实相关记忆约 0.60-0.64）

5. **实体链接增强**
   - 命中 NER 实体的记忆额外加分（+0.1 per entity，上限 0.3）
   - 最终排序 = rerank_score + entity_boost

---

## 安全说明

- 开源版配置中的真实密钥（阿里云 OSS / DashScope）已替换为占位符
- 若密钥曾出现在已推送的仓库历史中，请立即在阿里云控制台重置
- 本仓库不包含任何私人语音数据
- 内部服务通过 `X-INTERNAL` header 鉴权，网关强制拦截外部访问
- JWT 密钥通过环境变量注入，不入仓库

---

## 已知限制

1. **bge-reranker 模型下载**：首次启动需从 HuggingFace 下载约 2.2GB 模型，如网络不稳定建议配置镜像
2. **Threshold 校准**：当前 0.5 基于少量样本校准，后续应通过评测集正式标定
3. **Qdrant 版本警告**：client 1.19 vs server 1.17 minor 版本差 2（不影响功能，可忽略或升级服务端）
4. **MongoDB 双写**：motor 异步写入失败不阻断主流程（Qdrant 为主存储）

---

## 开发规范

- **Git 提交规范**: `feat/fix/refactor/docs/test(scope): message`
- **代码风格**: Java 遵循 Spring Boot 规范，Python 遵循 PEP 8
- **分支策略**: `main` 为稳定分支，功能开发走 feature 分支
- **密钥管理**: `.env` 文件加入 `.gitignore`，通过环境变量注入

---

## License

[Apache License 2.0](LICENSE)

CosyVoice 为 FunAudioLLM 项目，遵循其 Apache-2.0 许可。

---

## 参考文档

- [架构设计文档](docs/Echoes_Architecture.md)
- [模型下载指南](models/README.md)
- [Nacos 配置模板](Echoes_Backend/init/nacos-yaml/)
- [Agent 工作流图](Echoes_Backend/echoes-langgraph/README.md)（包含 StateGraph 可视化）
