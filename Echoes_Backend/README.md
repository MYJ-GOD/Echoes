# Echoes Backend

Java Spring Cloud 微服务 + Python AI 服务。配置集中在 Nacos，服务通过 Nacos 注册发现。

## 服务

| 服务 | 端口 | 职责 |
|---|---|---|
| echoes-service-gateway | 18080 | 网关，唯一外部入口 |
| echoes-service-user | 18081 | 认证、JWT、用户 |
| echoes-service-conversation | 18082 | 会话编排、SSE |
| echoes-service-voice | 18083 | 声音资产、TTS 分发 |
| echoes-service-admin | 18084 | 管理后台 |
| echoes-service-rag | 18086 | Agent 代理 |
| echoes-common | - | 公共模块 |
| [Echoes-AI](Echoes-AI/README.md) | 8000 | CosyVoice2 TTS/ASR |
| [echoes-langgraph](echoes-langgraph/README.md) | 8088 | LangGraph Agent |

## 基础设施

MySQL(3306)、MongoDB(27017)、Redis(6379)、Nacos(8848)、Qdrant(6333)、MinIO(9000)

## 启动

```bash
# 基础设施
docker-compose up -d mysql redis mongodb nacos qdrant minio

# 编译 + 启动（按依赖顺序）
mvn clean package -DskipTests
mvn spring-boot:run -pl echoes-service-gateway
mvn spring-boot:run -pl echoes-service-user
# ... 其余服务同理
```

Nacos 控制台 http://localhost:8848/nacos（`nacos/nacos`），首次启动自动导入 `init/nacos-yaml/` 配置。

## 常用命令

```bash
mvn clean package -DskipTests           # 编译全部
mvn spring-boot:run -pl <module>        # 运行单个服务
mvn test -pl <module>                   # 测试单个模块
```

## 配置

Java 服务从 Nacos 加载配置，本地 `application.yml` 仅含 Nacos 地址。配置模板在 `init/nacos-yaml/`，密钥走环境变量（见各服务 `.env.example`）。

## 文档

`docs/` 下有架构设计、Nacos 配置说明、接口清单等。
