# 前端验收记录

> 规范：[前端重设计.md](../前端重设计.md)
> 基线截图：`tmp/ui-shots/2026-11-02/`（本地生成，不进仓库）

## 2026-11-02 · D1（P0 + P1）

### 交付

| 项 | 位置 | 状态 |
|---|---|---|
| 新 token | `src/design/tokens.css` | ✅ 仅作用于 `[data-skin="next"]` |
| 基础样式 | `src/design/base.css` | ✅ reset / 焦点 / 滚动条 / reduced-motion |
| 基础组件 | `src/components/ui/` | ✅ 19 个 primitive |
| 设计沙盒 | `src/pages/Design.vue` | ✅ 仅开发态路由 `/#/design` |
| 截图脚本 | `scripts/ui-shot.mjs` | ✅ `npm run ui:shots` |
| 规范 | `docs/前端重设计.md` | ✅ v0.1 |

### 验证

- `npm run build`（`ipc:check` + `vue-tsc --noEmit` + `vite build`）通过。
- 生产构建没有包含 `Design.vue`（dev-only 动态路由被摇掉）。
- 截图 5 张：1100×760 / 800×600 × light / dark，外加 1100×760 compact。
- 旧页面未改视觉：`Chat.vue` / `Memory.vue` / `Hud.vue` / `FirstRun.vue` / `themes.css` 均未动；只新增了 `main.ts` 的 import、`App.vue` 对 `/design` 隐藏标题栏、`router` 的 dev 路由。

### 截图

| 文件 | 内容 |
|---|---|
| `design-light-1100x760.png` | 浅色 · 对话示例 + 色彩 + 字号 |
| `design-dark-1100x760.png` | 深色 · 同上 |
| `design-light-800x600.png` | 窄窗 · 单列堆叠 |
| `design-dark-800x600.png` | 窄窗 · 深色 |
| `design-light-1100x760-compact.png` | 紧凑密度 |

### 已知缺口

- 还没把新 skin 挂到主窗口；P2 才替换 `data-theme`。
- 对话页、历史页、记忆页、声音页仍是旧实现。
- 命令面板、字体子集、真实数据态未做。
- 对比度只做了 token 级人工检查，尚未加自动断言。
- `ui:shots` 依赖本机 Edge/Chrome；其他机器可用 `EDGE_PATH` / `CHROME_PATH` 指定。

### 下一步（D2）

1. 建 `AppShell` + `TitleBar` + `SideRail`。
2. 注册五页路由；`/settings` 作为独立窗口回退。
3. 主窗改 1100×760 / 最小 800×600；设置窗改 720×760。
4. 旧页面逐步挂到新 shell，业务逻辑不动。

---

## 2026-11-02 · D2（P2）

### 交付

| 项 | 位置 | 状态 |
|---|---|---|
| 应用壳 | `src/components/layout/AppShell.vue` | ✅ 标题栏 + 侧栏 + 主区；由 `App.vue` 持有，路由切换不重挂 |
| 自绘标题栏 | `AppTitleBar.vue` | ✅ 36px、窗口控制、拖拽区、几何恢复 |
| 侧栏 | `AppSideRail.vue` | ✅ 五页入口 / 设置 / 折叠；≤980px 自动收成图标 |
| 页头 | `PageHeader.vue` | ✅ 标题 / 描述 / 右侧动作 |
| 路由 | `src/router/index.ts` | ✅ `/`、`/history`、`/memory`、`/voice`、`/about`、`/settings`、`/hud` |
| 对话页 | `ChatPage.vue` + `Chat.vue` 的 `embedded` | ✅ 旧逻辑不动；隐藏品牌词/历史/设置图标，放宽到 860px |
| 历史页 | `HistoryPage.vue` | ✅ 会话列表 + 搜索 + 只读预览 + 继续入口 |
| 记忆页 | `MemoryPage.vue` | ✅ 旧 `Memory.vue` 挂进新壳（内容 P4 重做） |
| 声音页 | `VoicePage.vue` | ✅ 音色列表 / 切换 / 改名 / 删除；克隆入口回设置窗口 |
| 关于页 | `AboutPage.vue` | ✅ 版本 / 备份 / 诊断包 / 隐私说明 |
| 设置回退 | `SettingsFallbackPage.vue` | ✅ 独立窗口打不开时整页回退 |
| 窗口几何 | `tauri.conf.json` / `open_settings_window` | ✅ 主窗 1100×760（最小 800×600）；设置窗 720×760（最小 640×700） |
| 主题桥接 | `useSkinMode.ts` + `DsSkin.vue` | ✅ 旧 `data-theme` 映射到新 light/dark，避免两套主题打架 |

