# Echoes Frontend

Vue 3 + Vite 前端。语音对话、声音管理、会话管理。

## 技术

Vue 3 (Composition API)、Vite、Pinia、Vue Router、Axios、vue-i18n

## 启动

```bash
pnpm install
cp .env.example .env
pnpm dev          # http://localhost:5173
```

`/api` 请求由 Vite 代理到后端 Gateway（`VITE_PROXY_TARGET`，默认 `http://localhost:18080`）。

## 命令

```bash
pnpm dev          # 开发
pnpm build        # 构建
pnpm typecheck    # 类型检查
pnpm test         # 单元测试
```

## 目录

```
src/
├── pages/        # 页面（auth/chat/sessions/voices/families/profile）
├── components/   # 通用组件
├── services/     # API 层
├── store/        # Pinia
├── types/        # TS 类型
└── locales/      # i18n
```

## 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `VITE_PROXY_TARGET` | 后端 Gateway 地址 | `http://localhost:18080` |
| `VITE_API_BASE` | API 前缀 | `/api` |
