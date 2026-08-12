# Echoes

语音 AI 对话系统。基于 LangGraph 的 ReAct Agent 做对话与记忆，CosyVoice2 做声音克隆与 TTS，Spring Cloud 微服务承载业务，Vue 3 前端。

## 架构

```
客户端 → Gateway (18080) → Java 微服务 → Python AI 服务（内网）
```

| 服务 | 语言 | 端口 | 职责 |
|---|---|---|---|
| gateway | Java | 18080 | 网关，唯一外部入口 |
| user | Java | 18081 | 认证、用户 |
| conversation | Java | 18082 | 会话编排、SSE |
| voice | Java | 18083 | 声音资产、TTS 分发 |
| admin | Java | 18084 | 管理后台 |
| rag | Java | 18086 | Agent 代理 |
| Echoes-AI | Python | 8000 | CosyVoice2 TTS/ASR |
| echoes-langgraph | Python | 8088 | LangGraph Agent |

## 快速开始

```bash
# 1. 基础设施
cd Echoes_Backend
docker-compose up -d mysql redis mongodb nacos qdrant

# 2. Java 后端
mvn clean package -DskipTests
mvn spring-boot:run -pl echoes-service-gateway   # 各服务依次启动

# 3. AI 服务
cd echoes-langgraph && uvicorn app.main:app --port 8088
cd Echoes-AI && ./run_echoes_ai.bat

# 4. 前端
cd Echoes_Frontend && pnpm install && pnpm dev
```

模型权重需先下载，见 [models/README.md](models/README.md)。

## 技术栈

- **后端**：Spring Cloud（Gateway/OpenFeign）、Nacos、MySQL、MongoDB、Redis
- **AI**：LangGraph、Qdrant、bge-m3 / bge-reranker、CosyVoice2、DeepSeek
- **前端**：Vue 3、Vite、Pinia

## 文档

- [后端说明](Echoes_Backend/README.md)
- [Agent 服务](Echoes_Backend/echoes-langgraph/README.md)
- [架构设计](Echoes_Backend/docs/Echoes_Architecture.md)

## License

Apache-2.0