### 验证

- `npm run build`（`ipc:check` + `vue-tsc --noEmit` + `vite build`）通过。
- 截图：6 个主页面 × 1100×760 / 800×600 × light / dark（24 张）；设置窗口 720×760 × light / dark（2 张）；设计沙盒 1100×760 × light / dark（2 张）。
- 800×600 下侧栏自动收成图标，页面无横向溢出（截图目测）。
- 生产构建仍不包含 `Design.vue`；`AboutPage` 的 `@tauri-apps/api/app` 单独成 0.22KB chunk。
- 旧业务逻辑未改：Chat 的 PTT / 发送 / 打断 / 历史抽屉 / 设置面板仍在原文件里。

### 截图

主页面（`tmp/ui-shots/2026-11-02/`）：

| 文件 | 内容 |
|---|---|
| `chat-{light,dark}-1100x760.png` | 新壳 + 旧对话页 |
| `chat-{light,dark}-800x600.png` | 窄窗 + 折叠侧栏 |
| `history-{light,dark}-{1100x760,800x600}.png` | 历史列表 / 只读预览 |
| `memory-{light,dark}-{1100x760,800x600}.png` | 旧记忆页挂新壳 |
| `voice-{light,dark}-{1100x760,800x600}.png` | 音色列表 |
| `about-{light,dark}-{1100x760,800x600}.png` | 关于页 |
| `settings-{light,dark}-{1100x760,800x600}.png` | 设置回退页 |
| `settings-window-{light,dark}-720x760.png` | 真实设置窗口尺寸下的旧设置面板 |
| `design-{light,dark}-1100x760.png` | 设计沙盒 |

### 已知缺口（D3/P4 收口）

- **Chat 仍是旧布局**：内容列 860px 了，但空态、输入区、PTT 还是旧结构；深色下旧 `nocturne` 会把输入区翻到 PTT 上方，明暗布局不一致。P3 拆 `Chat.vue` 时一并解决。
- **历史「继续对话」只切会话，不回填线程**：`useHistory` 的 `replaceMessages` 在历史页是空实现；回对话页后视觉线程为空，但 sidecar 的活动会话已切换。P3 接回 ChatPage 的线程加载。
- **记忆页仍是旧实现**：原始 `TypeError` 文本会直接显示；P4 换成 `DsErrorState` + 新卡片。
- **设置窗口内容仍是旧面板**：4 个主题卡还是 3+1 网格；P4 换成新的分组导航 + 3 个主题选项。
- **声音克隆**仍回设置窗口；P4 再决定是否把克隆录音搬进声音页。
- 命令面板、字体子集、自动对比度断言未做。

### 下一步（D3）

1. 拆 `Chat.vue`：`MessageList` / `MessageItem` / `Composer` / `PttButton` / `ChatHeader`。
2. 空态、消息节奏、输入区、PTT 按 [前端重设计.md](../前端重设计.md) §5.1 重做。
3. 回对话页时加载活动会话最近 N 轮，补上历史页「继续对话」的断点。
4. 把旧 `letterhead` / 设置抽屉从对话页移除，设置只走独立窗口。

---

## 2026-11-02 · D3（P3）

### 交付

| 项 | 位置 | 状态 |
|---|---|---|
| 对话页眉 | `src/components/chat/ChatHeader.vue` | ✅ 名字 / 状态 / 隐私 / 音色 / 停止 / 恢复 |
| 消息项 | `src/components/chat/MessageItem.vue` | ✅ 时间栏 + 正文；她的衬线左声纹、用户的次级表面、打断 / 错误提示 |
| 输入区 | `src/components/chat/ChatComposer.vue` | ✅ 一个表面：PTT + 自适应 textarea + 发送 + 回声线 + 只读/重试/编辑 |
| PTT | 复用 `DsPttButton` | ✅ 40px；idle / listening / busy（打断）/ disabled |
| 空态 | `Chat.vue` + `DsEmptyState` | ✅ 居中的「她还在听。」+ 3 个开场建议 |
| 线程回填 | `Chat.vue::loadRecentThread` | ✅ 挂载与 hello 时加载活动会话最近 40 轮；历史页「继续对话」用 `sessionStorage` 交接 |
| 旧主界面清理 | `Chat.vue` | ✅ 主对话不再渲染旧 letterhead / 历史抽屉 / 旧 composer；设置窗口仍复用旧设置面板 |
| 视觉回归入口 | `#/?demo=1` | ✅ 仅开发态；截图脚本支持 `--routes chat-demo` |

