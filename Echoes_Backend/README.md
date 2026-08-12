# Echoes Backend — 微服务后端

Echoes 语音 AI 对话系统的后端，采用 Java Spring Cloud 微服务架构 + Python AI 服务。所有外部请求经 Gateway 统一入口，内部服务通过 Nacos 注册发现，配置集中管理。

---

## 服务清单

### Java 微服务（Spring Cloud）

| 服务 | 端口 | 职责 | 关键技术 |
|---|---|---|---|
| `echoes-service-gateway` | 18080 | 唯一外部入口，路由、鉴权、限流 | Spring Cloud Gateway |
| `echoes-service-user` | 18081 | 认证、JWT、用户管理 | Spring Security + JWT |
| `echoes-service-conversation` | 18082 | SSE 编排、会话/回合管理、Agent 转发 | WebFlux + SSE |
| `echoes-service-voice` | 18083 | 声音资产 CRUD、TTS 任务分发 | MyBatis + Redis Stream |
| `echoes-service-admin` | 18084 | 管理操作、数据治理 | Feign（跨服务调用） |
| `echoes-service-rag` | 18086 | Agent 代理（转发到 LangGraph） | WebClient |
| `echoes-common` | - | 公共模块（工具、异常、上下文） | - |

### Python AI 服务

| 服务 | 端口 | 职责 | 文档 |
|---|---|---|---|
| `Echoes-AI` | 8000 | CosyVoice2 TTS / ASR 执行 | [README](Echoes-AI/README.md) |
| `echoes-langgraph` | 8088 | LangGraph Agent（ReAct + 记忆检索） | [README](echoes-langgraph/README.md) |

---

## 架构原则

详见 [docs/Echoes_Architecture.md](docs/Echoes_Architecture.md)：

1. **唯一外部入口**：所有请求经 Gateway（18080），内部服务不直接对外
2. **唯一对外流式接口**：`POST /conversation/chat-stream`
3. **Python 职责边界**：只做 LLM/TTS/ASR 执行，不暴露 SSE，不做路由决策
4. **幂等性**：`turn_id` 由客户端生成，重试时不变
5. **内部鉴权**：服务间调用携带 `X-INTERNAL=1`，Gateway 硬拦截 `/internal/**` 与 `/voice/**`
6. **声音绑定**：会话绑定 `voiceAssetId` 后必须使用该音色，禁止静默回退

---

## 基础设施

| 组件 | 端口 | 用途 |
|---|---|---|
| MySQL 8.0 | 3306 | 业务数据（用户、会话、声音资产） |
| MongoDB 7 | 27017 | 对话记忆备份、静态画像 |
| Redis 7 | 6379 | 缓存、Redis Stream（TTS 任务队列） |
| Nacos 2.2.3 | 8848 | 服务注册发现、配置中心 |
| Qdrant | 6333 | 向量数据库（记忆检索） |
| MinIO | 9000 | 对象存储（声音文件） |

---

## 快速启动

### 1. 启动基础设施

```bash
docker-compose up -d mysql redis mongodb nacos qdrant minio
# 完整（含 LangGraph）：docker-compose up -d
```

- Nacos 控制台：http://localhost:8848/nacos（默认 `nacos/nacos`）
- 首次启动 Nacos 会自动导入 `init/nacos-yaml/` 下的配置

### 2. 编译 Java 服务

```bash
mvn clean package -DskipTests
```

### 3. 启动 Java 服务（按依赖顺序）

```bash
mvn spring-boot:run -pl echoes-service-gateway
mvn spring-boot:run -pl echoes-service-user
mvn spring-boot:run -pl echoes-service-conversation
mvn spring-boot:run -pl echoes-service-voice
mvn spring-boot:run -pl echoes-service-admin
mvn spring-boot:run -pl echoes-service-rag
```

### 4. 启动 Python 服务

```bash
# LangGraph Agent（见 echoes-langgraph/README.md）
cd echoes-langgraph && uvicorn app.main:app --port 8088

# TTS/ASR（见 Echoes-AI/README.md）
cd Echoes-AI && ./run_echoes_ai.bat
```

---

## 配置管理（Nacos）

所有 Java 服务启动时从 Nacos 加载配置，本地 `application.yml` 仅含 Nacos 连接地址。

- 配置模板：`init/nacos-yaml/Echoes--<service>.yaml`
- 共享配置：`init/nacos-yaml/application.yaml`
- 命名规范：双横线 `--` 表示无环境后缀（适用所有 profile）

密钥通过环境变量注入，仓库仅保留占位符。详见 [docs/Nacos 配置说明.md](docs/Nacos%20配置说明.md)。

---

## Java 服务内部结构

每个 Java 服务遵循统一包结构 `com.echoes.<service>/`：

```
com.echoes.<service>/
├── domain/        # 领域层：实体、Mapper、Service、DTO（按业务域分组）
├── config/        # Spring Bean、安全、框架配置
└── common/        # 服务内工具（非共享模块）
```

`echoes-common` 为共享库：`annotation/`、`aspect/`、`context/`（用户上下文传播）、`entity/`、`exception/`、`util/`。

---

## 常用命令

```bash
# 编译所有模块，跳过测试
mvn clean package -DskipTests

# 运行单个服务
mvn spring-boot:run -pl echoes-service-conversation

# 测试单个模块
mvn test -pl echoes-service-conversation

# 全量测试
mvn test
```

---

## 文档索引

| 文档 | 说明 |
|---|---|
| [Echoes_Architecture.md](docs/Echoes_Architecture.md) | 系统架构设计 |
| [Nacos 配置说明.md](docs/Nacos%20配置说明.md) | 配置中心使用 |
| [接口统计.md](docs/接口统计.md) | API 接口清单 |
| [项目结构.md](docs/项目结构.md) | 代码结构说明 |

---

## License

[Apache License 2.0](../LICENSE)
