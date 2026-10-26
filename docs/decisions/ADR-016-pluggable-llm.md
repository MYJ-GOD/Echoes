# ADR-016：可插拔 LLM 后端与首启按需供给

- 状态：**已定**（2026-10-26，产品改向）
- 影响范围：4.4 LLM 契约实现、3.4 设置拉取语义、16.1 隐私边界、7.3 部署供给、阶段 3 首启引导
- 前置：[ADR-011](ADR-011-packaging-split.md)（split-binary）、[ADR-001](ADR-001-llm-baseline.md)（本地 qwen3:8b 基准）

## 背景

原方案把「本地全栈」写死：Ollama + CosyVoice2 + faster-whisper + bge 全部随装。用户提出：

1. 安装包只装**本体**，模型/运行时首次启动再按需下载；
2. TTS 与 LLM 都允许 **API key** 或**本地部署**二选一。

这会动到已完成的克隆链路与隐私红线，需要先明确边界再实现。

## 决策

### 1. 后端矩阵（v1 收敛版）

| 能力 | v1 结论 | 理由 |
| --- | --- | --- |
| LLM | **本地 Ollama / OpenAI 兼容云端**二选一 | 一套 `openai` 客户端同时覆盖 DeepSeek、Kimi、硅基流动、LM Studio、vLLM |
| TTS | **仅本地 CosyVoice2** | 克隆（`add_zero_shot_spk` + campplus 质检）是 CosyVoice2 专属；云端预设音色会让阶段 0–2 的克隆能力归零 |
| ASR | **仅本地 faster-whisper** | 语音样本出网是另一个隐私故事；v1 不做 |
| 嵌入/记忆 | **始终本地 bge** | 记忆是陪伴体验的核心，不能因为选了云端 LLM 就消失 |

**关键推论**：`torch` 是本地 TTS 与本地 bge 的共同前置，**无论 LLM 选云端与否都省不掉**。
因此 ADR-011 的 `cpu` / `cuda126` 档位不变，不做「按组件分层下载」——那会带来重叠轮子的
复杂度，却换不来体积收益。

真正省下来的是：安装包不含 torch/权重（~88MB），模型与运行时在首启下载，且可以选择
**不装 Ollama、不拉 4.8GB 的 qwen3:8b**（云端 LLM）。

### 2. 设置键（3.4 拉取语义不变）

写入归壳（固定 SQL），sidecar 每轮读取；**不新增协议消息**。

| 键 | 取值 | 说明 |
| --- | --- | --- |
| `llm_provider` | `mock` / `ollama` / `openai` | `openai` 同时表示云端与本机兼容端点 |
| `llm_model` | 字符串 | `qwen3:8b` / `deepseek-chat` / … |
| `llm_base_url` | URL 或空 | 填到 `/v1` 为止；仅 `openai` 使用 |
| `privacy_mode` | bool | 见 §3 |

**API key 不入库**（4.4 明文禁令）。壳写 Windows 凭据管理器，sidecar 只读。

### 3. 隐私矩阵（16.1）

| provider \ privacy | true | false |
| --- | --- | --- |
| `mock` / `ollama` | 允许（本机） | 允许 |
| `openai` + 环回地址 | 允许（不出网） | 允许 |
| `openai` + 公网地址 | **拒绝** | 允许 |

拒绝是双层的：`write_settings` 直接报错（前端也自动取消勾选），Router 在 `generate`
处再拦一次并抛 `LLM_PROVIDER_UNAVAILABLE`。**不静默退回本地**——那会把用户的隐私选择
变成假的。

`openai` 的实例名按 base_url 判定：公网 → `cloud:openai`，环回 → `openai`。这沿用 4.4
既有约定，摘要/记忆抽取据此判断要不要压住。

### 4. 密钥存储与跨语言互操作

- 位置：Windows 凭据管理器，`target/service = "Echoes"`，`user = "llm-api-key"`。
- 壳：`keyring` crate 3.x，**必须** `Entry::new_with_target(SERVICE, SERVICE, ACCOUNT)`
  并启用 `windows-native` 特性（默认特性不含后端，会静默落到内存 mock）。
- sidecar：python `keyring.get_password(SERVICE, ACCOUNT)`。
- 两侧口径必须都是「target = service」：crate 默认是 `user.service`，python-keyring 会退到
  `user@service` 复合名——不对齐就会「写着成功、读着为空」。已实测双向互通。
- 前端只拿 `hasKey`（bool），key 输入框永不回显。
- 冻结形态：PyInstaller 需 `--collect-submodules keyring.backends` + `win32ctypes`；
  已实测冻结 exe 取到 key 并打到真实 401。

### 5. 错误码

新增 `LLM_KEY_MISSING`（只追加，3.4.1 允许）。HTTP 401/429/5xx 折成
`LLM_PROVIDER_UNAVAILABLE`，message 带状态码，前端按 code 渲染。

## 备选方案（未采纳）

- **运行时 pip 解析**：冻结进程里证书、构建隔离、断点续传全要另造；ADR-011 已选预构建档案。
- **DPAPI 加密文件**：能少一个依赖，但要两端各写一套加解密；凭据管理器是系统级标准答案。
- **云端 TTS（含克隆）**：ElevenLabs 一类要样本出网 + 授权确认，且与「离线陪伴」定位冲突；v1 延后。
- **云端 ASR**：同上，延后。
- **按组件分层下载**：见 §1 推论——torch 省不掉，分层只增加复杂度。

## 后果

- 首启引导必须做：检测硬件 → 推荐 `cpu`/`cuda126` → 下载运行时与权重 → 配置 LLM（本地 Ollama 或云端 key）→ 写 `first_run_done`。
- 安装器只装本体（~88MB sidecar + 壳），体积检查口径随之变化。
- 云端 LLM 的记忆/摘要不再被静态隐私开关压住：边界由设置校验 + Router 阻断承担（否则云端用户会静默失去记忆）。
- 仍需：运行时档案托管地址、真档位构建、首启向导、安装器、CI。

## 待办

1. 首启向导（消费 `runtime_manager.py list/install/verify` + 模型管理器 + 本 ADR 的设置键）。
2. 安装器（NSIS/MSI）。
3. 云端连通性测试按钮（`GET /models` 已在 `health()` 实现，壳侧只差一个命令）。
4. 多 provider 的 key 命名（当前单条 `llm-api-key`；多云端并存时按 provider 分账户）。