### 验证

- `npm run build`（`ipc:check` + `vue-tsc --noEmit` + `vite build`）通过。
- 聊天页截图：空态 / 有内容（含打断 + 错误条）× light/dark × 1100×760 / 800×600。
- 800×600 下侧栏收成图标，消息栏、输入区、错误条无横向溢出。
- 看板：`chat-light-1100x760.png`、`chat-dark-1100x760.png`、`chat-demo-{light,dark}-1100x760.png`。

### 已知缺口（P4 收口）

- `Chat.vue` 仍保留旧设置面板和大量已失效的 CSS（letterhead / history / composer / msg）；视觉不再引用，但代码还没删。
- 设置窗口内容仍是旧面板（4 个主题卡 3+1 网格）。
- 记忆页仍是旧实现，原始异常文本会直接显示。
- `loadRecentThread` 没有在真机 sidecar 上跑过；截图是浏览器 + mock demo。
- 命令面板、字体子集、自动对比度断言未做。

### 下一步（D4）

1. 设置窗口重做：左侧分组 + 3 个主题选项 + 引擎/设备/声音/数据分区；复用 `useSettings`，不改 IPC。
2. 记忆页重做：`DsErrorState` / `DsEmptyState` / 新卡片 + 来源回溯。
3. 清理 `Chat.vue` 的失效 CSS 和历史残留，把设置面板从 Chat 彻底拆出。
4. 真机 `tauri dev` 跑一次：回填线程、历史继续对话、设置窗口尺寸。

---

## 2026-11-02 · D4（P4 第一部分）

### 交付

| 项 | 位置 | 状态 |
|---|---|---|
| 记忆页 | `src/pages/MemoryPage.vue` | ✅ 新卡片 / 搜索 / 分类筛选 / 手动添加 / 批量导入 / 合并 / 来源回溯 / 空态 / 错误态 |
| 记忆错误 | `useMemory` 文案出口 | ✅ 原始异常不再直接显示；统一为「操作没有完成…」 |
| 设置窗口分组 | `Chat.vue` + `.settings-window` 布局 | ✅ 左侧 7 组导航 + 单节滚动 + 720×760 |
| 主题 | `THEMES` / `main.ts` / `themes.css` | ✅ 3 项（跟随系统 / 浅色 / 深色），3 列不再孤行；移除 desktop 皮肤 |
| 主题同步 | `onWindowFocus` | ✅ 设置窗口改主题后，主窗口回到前台时应用 |
| 保留能力 | 旧设置面板 | ✅ 引擎 / 密钥 / 模型清单 / 音频设备 / 音色克隆 / 数据备份 / 快捷键 / 首启向导仍在 |

### 验证

- `npm run build`（`ipc:check` + `vue-tsc --noEmit` + `vite build`）通过。
- 记忆页截图：1100×760 / 800×600 × light/dark。
- 设置窗口截图：720×760 × light/dark（外观页）。
- 记忆页在无 sidecar 时显示统一错误文案，不再显示 `TypeError`。
- 800×600 下记忆工具条、添加行、分类筛选不横向溢出。

### 已知缺口

- 设置窗口的表单控件仍是旧标记（`.field` / `.sheet` 类），只是套进了新布局；P5 再换成 `DsField` / `DsInput` / `DsButton`。
- 设置窗口没有 sticky 保存条；保存按钮仍在「引擎与启动」段内。
- 只有「外观」做了截图；引擎 / 音频 / 音色 / 数据 / 快捷键段的功能保留但未逐段视觉验收。
- 记忆页的编辑 / 合并仍用 `window.prompt`，没有自定义对话框。
- 克隆、音频设备、备份还原未上真机。

### 下一步（D5）

1. 把设置面板从 `Chat.vue` 拆成 `SettingsWindow` + 分组组件，表单换成 primitive。
2. sticky 保存条 + 每项重置 + 未保存提示。
3. 清理 `Chat.vue` 里失效的 letterhead / history / composer / msg CSS。
4. 真机 `tauri dev` 跑：设置窗口尺寸、记忆读写、克隆、历史继续对话。

