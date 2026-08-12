# Echoes Frontend — Vue 3 Web 应用

Echoes 语音 AI 对话系统的 Web 前端，基于 Vue 3 + Vite 构建，提供语音对话、声音管理、会话管理等功能。

---

## 技术栈

- **框架**：Vue 3（Composition API）
- **构建工具**：Vite 5
- **状态管理**：Pinia
- **路由**：Vue Router 4
- **HTTP 客户端**：Axios
- **国际化**：vue-i18n
- **本地存储**：IndexedDB（idb）
- **类型检查**：TypeScript

---

## 功能模块

| 模块 | 路径 | 说明 |
|---|---|---|
| **认证** | `/auth` | 登录、注册、JWT 管理 |
| **对话** | `/chat` | SSE 流式对话、语音播放、历史记录 |
| **会话管理** | `/sessions` | 会话列表、创建/删除会话 |
| **声音管理** | `/voices` | 声音资产 CRUD、声音克隆、试听 |
| **家庭成员** | `/families` | 成员管理、权限设置 |
| **个人中心** | `/profile` | 用户信息、设置 |

---

## 快速启动

### 1. 安装依赖

```bash
pnpm install
# 或 npm install / yarn install
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

主要配置项：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `VITE_PROXY_TARGET` | 后端 Gateway 地址（Vite 代理目标） | `http://localhost:18080` |
| `VITE_API_BASE` | API 请求前缀 | `/api` |

### 3. 启动开发服务器

```bash
pnpm dev
# 或 npm run dev
```

访问 http://localhost:5173

Vite 开发服务器会自动代理 `/api` 请求到后端 Gateway（配置在 `vite.config.ts`）。

---

## 构建部署

### 生产构建

```bash
pnpm build
```

产物位于 `dist/` 目录，可直接部署到 Nginx/CDN。

### 预览构建产物

```bash
pnpm preview
```

### 类型检查

```bash
pnpm typecheck
```

---

## 目录结构

```
Echoes_Frontend/
├── src/
│   ├── app/                 # 应用初始化
│   ├── assets/              # 静态资源（图片、样式）
│   ├── components/          # 通用组件
│   ├── pages/               # 页面组件
│   │   ├── auth/            # 认证页面
│   │   ├── chat/            # 对话页面
│   │   ├── sessions/        # 会话管理
│   │   ├── voices/          # 声音管理
│   │   ├── families/        # 家庭成员
│   │   └── profile/         # 个人中心
│   ├── services/            # API 服务层
│   │   └── modules/         # 按模块拆分的 API
│   ├── store/               # Pinia 状态管理
│   ├── types/               # TypeScript 类型定义
│   ├── utils/               # 工具函数
│   └── locales/             # 国际化文件
├── public/                  # 公共静态资源
├── .env.example             # 环境变量模板
├── vite.config.ts           # Vite 配置
├── tsconfig.json            # TypeScript 配置
└── package.json
```

---

## 核心流程

### SSE 流式对话

前端通过 `EventSource` 连接 `/api/conversation/chat-stream`，接收四类事件：

1. **message.delta**：文本回复（逐字推送）
2. **emotion**：情绪标签（开心、难过、平静等）
3. **citation**：引用来源（检索到的记忆）
4. **audio**：语音占位（实际音频由后端生成后推送）

```typescript
const eventSource = new EventSource('/api/conversation/chat-stream?sessionId=xxx&turnId=yyy');
eventSource.addEventListener('message.delta', (e) => {
  const delta = JSON.parse(e.data);
  // 追加文本
});
```

### 会话 + 回合管理

- **session_id**：一次完整对话会话（可包含多轮）
- **turn_id**：单轮对话唯一标识（UUIDv7/ULID/Snowflake），客户端生成，保证幂等

### 声音资产绑定

创建会话时可绑定 `voiceAssetId`，该会话后续对话必须使用该音色，禁止回退默认音色（否则返回 `VOICE_NOT_AVAILABLE`）。

---

## API 代理配置

开发环境下，Vite 将 `/api` 请求代理到后端 Gateway：

```typescript
// vite.config.ts
const target = env.VITE_PROXY_TARGET || "http://localhost:18080";

export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target,
        changeOrigin: true,
      }
    }
  }
})
```

生产环境需配置 Nginx 反向代理或使用同域部署。

---

## 状态管理

使用 Pinia 管理全局状态：

- **authStore**：JWT token、用户信息
- **chatStore**：当前会话、消息列表
- **voiceStore**：声音资产缓存
- **sessionStore**：会话列表

---

## 国际化

支持中英文切换（vue-i18n），语言包位于 `src/locales/`：

```
src/locales/
├── en-US.json
└── zh-CN.json
```

---

## 测试

```bash
# 运行单元测试
pnpm test

# 监听模式
pnpm test:watch
```

---

## 开发规范

- **组件命名**：PascalCase（`VoiceCard.vue`）
- **文件命名**：kebab-case（`chat-session.ts`）
- **Commit 规范**：`feat/fix/refactor/docs(scope): message`
- **类型安全**：优先使用 TypeScript，避免 `any`

---

## 已知限制

1. **SSE 兼容性**：IE 不支持 `EventSource`（现代浏览器均支持）
2. **音频播放**：依赖浏览器 `<audio>` 标签，移动端自动播放受限（需用户交互触发）
3. **IndexedDB**：用于本地缓存，Safari 隐私模式下受限

---

## 常见问题

**Q: 启动报端口占用？**  
A: 修改 `vite.config.ts` 中的 `server.port`，或 `pnpm dev --port 5174`。

**Q: API 请求 404？**  
A: 确认后端 Gateway 已启动（`http://localhost:18080`），检查 `.env` 中的 `VITE_API_BASE_URL`。

**Q: SSE 连接断开？**  
A: 检查网络代理/防火墙配置，SSE 需保持长连接。

---

## License

[Apache License 2.0](../LICENSE)
