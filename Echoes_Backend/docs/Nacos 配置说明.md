# Nacos 配置说明文档

## 概述

本文档介绍如何使用 Nacos 配置中心管理 Echoes Backend 的配置文件。所有敏感信息（密码、密钥、Token 等）都应通过 Nacos 或环境变量管理，不应硬编码在代码中。

## 配置文件列表

| 文件名 | Data ID | Group | 描述 |
|--------|---------|-------|------|
| `application.yaml` | `application.yaml` | DEFAULT_GROUP | 公共基础配置（数据库、Redis、MongoDB、阿里云 OSS、DashScope） |
| `Echoes--gateway.yaml` | `Echoes--gateway.yaml` | DEFAULT_GROUP | 网关服务配置 |
| `Echoes--user.yaml` | `Echoes--user.yaml` | DEFAULT_GROUP | 用户服务配置 |
| `Echoes--conversation.yaml` | `Echoes--conversation.yaml` | DEFAULT_GROUP | 会话服务配置 |
| `Echoes--voice.yaml` | `Echoes--voice.yaml` | DEFAULT_GROUP | 语音服务配置 |
| `Echoes--admin.yaml` | `Echoes--admin.yaml` | DEFAULT_GROUP | 管理服务配置 |

## 配置导入方式

### 方式一：通过 Nacos Web 控制台导入

1. 访问 Nacos 控制台：http://localhost:8848/nacos
2. 登录（默认账号/密码：nacos/nacos）
3. 进入 **配置管理 > 配置列表**
4. 点击 **+** 按钮创建新配置
5. 填写配置信息：
   - **Data ID**: `application.yaml`（或其他文件名）
   - **Group**: `DEFAULT_GROUP`
   - **配置格式**: `YAML`
   - **配置内容**: 复制对应 YAML 文件内容
6. 点击 **发布** 按钮

### 方式二：使用 Nacos CLI 工具

```bash
# 使用 nacos-cli 工具导入
nacos-cli config import --file application.yaml --data-id application.yaml --group DEFAULT_GROUP
```

### 方式三：通过 API 导入

```bash
curl -X POST "http://localhost:8848/nacos/v1/cs/configs" \
  -d "dataId=application.yaml" \
  -d "group=DEFAULT_GROUP" \
  -d "content=$(cat application.yaml)"
```

## 配置导入顺序

建议按照以下顺序导入配置：

1. **application.yaml** - 公共基础配置（最先导入，被其他配置引用）
2. **Echoes--gateway.yaml** - 网关服务配置
3. **Echoes--user.yaml** - 用户服务配置
4. **Echoes--conversation.yaml** - 会话服务配置
5. **Echoes--voice.yaml** - 语音服务配置
6. **Echoes--admin.yaml** - 管理服务配置

## 环境变量配置

配置文件中的敏感信息使用环境变量引用，格式如下：

```yaml
# 格式：${环境变量名：默认值}
echoes:
  datasource:
    username: ${DB_USERNAME:root}
    password: ${DB_PASSWORD:root}
```

### 设置环境变量的方式

#### Linux/Mac

```bash
# 临时设置（当前终端会话有效）
export DB_PASSWORD=your_password

# 永久设置（添加到~/.bashrc 或~/.zshrc）
echo "export DB_PASSWORD=your_password" >> ~/.bashrc
source ~/.bashrc
```

#### Windows (PowerShell)

```powershell
# 临时设置（当前终端会话有效）
$env:DB_PASSWORD="your_password"

# 永久设置（用户级别）
[System.Environment]::SetEnvironmentVariable("DB_PASSWORD", "your_password", "User")
```

#### Windows (CMD)

```cmd
:: 临时设置
set DB_PASSWORD=your_password

:: 永久设置（需要管理员权限）
setx DB_PASSWORD "your_password"
```

#### 使用.env 文件（推荐开发环境）

1. 复制 `.env.example` 为 `.env`：
   ```bash
   cp init/nacos-yaml/.env.example init/nacos-yaml/.env
   ```

2. 编辑 `.env` 文件，修改配置值

3. 使用 dotenv 工具加载环境变量：
   ```bash
   # Python
   pip install python-dotenv
   python -c "from dotenv import load_dotenv; load_dotenv('init/nacos-yaml/.env')"

   # Node.js
   npm install dotenv
   ```

## 配置示例

### application.yaml（公共配置）

```yaml
echoes:
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    host: ${DB_HOST:localhost}
    port: 3306
    database: ${DB_NAME:echoes}
    username: ${DB_USERNAME:root}
    password: ${DB_PASSWORD:root}

  redis:
    host: ${REDIS_HOST:localhost}
    port: 6379
    database: 0
    timeout: 3000ms

  mongodb:
    host: ${MONGODB_HOST:localhost}
    port: 27017
    database: ${MONGODB_DATABASE:echoes}
    username: ${MONGODB_USERNAME:root}
    password: ${MONGODB_PASSWORD:root}

  alioss:
    endpoint: "oss-cn-beijing.aliyuncs.com"
    accessKeyId: ${ALIYUN_ACCESS_KEY_ID:your-aliyun-access-key-id}
    accessKeySecret: ${ALIYUN_ACCESS_KEY_SECRET:your-aliyun-access-key-secret}
    bucketName: "echoes-sim"

spring:
  ai:
    dashscope:
      api-key: ${DASHSCOPE_API_KEY:your-dashscope-api-key}
      base-url: https://dashscope.aliyuncs.com/api/v1
      model: qwen3-max
```