---

## 2026-11-02 · D5（P5 第一部分）

### 交付

| 项 | 位置 | 状态 |
|---|---|---|
| 独立设置窗口 | `src/components/settings/SettingsWindow.vue` | ✅ 7 组（外观 / 人设 / 引擎与启动 / 声音与设备 / 数据与隐私 / 快捷键 / 关于） |
| 表单 primitive | `DsField` / `DsInput` / `DsTextarea` / `DsSelect` / `DsCheckbox` / `DsSwitch` / `DsSegmented` / `DsButton` | ✅ 设置窗口不再使用旧 `.field` 标记 |
| sticky 保存条 | `settings__footer` | ✅ 未保存状态 + 关闭 + 保存设置；保存人设与设置 |
| 主题 | `useTheme` + 3 项分段控件 | ✅ system / light / dark；旧 `paper/nocturne` 仍兼容 |
| 引擎 | 预设 / LLM / ASR / TTS / 密钥 / 逐链同意 / 双显 / 模型清单 | ✅ 复用 `useSettings`，不改 IPC |
| 声音 | 音色列表 / 切换 / 改名 / 删除 / 克隆（3–6 秒）/ 进度 | ✅ 克隆录音与进度在设置窗口内完成 |
| 音频 | 输入 / 输出 / 音量 / 电平 / 试听 | ✅ 复用 `useAudioDevices` |
| 数据 | 隐私模式 / 导出 / 备份 / 导入 / 诊断 / 还原 / 彻底删除 | ✅ 复用 `useData`，异常统一翻译 |
| 启动与快捷键 | 自启 / 关闭到托盘 / 通知 / 说话快捷键 / hold-toggle | ✅ |
| 旧面板清理 | `Chat.vue` | ✅ 旧设置 sheet 模板已删除（约 28k 字符），主对话不再 import `PERSONA_PRESETS` 设置面板 |

### 验证

- `npm run build`（`ipc:check` + `vue-tsc --noEmit` + `vite build`）通过。
- 设置窗口 720×760：外观 light/dark；引擎、声音与设备、数据与隐私、快捷键、关于 light。
- 聊天页回归：空态 1100×760 light/dark，确认拆设置面板后主对话未受影响。
- 独立窗口走 hash 路由 `#/settings` 渲染 `SettingsWindow`（`?window=settings` 那套 query 检测已删除）；窗口由 Rust 在 `setup` 里预创建并隐藏，关闭只隐藏不销毁。
- 原始 `TypeError` 不再出现在音色 / 音频 / 备份状态里。

### 已知缺口（P6 收口）

- `Chat.vue` 仍保留旧设置脚本状态与旧 CSS（`.sheet` / `.field` / 主题卡 / 数据区等），模板已删但代码没清完；CSS 仍有 ~10k 行级旧块。
- 设置窗口没有逐项「未保存」标记；sticky 条只显示最后一次保存结果。
- `/settings` 整页回退仍是 D2 的简单重试页，不是 `SettingsWindow`。
- 克隆、音频设备、备份还原、快捷键注册未上真机；浏览器截图里系统集成会显示失败是预期。
- 640×700 最小宽度未做截图验收；命令面板、密度、字体子集未做。

### 下一步（D6）

1. 清理 `Chat.vue` 旧设置脚本与失效 CSS；把主对话组件收口。
2. 设置窗口接 `data-density`，补 640×700 与键盘路径验收。
3. 命令面板（`Ctrl+Shift+P`）+ 全局搜索。
4. 真机 `tauri dev`：设置窗口、克隆、记忆读写、历史继续对话。

---

## 2026-11-02 · D6（P6 第一部分）

### 交付

| 项 | 位置 | 状态 |
|---|---|---|
| 命令面板 | `src/components/layout/CommandPalette.vue` | ✅ `Ctrl+Shift+P`；去对话/历史/记忆/声音/关于/设置/停止回复；↑↓ / Enter / Esc |
| 全局挂载 | `App.vue` | ✅ 只在主壳路由出现；HUD、设置窗口、设计沙盒不挂 |
| 空态/搜索 | 命令面板 | ✅ 实时过滤、无结果提示、首项高亮、鼠标悬停同步 |
| 640 宽验收 | 设置窗口 | ✅ 640×700 light/dark 截图，导航与外观页不溢出 |
| Rust 检查 | `cargo check --manifest-path src-tauri/Cargo.toml` | ✅ 通过（53s） |
| 旧设置模板 | `Chat.vue` | ✅ 旧 sheet 模板已删；主对话只保留消息/输入/恢复/首启 |

