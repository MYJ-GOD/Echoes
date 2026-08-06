# Echoes — 语音 AI 对话系统

Echoes 是一个端到端的**语音 AI 对话系统**：使用 CosyVoice2 做声音克隆与语音合成（TTS）、大模型驱动对话、ASR 语音识别，并提供知识库问答（RAG）。后端基于 Java Spring Cloud 微服务，AI 侧为 Python 服务，前端为 Vue 3。

## ✨ 功能特性

- 🗣️ **语音对话**：SSE 流式对话 + 实时 TTS 语音合成 + ASR 语音识别
- 🎙️ **声音克隆**：上传一段参考音频即可克隆声音，支持多声音资产管理
- 🧠 **知识库问答**：LangGraph + Qdrant + bge-m3 的 RAG 能力
- 💬 **多轮会话管理**：`turn_id` 幂等，SSE 事件序列号规范
- 👨‍👩‍👧 家庭成员管理、对话记录
- 🌐 Vue 3 前端 + Java 网关统一入口

## 🏗️ 技术架构

外部客户端 → **Gateway (18080)** → Java 微服务 → Python AI 服务（仅内部调用）

| 服务 | 语言 | 端口 | 职责 |
|---|---|---|---|
| `echoes-service-gateway` | Java | 18080 | Spring Cloud Gateway，唯一外部入口 |
| `echoes-service-user` | Java | 18081 | 认证、JWT、用户管理 |
| `echoes-service-conversation` | Java | 18082 | SSE 编排、会话/回合管理 |
| `echoes-service-voice` | Java | 18083 | 声音资产 CRUD、TTS 任务分发 |
| `echoes-service-admin` | Java | 18084 | 管理操作 |
| `echoes-service-rag` | Java | 18086 | RAG 集成（代理到 LangGraph） |
| `Echoes-AI` | Python | 8000 | CosyVoice2 TTS / ASR 执行 |
| `echoes-langgraph` | Python | 8088 | LangGraph RAG（Qdrant + bge-m3） |

**关键约定**（详见 `docs/Echoes_Architecture.md`）：

- 唯一的对外流式接口：`POST /conversation/chat-stream`
- Python 只做 LLM/TTS/ASR 执行，不向外暴露 SSE，不做路由决策
- `turn_id` 由客户端生成（UUIDv7/ULID/Snowflake），且重试时不变
- 内部服务调用必须携带 `X-INTERNAL=1`，网关硬性拦截 `/internal/**` 与 `/voice/**`
- 绑定 `voiceAssetId` 的会话必须使用该声音，禁止静默回退默认音色（否则返回 `VOICE_NOT_AVAILABLE`）

## 📁 目录结构

```
Echoes/
├── Echoes_Backend/          # Java 微服务 + Python AI 服务
│   ├── Echoes-AI/           # CosyVoice2 TTS/ASR 服务
│   ├── echoes-langgraph/    # LangGraph RAG 服务
│   ├── echoes-service-*/    # Java 微服务（gateway/user/conversation/voice/admin/rag/common）
│   ├── init/nacos-yaml/     # Nacos 配置中心模板（密钥为占位符）
│   ├── docs/                # 架构与方案文档
│   └── third_party/         # 第三方源码（CosyVoice，需自行 clone，不入仓）
├── Echoes_Frontend/         # Vue 3 + Vite 前端
├── models/                  # 本地模型权重与声音数据（不入仓，见 models/README.md）
└── docs/
```

## 🚀 快速开始

### 0. 准备模型权重（必做）

CosyVoice2 权重和 `third_party/CosyVoice` 源码不入仓，请先按 **[models/README.md](models/README.md)** 下载。

### 1. 启动基础设施

```bash
cd Echoes_Backend
docker-compose up -d mysql redis mongodb nacos qdrant
# 完整（含 LangGraph）：docker-compose up -d
```

Nacos 控制台：http://localhost:8848/nacos （默认 `nacos/nacos`）

### 2. 启动 Java 后端

```bash
cd Echoes_Backend
mvn clean package -DskipTests
mvn spring-boot:run -pl echoes-service-gateway   # 依次启动各服务
```

### 3. 启动 Echoes-AI（TTS/ASR）

```bash
cd Echoes_Backend/Echoes-AI
./run_echoes_ai.bat   # Windows 一键启动（配置 conda 环境）
# 或手动：
# conda activate cosyvoice2 && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. 启动 LangGraph RAG

```bash
cd Echoes_Backend/echoes-langgraph
python -m venv venv && venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8088
```

### 5. 启动前端

```bash
cd Echoes_Frontend
pnpm install
pnpm dev   # http://localhost:5173，/api 代理到 18080
```

## 🔧 配置说明

所有 Java 服务启动时从 **Nacos** 加载配置，模板位于 `Echoes_Backend/init/nacos-yaml/`。
密钥通过环境变量注入，仓库中仅保留占位符：

| 环境变量 | 说明 |
|---|---|
| `DASHSCOPE_API_KEY` | 阿里云百炼大模型 API Key（对话模型） |
| `ALIYUN_ACCESS_KEY_ID` / `ALIYUN_ACCESS_KEY_SECRET` | 阿里云 OSS（声音文件存储） |
| `JWT_USER_SECRET_KEY` / `JWT_ADMIN_SECRET_KEY` | JWT 签名密钥（≥32 字符） |
| `VOICE_CALLBACK_API_KEY` | 内部回调密钥 |
| `DB_PASSWORD` / `MONGODB_PASSWORD` | 数据库密码 |

> 部署时请复制 `init/nacos-yaml/.env.example` 为 `.env` 并填入真实值；
> **切勿把真实密钥提交到仓库**。

## 🔒 安全说明

- 开源版配置中的真实密钥（阿里云 OSS / DashScope）已替换为占位符
- 若你的密钥曾出现在已推送的仓库历史中，请**立即在阿里云控制台重置**
- 本仓库不包含任何私人语音数据

## 📄 License

[Apache License 2.0](LICENSE)。CosyVoice 为 FunAudioLLM 项目，遵循其 Apache-2.0 许可。