### Echoes--user.yaml（用户服务配置）

```yaml
server:
  port: 18081

spring:
  datasource:
    type: com.alibaba.druid.pool.DruidDataSource
    url: jdbc:mysql://${echoes.datasource.host:localhost}:${echoes.datasource.port:3306}/${echoes.datasource.database:echoes}?useUnicode=true&characterEncoding=utf-8&useSSL=false&serverTimezone=Asia/Shanghai
    username: ${echoes.datasource.username:root}
    password: ${echoes.datasource.password:root}

# JWT 配置
sky:
  jwt:
    user-secret-key: ${JWT_USER_SECRET_KEY:change-me-user-secret-key-0123456789abcdef}
    user-ttl: 7200000
    user-token-name: token
```

## 生产环境配置建议

### 1. 使用 Nacos 配置中心

生产环境推荐使用 Nacos 配置中心统一管理配置：

- **优势**：
  - 配置集中管理，易于维护
  - 支持配置热更新
  - 支持配置版本管理
  - 支持多环境隔离（通过 Namespace）

### 2. 使用 K8s Secrets

如果使用 Kubernetes 部署，建议使用 K8s Secrets 管理敏感信息：

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: echoes-secrets
type: Opaque
stringData:
  DB_PASSWORD: your_production_password
  JWT_SECRET_KEY: your_production_jwt_key
  ALIYUN_ACCESS_KEY_SECRET: your_production_key_secret
```

### 3. 使用云厂商密钥管理服务

生产环境建议使用云厂商的密钥管理服务（KMS）：

- 阿里云 KMS
- AWS Secrets Manager
- Azure Key Vault

### 4. 密钥轮换

建议定期轮换以下密钥：

| 密钥类型 | 轮换周期 | 注意事项 |
|---------|---------|---------|
| 数据库密码 | 每年 | 需要提前通知相关人员 |
| JWT 密钥 | 每季度 | 轮换后所有 Token 失效，需要用户重新登录 |
| 阿里云 AccessKey | 每半年 | 需要使用 RAM 子账号 |
| DashScope API Key | 根据需要 | 监控用量，异常时及时更换 |

## 故障排查

### 问题 1：配置未生效

**现象**：修改 Nacos 配置后，服务仍使用旧配置

**可能原因**：
1. 配置未正确发布到 Nacos
2. 服务未开启配置刷新
3. 配置 Data ID 或 Group 不匹配

**解决方案**：
1. 检查 Nacos 控制台配置是否正确发布
2. 检查服务是否配置了 `spring.cloud.nacos.config.refresh-enabled: true`
3. 检查 bootstrap.yml 中的 Data ID 和 Group 配置

### 问题 2：环境变量未生效

**现象**：配置文件中引用的环境变量未正确解析

**可能原因**：
1. 环境变量未正确设置
2. 环境变量名称不匹配
3. 服务启动时未加载环境变量

**解决方案**：
1. 使用 `echo $VAR_NAME`（Linux/Mac）或 `echo %VAR_NAME%`（Windows）检查环境变量
2. 检查配置文件中的环境变量名称是否正确
3. 确保在启动服务前设置环境变量

### 问题 3：Nacos 连接失败

**现象**：服务启动时报 Nacos 连接错误

**可能原因**：
1. Nacos 服务未启动
2. Nacos 地址配置错误
3. 网络问题

**解决方案**：
1. 检查 Nacos 服务是否正常运行
2. 检查 `spring.cloud.nacos.config.server-addr` 配置
3. 检查防火墙和网络连通性

## 安全最佳实践

1. **不要提交 .env 文件到 Git**
   - 将 `.env` 添加到 `.gitignore`
   - 只提交 `.env.example` 模板文件

2. **限制 Nacos 访问权限**
   - 开启 Nacos 认证
   - 使用 RBAC 控制配置读写权限
   - 生产环境使用 HTTPS

3. **使用加密配置**
   - 对于高度敏感的配置，使用 Jasypt 等工具加密
   - Nacos 支持配置加密插件

4. **审计配置变更**
   - 启用 Nacos 配置变更审计日志
   - 定期审查配置变更历史

5. **多环境隔离**
   - 使用 Nacos Namespace 隔离 dev/test/prod 环境
   - 不同环境使用不同的数据库和密钥

## 相关文件

- `.env.example` - 环境变量配置模板
- `application.yaml` - 公共基础配置
- `Echoes--*.yaml` - 各服务配置
- `docs/静态代码审查报告 -20260302.md` - 安全审查报告

---

*文档更新时间：2026-03-02*
*文档版本：v1.0*