### 验证

- `npm run build`（`ipc:check` + `vue-tsc --noEmit` + `vite build`）通过。
- `cargo check` 通过，窗口尺寸常量与 Rust 外壳可编译。
- 命令面板截图：1100×760 × light/dark。
- 设置窗口 640×700 × light/dark。
- 聊天空态 / 有内容回归通过。

### 已知缺口

- `Chat.vue` 仍保留旧设置脚本状态（useData / autostart / model inventory / clone 等）和大量失效 CSS；模板已删，但代码没清完。
- `data-density` 还没有接到主壳；紧凑密度只在设计沙盒里可用。
- `/settings` 整页回退仍是 D2 的简单重试页，不是完整设置窗口。
- 命令面板还没有全局搜索（搜索会话原文/记忆）的入口，只是导航 + 动作。
- 没有跑完整 `tauri dev` UI（只跑了 `cargo check` 与浏览器截图）；克隆、设备、备份未上真机。
- 对比度、键盘全路径、屏幕阅读器还没有自动化断言。

### 下一步（D7）

1. 清 `Chat.vue` 旧脚本与失效 CSS，把 `useData` / 设置状态 / clone 残留移出。
2. `data-density` 接到 AppShell + SettingsWindow；补 800×600 / 640×700 键盘路径。
3. 命令面板接全局搜索（历史原文 + 记忆）。
4. 真机 `tauri dev` 跑一轮设置窗口、克隆、历史继续对话。

---

## 2026-11-02 · D7（P6 收口）

### 交付

| 项 | 位置 | 状态 |
|---|---|---|
| 密度 | `useDensity.ts` + `DsSkin` + 设置窗口 | ✅ 舒适 / 紧凑；`data-density` 只改间距/行高；跨窗口 storage 同步 |
| 命令面板全局搜索 | `CommandPalette.vue` | ✅ 输入非空时出现「在历史中搜索」/「在记忆中搜索」 |
| 历史搜索入口 | `HistoryPage.vue` | ✅ `?q=` 自动填入并执行全文搜索 |
| 记忆搜索入口 | `MemoryPage.vue` | ✅ `?q=` 自动填入搜索框 |
| Chat 清理 | `Chat.vue` | ✅ 3891 → **1435** 行；模板 163 行、CSS 363 行；`useData` / clone / 设置状态 / 旧抽屉全部移除 |
| 旧 CSS 清理 | `Chat.vue` | ✅ 删除 letterhead / history / preview / composer / settings / model / voice 等失效块，CSS 87.5 → 71.6KB |
| Rust 外壳 | `cargo check` | ✅ 通过（D6 已跑；本轮无 Rust 变更） |

### 验证

- `npm run build`（`ipc:check` + `vue-tsc --noEmit` + `vite build`）通过。
- 聊天页 1100×760 / 800×600 × light/dark 截图通过；拆 clone / 设置状态后 PTT 空态未回退。
- 设置窗口 720×760 / 640×700 × light/dark 截图通过；外观页包含主题与密度。
- 命令面板 1100×760 × light/dark 截图通过；输入查询后新增两个搜索命令（代码路径已接）。

### 已知缺口

- 没有跑完整 `tauri dev` UI：只跑了 `cargo check` + 浏览器截图；PTT、克隆、设备、备份仍未上真机。
- `/settings` 整页回退仍是简单重试页；独立设置窗口正常时不会走到。
- 记忆编辑 / 合并仍用 `window.prompt`；没有自定义对话框。
- 命令面板的搜索只把查询词带进历史/记忆页，不是面板内直接显示结果。
- 对比度、屏幕阅读器、完整键盘路径还没有自动化断言。
- `Chat.vue` 仍有 `FirstRun` / 恢复面等旧组件的内联逻辑；它们视觉已接新 token，但结构没有继续拆。

## 2026-11-02 · D8（回退与记忆对话框）

### 交付

| 项 | 位置 | 状态 |
|---|---|---|
| `/settings` 整页回退 | `SettingsWindow.vue` + `App.vue` + router | ✅ `inline` 模式直接渲染完整设置，不再显示重试页 |
| 回退关闭行为 | `SettingsWindow.vue` | ✅ inline 下「返回对话」回 `/`；独立窗口仍走 `closeWindow` |
| 回退删除 | `SettingsFallbackPage.vue` | ✅ 文件已删除，路由直接指向 `SettingsWindow` |
| 记忆编辑对话框 | `DsTextDialog.vue` + `MemoryPage.vue` | ✅ 应用内编辑，不再 `window.prompt` |
| 记忆合并对话框 | `DsTextDialog.vue` + `useMemory.mergeFacts` | ✅ 预填合并文本、校验、busy/error |
| 记忆删除确认 | `DsConfirmDialog.vue` + `useMemory.deleteFact` | ✅ 应用内确认，不再 `window.confirm` |
| 无 UI 提交函数 | `useMemory.ts` | ✅ `updateFact` / `mergeFacts` / `deleteFact` |
| Teleport 主题修复 | `DsDialog.vue` / `DsToast.vue` | ✅ 传送到 body 后仍带 `data-skin` / `data-mode`，不再透明 |

### 验证

- `npm run build` 通过。
- `/settings` 1100×760 / 800×600 × light/dark 截图通过；关闭按钮不再误关主窗口。
- 记忆编辑对话框 1100×760 × light/dark、删除确认 1100×760 light 截图通过。
- 对话框焦点进入输入框/取消按钮，Esc 关闭后焦点回到触发按钮。
- 记忆页不再调用原生 prompt/confirm。

### 已知缺口

- 合并对话框只验证了组件路径，没有在真实数据上点选两条执行合并。
- 会话改名、音色改名仍用 `window.prompt`（本轮只收记忆页）。
- 没有真机 sidecar 验证保存/合并/删除的实际落库。
- `/settings` inline 模式没有独立窗口的 native 标题栏，属于预期。

---

## 2026-11-02 · D9（命令面板内联搜索）

### 交付

| 项 | 位置 | 状态 |
|---|---|---|
| 面板内搜索 | CommandPalette.vue | ✅ 输入后 200ms debounce，分组显示命令 / 历史 / 记忆 |
| 历史结果 | ipc.historySearch | ✅ 最多 6 条，显示轮次、会话、日期；Enter 打开对应轮次 |
| 记忆结果 | ipc.listMemories(200) 缓存 + 客户端过滤 | ✅ 最多 6 条，显示分类、日期；Enter 跳到对应事实 |
| 深链 | HistoryPage.vue | ✅ ?q=&turn= 自动搜索并打开只读预览；同页 query 变化也响应 |
| 深链 | MemoryPage.vue | ✅ ?focus= 滚动到卡片并高亮 2.4s；同页 query 变化也响应 |
| 焦点恢复 | CommandPalette.vue | ✅ 关闭后焦点回到打开前的元素 |
| 请求竞态 | CommandPalette.vue | ✅ 请求序号丢弃过期响应 |

### 验证

- `npm run build` 通过。
- 命令面板 1100×760 light/dark：查询「爵士」显示历史/记忆两组结果。
- 历史页 ?q=&turn=、记忆页 ?focus= 代码路径已接；browser 无 sidecar 时只显示统一的搜索失败提示。
- 开发态 palette-demo=1 固定数据用于截图，不进生产逻辑。

### 已知缺口

- 搜索请求未在真机 sidecar 上验证；截图使用 dev fixture。
- 历史最多 6 条、记忆最多 200 条内存过滤；更大数据量需要后端 memory search。
- 面板内不显示命中高亮片段，只截断文本。

## 2026-11-02 · D10（对比度 / axe / 键盘门禁）

### 交付

| 项 | 位置 | 状态 |
|---|---|---|
| 对比度门禁 | `scripts/check-contrast.mjs` | ✅ 从 token 取实际计算值，12 对颜色 × light/dark，正文 4.5、大字/控件 3.0 |
| axe 门禁 | `scripts/check-a11y.mjs` + `axe-core` devDependency | ✅ 7 个页面 × light/dark，WCAG 2.0/2.1 A/AA；serious/critical 失败即退出 |
| 键盘门禁 | `scripts/check-keys.mjs` | ✅ 主壳 Tab 顺序、焦点环、命令面板焦点恢复、设置导航、记忆对话框焦点陷阱 |
| npm 入口 | `package.json` | ✅ `check:contrast` / `check:a11y` / `check:keys` / `check` |
| 对比度修复 | `tokens.css` | ✅ 浅色 `--ink-3` 加深、light/dark `--rule-strong` 加深到 3:1 |
| 语义修复 | `Chat.vue` / `DsSelect.vue` / `themes.css` | ✅ 去掉 `ol[role=log]`；`DsSelect` 的 label 落到 select；删除会污染 code 背景的旧主题规则 |

### 验证

- `npm run check` 全绿：对比度通过、axe 14 个页面/主题组合通过、键盘 10 项通过。
- 对比度门禁修掉的真实问题：浅色 `--ink-3` 4.32 → 4.54；控件边框 light 1.52 / dark 1.79 → 3.24 / 3.34。
- axe 修掉的真实问题：聊天页 `li` 因 `role=log` 失去列表语义；记忆页 select 无名字且 `aria-label` 落在 wrapper 上。
- 键盘门禁验证：命令面板 Esc 后焦点回到打开前元素；记忆对话框 Tab 锁定、Esc 关闭并恢复触发按钮焦点。

### 已知缺口

- axe 跑在浏览器 + 无 sidecar 状态，不覆盖真实引擎错误态；也不替代 NVDA/Narrator 人工朗读验证。
- 键盘脚本覆盖主路径，不覆盖所有页面/所有控件；方向键导航目前只验证命令面板。
- CI 还没有接这三个门禁；目前是本地脚本。
- 对比度只测 token 对，没有穷举每个组件的实际 computed 背景。

---

## 2026-11-02 · 记忆页 Obsidian 式三栏

### 交付

| 项 | 位置 | 状态 |
|---|---|---|
| 三栏布局 | `src/pages/MemoryPage.vue` | ✅ 左分类树 / 中详情 / 右关联 |
| 反链 | `memory_usage` | ✅ 右栏「被回复用过」按会话与轮次分组 |
| 同类别邻近 | `MemoryView.category` | ✅ 右栏分组列表，可点击切换 |
| 新建 / 批量 | 中栏表单 | ✅ 不再占用左栏列表顶部 |
| 合并模式 | 左栏行首复选框 | ✅ 底部固定「已选 n 条 / 合并所选」 |
| 折叠分组 | 左栏 | ✅ 搜索时自动展平 |
| 窄屏 | `@media (max-width: 1080px)` | ✅ 隐藏右栏，保留左树 + 中详情 |

### 验证

- `npm run build` 通过。
- `npm run check` 全绿：对比度、axe 14 个页面/主题组合、键盘 10 项。
- `ui:shots` 覆盖 memory-demo 1100×760 与 800×600 的 light/dark 截图，布局无溢出。

### 已知缺口

- 边是从 `turn_memory_ref` 与 `source_session_id` 推导的，不是人工标注或语义相似度。
- 窄屏右栏直接隐藏，未折叠到中栏；800×600 下看不到反链。
- 反链依赖 `memory_usage`，只覆盖“被回复引用过”，不覆盖“被合并/取代”的历史链路。

## 2026-11-02 · 记忆关系图谱

### 交付

| 项 | 位置 | 状态 |
|---|---|---|
| 图查询 | `src-tauri/src/memory.rs` `graph()` | ✅ co-used + same-session |
| 命令注册 | `src-tauri/src/lib.rs` `memory_graph` | ✅ |
| 前端图 | `src/components/memory/MemoryGraph.vue` | ✅ Canvas + d3-force |
| 交互 | 拖拽 / 缩放 / 平移 / hover / 点击 | ✅ |
| 入口 | 左栏「列表 / 图谱」+ `?graph=1` | ✅ |
| 可访问性 | canvas `role="img"` + aria-label | ✅ axe 通过 |

### 验证

- `npm run build` 通过；bundle 增加约 21KB（d3-force）。
- `npm run check` 全绿；axe 16 组含 memory-graph。
- Rust `cargo test memory::tests`：5 项通过（含两条图边测试）。

### 已知缺口

- 边不是语义相似度：没有 `turn_memory_ref` 的库只有 same-session 链。
- 图没有持久化关系表，不能手工加边/删边。
- Canvas 不支持键盘遍历节点；键盘用户仍需用列表视图。
