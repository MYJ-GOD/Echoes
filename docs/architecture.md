# Echoes 重构开发文档 v1.4.1

本文档是重构的唯一执行依据。所有讨论中已收敛的决策直接写入，不再重复论证过程；未决事项标注为「决策待定」并给出收敛路径。文档本身随阶段推进迭代，但第 4 节的接口契约在阶段 0 冻结后，后续变更需走变更记录。

**变更记录**

- **v1.4.1 相对 v1.4**（阶段 0 第一周实施中发现的契约缺口，走 12.2 冻结层变更）：3.4 stdio 事件清单追加 `assistant_text` 帧——v1.4 的控制面只有用户侧转写（`asr_partial`/`asr_final`），LLM 回复文本无承载帧，第一周验收「文本→LLM→文本」的文本侧在壳/前端没有数据源。新帧 `{type, session_id, text, t}`：`text` = 截至当前的全量回复文本，流式期间逐帧递增（UI 直接替换渲染），收尾边界由同 turn 的 `turn_complete` 界定；不携带 `turn_seq`（归属当前在途 turn，3.5 单会话单在途 turn）。schema/golden/壳侧解析同 patch 落地；纯追加，旧端 extra=ignore 兼容（3.4 兼容规则）。

- **v1.4.2 相对 v1.4.1**（CosyVoice2 搬运专项启动，新增 ADR-014，不动冻结契约）：15.1 CosyVoice2 行钉死上游锚——FunAudioLLM/CosyVoice main `074ca6d`（2026-05-26）+ Matcha-TTS 子模块 pin `dd9105b3`，vendored 落位 `sidecar/vendor/cosyvoice2/`。ADR-014 收敛搬运环境决策：Windows 裸装 + uv（Docker/WSL 不进基准与交付）；pynini/WeTextProcessing 依赖链经上游 main 全包 AST 侦察确认已消失（TextNorm 换 `regex`+`inflect`+`wetext`，无需 conda 特例，此前处置预案作废）；推理依赖取子集而非上游 requirements 全集（deepspeed/tensorrt/vllm/gradio/fastapi/grpcio/pyarrow/pyworld/librosa 等训练/部署面不进 venv）；torch 先试 2.7.x+cu126（冒烟失败回上游锚 2.3.1+cu121 并走变更）；权重走 modelscope（`iic/CosyVoice2-0.5B`）运行时下载，ttsfrd 闭源前端资源不下载（try/except fallback 成立）。

- **v1.4.3 相对 v1.4.2**（CosyVoice2 搬运实施第一笔，走 12.2）：15.1 Python 锚 3.11.x → **3.13.x**——实际 venv 为 miniconda base 3.13.5，92 tests/heavy 冒烟真机证据链全出自该解释器，torch 2.7 cp313 官方轮子在位（pyproject 同步 `requires-python>=3.13`、mypy 3.13）。依赖子集三笔 `==` 锚修订：onnxruntime 1.18.0 → **1.31.0**（上游锚无 cp313 轮子）、openai-whisper 20231117 → **20250625**（20231117 setup.py 在 py3.13 PEP 667 `locals()` 快照语义下 build 必炸）、tiktoken 补声明 **0.14.0**（上游 requirements 漏）；whisper build env 补丁 setuptools<81（pkg_resources 模块剥离）。vendored 落位入库 98 文件（`cosyvoice@074ca6d` + `matcha@dd9105b3` + 双 LICENSE + UPSTREAM.md）；ruff/mypy/import-linter 对 vendor 排除。uv 迁移完成：`uv.lock`（104 packages）入库，torch cu126 经 `tool.uv.sources` 显式映射官方源。全项记入 ADR-014 实施修订记录。
- **v1.4 相对 v1.3**（依独立架构评审修复：3 blocking + 7 important + 2 nit + 3 suggestion，全部采纳；评审框架 source：code-review-skill 架构评审指南）：① 3.4 补控制面消息与控制流定案（`user_text` / `clone_start` / `clone_cancel`、WS 帧 `bit2 = clone_sample`、`interrupt` 与 `cancel_turn` 语义边界及停止按钮映射、设置改为拉取式生效）；② 3.5 状态集合补 `error` 吸收态（含唯一迁出路径），3.4 枚举同步；③ 15.2 依赖图补 `audio/` `ipc/` 两层，AudioChunk 定家 `core/`，15.3 strict 边界同步；④ 分级就绪信号：`hello` 允许重发，`booting→ready` 必需引擎集合定死为 {ASR, LLM}；⑤ 阶段 -1 评测改「本人评分 + LLM-as-judge 双通道」（单人可执行）；⑥ 14.1 补重启后 Session 重建语义；⑦ chunker 职责定案：纯函数句切模块，策略由引擎注入；⑧ 3.2 资产路径原则收敛为资产层内相对路径；⑨ `llama_cpp` 按 YAGNI 移出目录（条件引入条款交给 ADR-001）；⑩ 新增 5.3 数据目录与磁盘治理（AppData 落点、Windows 路径自检、模型删除）；⑪ 错误码表补 `CLONE_CANCELLED`；4.x 签名注解与 `Persona` 定义补全；交叉引用修正两处；音色资产量级条件化。
- **v1.3 相对 v1.2**：① 新增 3.5 统一应用状态机（合法迁移表 + 用户动作矩阵 + `hello` 握手）；② 3.4 固化观测字段（`t` 时间戳、turn 生命周期耗时），供第 13 节自动测量；③ 新增 13 测试与质量保障（含 IPC schema 单一来源、记忆抽取评测门禁）；④ 新增 14 故障与恢复语义；⑤ 新增 15 工程规范与技术选型（版本锚定、依赖方向 import-linter）；⑥ 新增 16 隐私边界与数据可携带；⑦ 7.1 体积表按 torch 现实修正（ADR-011）+ PyInstaller 探测前置到阶段 0；⑧ ADR-009 写入兜底决策规则（zero-shot 保底）；⑨ 7.3 模型清单支持多下载源；⑩ 阶段 -1 评测方法学修订（交叉评分）并新增「档位×模型矩阵」交付物；⑪ 新增风险 12；ADR 索引补 ADR-011/012/013。
- v1.2 相对 v1.1：音色状态机、权威错误码总表、打断协议、壳侧采集、ADR-009 升格、上下文预算归属、分阶段验收修订（详见 git 历史）。
- v1.1 相对 v1.0：声音克隆范围界定改「技术范围界定」，移除「克隆对象」概念。

---

## 1. 文档目的与范围

**目的**：把 Echoes 从「Java 微服务 + Python AI 的 SaaS 形态」重构为「桌面级语音陪伴应用」，并在架构上为「局域网远程大脑」预留延伸路径。

**范围**：覆盖产品定义、架构分层、接口契约、数据模型、分阶段计划、打包策略、远程预留边界，以及测试策略、故障恢复、工程规范与隐私边界。不覆盖：具体 UI 视觉设计、模型训练细节、运营与分发渠道。

**读者**：开发者本人（主要）、未来的协作者（次要）。假设读者已了解原仓库 Echoes 的现状与诊断结论。

---

## 2. 产品定义

### 2.1 一句话定义

双击打开 → 克隆一个声音 → 语音闲聊，它记得你是谁。

### 2.2 核心体验（不可协商）

- **语音优先**：主要交互是说话，不是打字。文本输入可作为辅助，但不是默认路径。
- **音色绑定**：AI 的回复使用会话绑定的音色（未克隆时为内置音色，状态语义见 2.5）。克隆成功绑定后禁止任何静默替换；克隆失败时明确报错，保持现有绑定不变。
- **连续记忆**：隔天再聊，它记得昨天说过的事实与偏好。
- **本地底线**：断网状态下，对话链路（ASR → LLM → TTS）完整可用；联网是质量增强，不是功能前提。

### 2.3 明确非目标（MVP = 阶段 0–1 不做）

> 口径说明：本节约束的是 MVP（阶段 0–1）。阶段 2 引入的「音色列表 + 切换」「局域网第二终端」不违反本节——那是按 ADR-008 的渐进放开。

- 多角色 / 多用户 / 多租户
- 管理后台、运营面板
- 公网访问、账号体系、云同步
- 主动开口（架构预留，阶段 0 不实现）、全双工免提对话（VAD + 回声消除；MVP 采用按住说话的半双工模式，echo/AEC 问题是其边界理由，见 16.4）
- 移动端、视觉形象 / 虚拟人动画
- 任务管理、日程、效率工具功能
- 多音色档案管理（音色列表、试听、重命名、切换）
- 克隆对象关系/归属元数据（「为谁克隆」「关系」「权限」等字段与 UX）
- 远程大脑的多终端并发、公网中继

### 2.4 声音克隆的范围界定（MVP）

**MVP 做什么**：一个克隆入口——录制音频样本 → 生成音色（技术路线 zero-shot / fine-tune 见 ADR-009）→ 产出 `voice_id` → 绑定为当前会话音色。UI 文案保持中性（「录制声音样本」「生成音色」），不在产品层面引入「为谁克隆」的概念。

**MVP 不做什么**（真正的范围膨胀风险在这里）：

- 多音色档案管理：MVP 只有「当前音色」一个槽位，不做音色列表、试听、重命名、切换。阶段 2 再加（ADR-008）。
- 克隆对象元数据：`voice` 表不设「归属人」「关系」字段。
- 任何附加叙事：功能在技术上是中性的——「录一段样本，得到一个音色」。产品不引导、不设限、不加提示文案。

**理由**：克隆入口在技术上是一视同仁的；真正的范围风险不在于「克隆谁」，而在于一旦引入「克隆对象」概念，就会连带动出多音色管理、档案切换、伦理提示、素材合法性校验等一连串功能。守住「一个入口、一个槽位、无归属概念」，后续加什么叙事都不会推翻现有结构。

**质量约束（分层定案，与克隆对象无关）**：

- 阶段 0（引擎级校验）：录制完成即校验时长下限、采样率、噪声能量，失败报 `SAMPLE_TOO_SHORT` / `SAMPLE_TOO_NOISY`（码表见 3.4.1），不进入生成环节。
- 阶段 2（质量级校验）：克隆后自动生成对比样本计算说话人相似度，低于阈值报 `CLONE_QUALITY_LOW` 并引导重录。此前不存在"用户觉得不像"的判定路径。
- 全程：克隆失败明确报错，`failed` 态不改写现有绑定（2.5），禁止静默回退任何音色。

### 2.5 音色状态机（权威语义）

`Session.voice_id` 的三态语义，全文唯一的音色状态权威定义：

| 状态 | 含义 | 合成行为 | UI 表现 |
| --- | --- | --- | --- |
| `none` | 从未成功克隆 | 使用内置音色 `builtin:default`（CosyVoice2 预设） | 明示「当前音色：内置」 |
| `ready` | 绑定了一个 `status=ready` 的克隆音色 | 只使用该音色；合成链路任何失败必须 `error` 事件报出，**禁止改用内置音色完成本轮回复** | 明示「当前生效音色 ID」 |
| `failed` | 最近一次克隆失败 | 状态机**不回退**：已有绑定保持不变；无绑定则仍处于 `none` | 展示错误码 + 「重录」引导 |

- **解析规则**：编排层在调用 `TTSEngine.synthesize` 之前，把 `Session.voice_id`（可为 `None`）解析为具体音色 ID（含 `builtin:default`）。引擎契约不接受 `None`（4.5）。
- **「报错而非降级」约束的是 `ready` 态**：`none → builtin:default` 是初始态选择，不是降级。
- 内置音色以保留 ID `builtin:default` 表示，不属于 `voice` 表资产，永不参与列表/切换。

---

## 3. 架构总览

### 3.1 分层图

```text
┌─────────────────────────────────────────────────┐
│  Tauri 2 桌面壳（Rust 主进程 + WebView）          │
│  ├─ Vue 3 + Vite + Pinia 前端（复用现有积累）      │
│  ├─ sidecar 生命周期管理（hello 握手/健康检查/重启）│
│  ├─ 音频采集（getUserMedia → 重采样 16k → WS 推送） │  ← 麦克风归壳侧，sidecar 不碰设备
│  └─ 音频播放（rodio）                             │
└──────────────────┬──────────────────────────────┘
                   │ IPC：stdin/stdout JSON（控制/事件）
                   │     + 本地 WebSocket 二进制帧（音频）
                   │（协议见 3.4）
┌──────────────────▼──────────────────────────────┐
│  Python Sidecar（单进程，纯 asyncio）             │
│  ┌────────────────────────────────────────────┐ │
│  │ Transport 层（stdio / LocalWS / LanWS）     │ │
│  ├────────────────────────────────────────────┤ │
│  │ Session 管理层（每会话一个 Session 对象）    │ │
│  ├────────────────────────────────────────────┤ │
│  │ 编排层（最简 LangGraph：检索→拼接→生成）     │ │
│  ├──────────┬──────────┬──────────┬───────────┤ │
│  │ ASR      │ LLM      │ TTS      │ Memory    │ │
│  │ Engine   │ Provider │ Engine   │ Store     │ │
│  │(faster-  │(local /  │(CosyVoice│(sqlite-   │ │
│  │ whisper) │ cloud)   │ 2)       │ vec)      │ │
│  ├──────────┴──────────┴──────────┴───────────┤ │
│  │ SQLite（会话/记忆/人设/音色资产元数据）      │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### 3.2 核心架构原则

| 原则 | 含义 | 违反的典型症状 |
| --- | --- | --- |
| I/O 与设备解耦 | 输入输出是「音频帧流 + 事件流」；**麦克风采集与播放都在壳侧，sidecar 只消费/产出帧流** | 业务代码里出现 `pyaudio.open()` / `sounddevice.query_devices()` |
| 业务层不知道传输 | 编排、检索、合成不知道数据来自 IPC 还是 WebSocket | 编排节点里出现「如果是远程的话…」 |
| Provider/Engine 可替换 | LLM、ASR、TTS 各自走统一接口，上层不感知具体实现 | 业务代码里出现 `ollama.` 或 `cosyvoice.` 前缀 |
| 组装归组合根 | 具体引擎/provider 只在 `main.py`（组合根）实例化，其余代码只接收 ABC | engines 目录之外的模块出现 `import cosyvoice2` |
| 资产用 ID 引用 | 音色、人设、会话均以 ID 引用；`sample_path`/`model_path` 等**相对路径仅允许资产解析层（TTS 引擎内部）读写**，业务代码一律持 ID | 数据库里存 `.pt` 绝对路径 |
| 报错而非降级 | 任何环节失败显式报错，不静默替换（约束域见 2.5） | 克隆失败后自动用默认音色 |
| 单进程内事件有序 | 放弃跨进程幂等协议，IPC 天然有序 | 引入 `turn_id` / `idempotency_key` |
| 会话状态挂 Session | 对话上下文、记忆、当前音色挂 Session 对象，不散落全局 | 用模块级全局变量存当前音色 |
| Prompt 预算归编排 | 上下文组装与超限裁剪是编排层的职责，Provider 不感知截断 | provider 接口里出现「帮我截短 messages」类参数 |
| 推理不进事件循环 | 所有模型推理在独立线程池执行（`asyncio.to_thread` 或引擎自管线程），事件循环只做调度与流转发 | 事件循环回调内出现长阻塞推理调用 |

### 3.3 目录结构

```text
echoes/
├── src-tauri/                 # Rust 主进程
│   ├── src/
│   │   ├── main.rs
│   │   ├── sidecar.rs         # 生命周期管理、hello 握手、健康检查、重启
│   │   ├── capture.rs         # 麦克风采集、重采样、WS 推送
│   │   └── audio.rs           # 播放（rodio）、打断 flush
│   ├── tauri.conf.json
│   └── binaries/              # sidecar 按 target triple 放置
├── src/                       # Vue 3 前端
│   ├── views/                 # ChatView / CloneView / SettingsView
│   ├── stores/
│   └── lib/
│       ├── ipc.ts             # 与 sidecar 的 IPC 封装
│       └── ipc_types.ts       # ← 由 sidecar schema 自动生成（13.2），禁止手改
├── sidecar/                   # Python sidecar（独立可构建）
│   ├── pyproject.toml
│   ├── echoes_sidecar/
│   │   ├── main.py            # 组合根：DI 装配 + 启动 Transport
│   │   ├── ipc/
│   │   │   └── schema.py      # 消息 pydantic 模型（单一来源，13.2）
│   │   ├── transport/         # base / stdio / local_ws
│   │   ├── session/           # manager / session
│   │   ├── orchestration/     # graph.py（最简 LangGraph）
│   │   ├── engines/
│   │   │   ├── asr/           # base / faster_whisper
│   │   │   ├── tts/           # base / cosyvoice2
│   │   │   └── llm/           # base / ollama / cloud_api / mock 各自实现
│   │   │                      #（llama_cpp 仅当 ADR-001 弃用 Ollama 捆绑时引入，届时同步补 15.1 锁定；现已从目录移除——YAGNI）
│   │   ├── memory/            # store / extractor
│   │   ├── audio/             # stream / chunker（chunker 为纯函数句切模块，策略由引擎注入，见 4.5）
│   │   ├── db/                # schema.sql / migrations/
│   │   └── core/              # 错误码常量、事件类型、AudioChunk 等零依赖类型
│   ├── tests/
│   │   ├── golden/            # IPC 契约 golden 样例（13.2）
│   │   ├── fixtures/          # 音频夹具（clone_sample.wav 等）
│   │   └── ...
│   └── scripts/
│       └── gpu_smoke.py       # GPU 冒烟脚本（7.2 CI 边界）
├── models/                    # 模型权重（运行时下载，不入库）
├── docs/
│   ├── architecture.md        # 本文档
│   ├── decisions/             # ADR
│   └── benchmarks/            # 阶段 -1 产出 + 档位×模型矩阵
└── .github/workflows/
    ├── build-sidecar.yml
    └── schema-drift.yml       # schema 对拍检查（13.2）
```

### 3.4 IPC 协议（v1.2 起；v1.4 控制面补全）

**传输选择**：主链路 stdin/stdout 行分隔 JSON（控制/事件）；音频流本地 WebSocket 二进制帧（避免 base64 膨胀，且为远程预留同一协议）；麦克风数据由壳侧采集后经 WS 推入 sidecar。

**stdio JSON 事件消息**（每行一条）：

```json
{"type": "hello", "sidecar_version": "0.1.0", "protocol_version": "1.0", "t": 3, "engines": [{"name": "asr", "ready": false}, {"name": "tts", "ready": false}, {"name": "llm", "ready": false}]}
{"type": "asr_partial", "session_id": "...", "text": "...", "t": 1042}
{"type": "asr_final", "session_id": "...", "text": "...", "is_final": true, "t": 1187}
{"type": "assistant_text", "session_id": "...", "text": "...", "t": 1320}
{"type": "turn_complete", "session_id": "...", "turn_seq": 7, "status": "SUCCESS | CANCELLED | FAILED", "timings": {"total_ms": 2431, "llm_first_token_ms": 692, "tts_first_audio_ms": 1180}}
{"type": "clone_progress", "session_id": "...", "phase": "recording | training | checking", "pct": 42, "t": 5120}
{"type": "error", "session_id": "...", "code": "CLONE_QUALITY_LOW", "message": "...", "fatal": false, "t": 214}
{"type": "state", "session_id": "...", "state": "booting|ready|generating|speaking|error", "t": 68}
```

**stdio JSON 控制消息**（壳 → sidecar）：

```json
{"type": "control", "action": "interrupt | cancel_turn", "session_id": "...", "turn_seq": 7}
{"type": "user_text", "session_id": "...", "text": "…"}
{"type": "clone_start", "session_id": "...", "sample_keys": ["clone:<uuid>"]}
{"type": "clone_cancel", "session_id": "..."}
```

**控制动词与控制流（v1.4 定案，冻结范围）**：

- `interrupt` = 取消当前 turn 的生成与播放，随后立即回到可采集状态（PTT 打断专用）。
- `cancel_turn` = 仅丢弃当前 turn 且**不进入采集**（停止播放按钮映射为它，3.5）。两者收尾一致：`turn_complete(status=CANCELLED)`，播放缓冲清理由壳负责。
- **文本输入** = `user_text`：与 `asr_final` 等价触发新 turn（12.3 首周「文本→LLM→文本」即用）。
- **回复文本** = `assistant_text`（v1.4.1 追加）：LLM 流式回复的文本承载帧，`text` 截至当前全量、逐帧递增，前端直接替换渲染当前 assistant 气泡；turn 收尾以 `turn_complete` 界定（UI 将其定稿）。仅走 stdio 控制面，不走 WS 音频信道。
- **克隆** = 录制样本经 WS 二进制帧上送（`flags bit2 = clone_sample`），收尾帧后发 `clone_start`，SessionManager 由此触发 `TTSEngine.clone`；`clone_cancel` 中途取消 → 取消克隆协程 + `CloneError(CLONE_CANCELLED)` → 音色落 `failed`（2.5，已绑定会话的绑定关系不受影响）。样本仅在资产目录暂存，不进业务库。
- **设置生效** = 拉取语义：sidecar 在**每个 turn 开始前**从 `setting` 表读取 provider/隐私模式等配置；壳写入 SQLite 即完成传播，协议不设推送消息。API key 仅由 provider 进程内读取（4.4）。

**WS 二进制音频帧**（`audio_chunk` / `tts_chunk` 的 JSON 形式仅保留为调试回放格式）：

```text
偏移 0     : 1B   方向   （0x01 壳→sidecar / 0x02 sidecar→壳）
偏移 1     : 4B   seq    （LE u32，方向内单调递增）
偏移 5     : 1B   flags  （bit0 = is_final，bit1 = interrupt_hint，bit2 = clone_sample）
偏移 6 ... : PCM16 payload（输入 16kHz mono / 输出 24kHz mono）
```

**打断协议（三跳预算分摊）**：

| 环节 | 责任方 | 预算 |
| --- | --- | --- |
| PTT 触发即清 playback 缓冲（不等 sidecar 确认） | Tauri 壳 | ≤100ms |
| `control(action=interrupt)` shell→sidecar 往返确认 | IPC | ≤50ms |
| sidecar 取消生成、丢弃在途 chunk，停止向 WS 产出 | sidecar | ≤150ms |
| 用户感知总预算 | — | ≤300ms |

- 前提：壳侧在途音频缓冲上限 **600ms**、sidecar 出队缓冲上限 **300ms**，超上限即背压丢弃。
- 被打断的 turn 以 `turn_complete(status=CANCELLED)` 收尾。

**观测字段（v1.3）**：每条 sidecar 事件携带 `t`（sidecar 单调时钟，ms，自进程启动起算）；`turn_complete.timings` 携带 `llm_first_token_ms` / `tts_first_audio_ms` / `total_ms`。这些字段是 13.4 自动测量的唯一数据来源，也支撑用户侧诊断（14.4）。

**握手（v1.3；v1.4 补重发语义）**：sidecar 启动后第一行输出 `hello`（含 `sidecar_version` / `protocol_version` / 引擎就绪清单）；**任一引擎就绪状态变化时重发 `hello`**（schema 相同，壳以最后一份为准）——它是 6/阶段 0 验收 1「分级开麦/完整对话信号」的唯一载体，必需引擎集合见 3.5。壳校验 `protocol_version` 大版本不匹配（3.4.1 `PROTOCOL_MISMATCH`）时终止并显示修复引导；大版本一致时，未知字段必须忽略、未知消息类型必须忽略（只追加兼容规则的执行点）。

**错误消息约束**：`error.code` 采用 `DOMAIN_REASON` 命名，前端按 code 渲染，不解析 message。

#### 3.4.1 权威错误码总表

跨全文的唯一错误码来源，其余章节只引用：

| code | 域 | 触发 |
| --- | --- | --- |
| `SAMPLE_TOO_SHORT` | clone | 样本时长低于下限 |
| `SAMPLE_TOO_NOISY` | clone | 样本噪声能量超标 |
| `CLONE_QUALITY_LOW` | clone | 阶段 2 说话人相似度低于阈值 |
| `CLONE_ENGINE_FAILED` | clone | 生成音色过程异常（非质量原因） |
| `CLONE_CANCELLED` | clone | 用户中途取消克隆（3.4 `clone_cancel` 触发，落 `failed` 非绑定回退） |
| `MODEL_NOT_LOADED` | engine | 引擎模型未预热完成 |
| `VOICE_NOT_AVAILABLE` | voice | `ready` 态音色文件缺失/权限不足（禁止静默回退） |
| `MIC_NOT_AVAILABLE` | capture | 壳侧采集失败（权限拒绝/设备占用） |
| `LLM_PROVIDER_UNAVAILABLE` | llm | 当前 provider 不可达 |
| `ASR_ENGINE_ERROR` | asr | 引擎内部异常 |
| `TTS_ENGINE_ERROR` | tts | 引擎内部异常 |
| `STORAGE_ERROR` | storage | 磁盘满/SQLite 写失败（14.2） |
| `PROTOCOL_MISMATCH` | ipc | hello 握手协议版本不匹配 |
| `INTERNAL_ERROR` | misc | 兜底 |

新码**只追加，不重命名、不复用**。

### 3.5 统一应用状态机（v1.3）

**所有权**：`state` 是 sidecar 的状态机，壳/UI 只是渲染者；`listening`（PTT 按住中、麦克风活跃）是壳本地状态，不进 sidecar 状态机。

状态集合：`booting | ready | generating | speaking | error`

`error` 为**吸收态**（v1.4）：仅 fatal 错误进入（3.4 `error` 事件 `fatal=true`）；非致命错误只发 `error` 事件，状态机留在原状态。唯一出口：壳按 14.1 重启 sidecar 后经 `hello` 重新握手回到 `booting`。

合法迁移（全部由 sidecar 发出，`state` 变更才发，不重复发）：

| from | to | 触发 |
| --- | --- | --- |
| `booting` | `ready` | **必需引擎集合 = {ASR, LLM}** 就绪（分级预热见 6/阶段 0；TTS 就绪不改状态机，仅经 hello 引擎清单驱动壳侧语音按钮解锁） |
| `booting` | `error`(fatal) | 引擎加载失败且不可恢复 |
| `error` | `booting` | 壳按 14.1 重启 sidecar 后经 `hello` 重新握手（`error` 的唯一出口） |
| `ready` | `generating` | `asr_final` / `user_text`（3.4）触发新 turn |
| `generating` | `speaking` | 首个 TTS chunk 产出 |
| `generating` | `ready` | turn 以 FAILED 结束且无音频产出 |
| `speaking` | `ready` | `turn_complete(status=SUCCESS/FAILED/CANCELLED)` 播完 |
| `generating`/`speaking` | `generating`(重入) | `control(interrupt)` + 新输入：取消当前 turn，直接进入新 turn |

**用户动作矩阵**（壳侧执行部门转发给 sidecar 或本地处理）：

| 用户动作 | `booting` | `ready` | `generating` | `speaking` |
| --- | --- | --- | --- | --- |
| PTT 按下 | 禁用（按钮灰） | 开始采集 | **打断**（control=interrupt，清播放缓冲） | **打断**（同左） |
| 文本输入（`user_text`） | 禁用 | 发起新 turn | 打断并发起新 turn | 打断并发起新 turn |
| 停止播放按钮 | 禁用 | 不存在 | 不存在 | 发 `cancel_turn`，`turn_complete(status=CANCELLED)` 收尾，不进入采集 |
| 克隆入口 | 禁用 | 允许 | 禁用 | 禁用 |
| 设置/切 provider | 允许（booting 内只读） | 允许 | 允许（下轮生效：拉取语义见 3.4） | 允许（同左） |

规则：非法迁移出现即 sidecar 自身 bug——按 `INTERNAL_ERROR` 上报并写入日志，UI 显示当前状态供排障；本表是 13.2 契约测试的输入。

---

## 4. 关键接口契约（阶段 0 冻结）

### 4.1 Transport

```python
# sidecar/echoes_sidecar/transport/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator

class Transport(ABC):
    @abstractmethod
    async def recv(self) -> dict | None:
        """拉取下一条消息（见 3.4）；流关闭且无后续消息时返回 None。"""

    @abstractmethod
    async def send(self, msg: dict) -> None:
        """发送消息 dict"""

    @abstractmethod
    async def close(self) -> None: ...
```

实现：

- `StdioTransport`：stdin/stdout 行分隔 JSON，阶段 0 默认，承载事件与控制消息。
- `LocalWebSocketTransport`：本机 `ws://127.0.0.1:PORT`，阶段 0 并存（音频二进制帧走 WS）。
- `LanWebSocketTransport`：阶段 2 之后实现，现在不写，但接口已兼容。
- 所有 Transport 实现必须通过同一套一致性测试（13.2 第 3 条），这是「远程大脑只需换 Transport」的证明义务。

### 4.2 AudioChunkStream

```python
# sidecar/echoes_sidecar/audio/stream.py
# AudioChunk 权威定义归 core/（零依赖层，见 3.3/15.2）：from echoes_sidecar.core import AudioChunk
# 以下为字段示意：
from dataclasses import dataclass
from typing import AsyncIterator

@dataclass
class AudioChunk:
    data: bytes            # PCM16, 16kHz, mono（输入）/ 24kHz（输出）
    seq: int
    is_final: bool = False

class AudioInputStream:
    """输入源抽象。壳侧采集（经 WS）、文件、网络 WS 都是它的实现。
    sidecar 内不存在任何直接打开麦克风的代码。"""
    def __aiter__(self) -> AsyncIterator[AudioChunk]: ...

class AudioOutputStream:
    """输出目标抽象。壳侧播放（经 WS）、文件、网络 WS 都是它的实现。
    真正的播放设备与缓冲在 Tauri 壳（rodio）；本抽象负责把 chunk 送出 sidecar，
    并保证 stop() 语义成立（三跳协议见 3.4）。"""
    async def write(self, chunk: AudioChunk) -> None: ...
    async def stop(self) -> None:
        """打断：清空内部缓冲，立即停止。
```

**打断验收**：PTT 触发后壳不再播出旧 turn 的新音频，且上游不再产生新 chunk；预算按 3.4 三跳口径。

### 4.3 TriggerSource（阶段 0 只实现 USER_INPUT）

```python
from enum import Enum

class TriggerSource(Enum):
    USER_INPUT = "user_input"
    TIMER = "timer"                  # 阶段 0 不实现
    IDLE_DETECTED = "idle_detected"  # 阶段 0 不实现
    EXTERNAL_EVENT = "external_event"  # 阶段 0 不实现
```

编排入口签名 `async def run_turn(session, trigger: TriggerSource, payload: dict)`（payload 结构见 3.4 对应消息）。阶段 0 只有 `USER_INPUT` 被调度；其余枚举值触发路径返回 `NotImplementedError`，防止未来加主动开口时改签名。

### 4.4 LLM Provider

```python
# sidecar/echoes_sidecar/engines/llm/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator

class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: list[dict],       # [{"role": "system|user|assistant", "content": "..."}]
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """流式产出 token 片段。"""

    @abstractmethod
    async def health(self) -> bool:
        """provider 可用性检查（供 Settings 页展示）。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """'ollama' / 'cloud:deepseek' 等。"""
```

约束：

- 编排层只接受 `list[dict]` 的 `messages`，不接受任何 provider 特有字段。
- `generate` 返回 `AsyncIterator[str]`，不暴露 token logits 或 provider 原生 chunk。
- **上下文预算归编排层**：messages 组装、排序、超限裁剪全部在编排层完成（策略见 5.2）；provider 收到的 messages 永远已合预算，接口不提供截断参数。
- 云端 provider 的 API key 从 Settings 读取，不硬编码、不入库明文（阶段 1 本地加密存储，阶段 0 可用环境变量）。
- **隐私模式约束**：provider 进入「隐私模式」时，该语义覆盖全部经此 provider 的调用——包括 5.2 的记忆事实抽取。隐私模式下抽取出网即违反 2.2 本地底线。

### 4.5 ASR Engine / TTS Engine

```python
class ASREngine(ABC):
    @abstractmethod
    async def transcribe(
        self, audio: AudioInputStream
    ) -> AsyncIterator[dict]:
        """产出 {"text": str, "is_final": bool, "start_ms": int, "end_ms": int}"""

class TTSEngine(ABC):
    @abstractmethod
    async def synthesize(
        self, text: str, voice_id: str
    ) -> AsyncIterator[AudioChunk]:
        """流式产出音频 chunk。voice_id 是已解析的资产 ID（含 builtin:default，
        由编排层按 2.5 解析；本契约不接受 None，引擎内部不做状态机判断）。"""

    @abstractmethod
    async def clone(self, sample: AudioInputStream) -> str:
        """克隆。技术路线见 ADR-009（含兜底规则）；无论哪条路线，
        产出都是 voice_id + 资产目录内的缓存文件。失败抛 CloneError。"""
```

TTS 分句：句切是**纯函数模块**，物理上归 `audio/chunker`（3.3，可做 L1 独立单测——13.1）；分句策略（默认按标点分句）作为入参由 TTSEngine 注入。引擎侧逐句合成、逐句产出；编排层不感知分句，只消费 chunk 流。

克隆契约：

- `clone()` 只接收音频流，不接收任何「对象」元数据。
- 失败抛 `CloneError(code, message)`，code 取自 3.4.1（`SAMPLE_TOO_SHORT` / `SAMPLE_TOO_NOISY` / `CLONE_ENGINE_FAILED` / `CLONE_CANCELLED`（3.4 `clone_cancel` 触发）；`CLONE_QUALITY_LOW` 由阶段 2 质检模块产出）。
- 调用方收到异常后必须向 UI 报错并置音色 `failed`（2.5），禁止回退。
- 克隆期间 `clone_progress`（recording → training → checking）由 SessionManager 产出；无进度即"假死"，属验收项。

### 4.6 Session

```python
@dataclass
class Session:
    session_id: str
    profile_id: str            # 记忆归属（阶段 0 固定 "default"）
    voice_id: str | None       # None = 2.5 none 态（由编排层解析）
    persona: Persona           # 人设卡
    turn_seq: int = 0
    created_at: float = ...
    # 不持有 Transport / AudioStream，由 Manager 注入
```

`Persona` 同为 `core/` 零依赖 dataclass，与 5.1 persona 表字段一一映射：`id / name / system_prompt / created_at / updated_at`。

SessionManager 负责：创建/获取/销毁 Session、注入 Transport 与 AudioStream、串行化同一 Session 内 turn、响应 3.4 `clone_start` 并产出 `clone_progress`。阶段 0 只维护一个 Session，但代码路径按「按 session_id 查找」写；sidecar 重启后的 Session 重建语义见 14.1。

---

## 5. 数据模型（SQLite）

### 5.1 Schema（v1）

```sql
-- 人设
CREATE TABLE persona (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);

-- 音色资产（元数据；克隆产出文件在资产目录下，以 id 命名，格式视 ADR-009）
-- 无「归属人」「关系」等字段，MVP 不引入克隆对象概念
CREATE TABLE voice (
    id            TEXT PRIMARY KEY,          -- uuid；保留 ID builtin:default 不落库
    display_name  TEXT NOT NULL,             -- 自动生成，如「音色 1」
    sample_path   TEXT NOT NULL,             -- 相对资产目录的路径
    model_path    TEXT,                      -- 克隆产出文件，未生成成功为 NULL
    status        TEXT NOT NULL,             -- 'training'|'ready'|'failed'
                                             -- （录音中是 UI 态，不落库）
    quality_score REAL,                      -- 阶段 2 起的相似度，此前为 NULL
    created_at    REAL NOT NULL
);

-- 会话（轮次明细不落库，落库的是摘要与事实）
CREATE TABLE session (
    id            TEXT PRIMARY KEY,
    profile_id    TEXT NOT NULL DEFAULT 'default',
    persona_id    TEXT NOT NULL,
    voice_id      TEXT,
    started_at    REAL NOT NULL,
    last_active_at REAL NOT NULL,
    FOREIGN KEY (persona_id) REFERENCES persona(id),
    FOREIGN KEY (voice_id)   REFERENCES voice(id)
);

-- 记忆事实（用户偏好、事实、事件）
CREATE TABLE memory_fact (
    id            TEXT PRIMARY KEY,
    profile_id    TEXT NOT NULL DEFAULT 'default',
    fact          TEXT NOT NULL,             -- "用户下周有面试"
    category      TEXT NOT NULL,             -- 'preference'|'event'|'identity'|'other'
    source_session_id TEXT,                  -- 来自哪个会话（可追溯）
    source_turn   INTEGER,                   -- 来自该会话第几轮
    created_at    REAL NOT NULL,
    last_seen_at  REAL NOT NULL,
    superseded_by TEXT,                      -- 被新事实取代时指向新 id
    deleted       INTEGER NOT NULL DEFAULT 0 -- 删除语义见 16.2（真删时向量同步移除）
);

-- 对话滚动摘要
CREATE TABLE session_summary (
    session_id    TEXT PRIMARY KEY,
    summary       TEXT NOT NULL,
    up_to_turn    INTEGER NOT NULL,
    updated_at    REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES session(id)
);

-- 向量索引（sqlite-vec）
-- 维度参数化：默认 bge-small-zh（512 维）；质量档 bge-m3（1024 维）。
-- vec0 表不可 ALTER——切档 = migrations 重建本表。
CREATE VIRTUAL TABLE memory_vec USING vec0(
    fact_id TEXT PRIMARY KEY,
    embedding FLOAT[<dim>]
);

-- 设置（键值，含 LLM provider 选择、嵌入档位、隐私模式等）
CREATE TABLE setting (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL                      -- JSON 编码
);
```

### 5.2 记忆策略

- **抽取时机**：每轮 turn 结束后，异步调用 LLM 抽取事实写 `memory_fact`，在独立线程执行（3.2 最后一行的执行约束）。抽取 provider 必须跟随当前全局模式，隐私模式（本地）下绝不出网（4.4）。
- **检索时机**：每轮 turn 开始前，用用户输入 query 检索 top-k 相关 fact（sqlite-vec 暴力扫描，k=5~8）拼进 system prompt。
- **摘要更新**：每 10 轮或每 30 分钟更新 `session_summary`，摘要与事实并列进 prompt。
- **上下文组装与截断**：prompt 组装器归编排层——`system(人设 + facts)` → `session_summary` → 会话内最近 N 轮；超预算依序裁剪最旧轮次，provider 不感知。
- **事实质量门禁**：抽取产线的正确率以 13.3 评测集守护——错误记忆比没有记忆更毒，低于阈值不得合入新抽取策略。
- 不存储原始对话全文（阶段 0）；阶段 1 如需调试加 `turn_log` 表，默认关闭。

### 5.3 数据目录与磁盘治理（v1.4 新增）

- **目录布局（Windows）**：配置与业务数据落 `%LOCALAPPDATA%\Echoes\`：`db\`（SQLite + WAL）、`assets\`（音色样本与克隆产物；5.1 的相对路径仅相对此目录解析）、`logs\`；模型权重与 torch/CUDA 运行时在 `~/.cache/echoes/`（跨版本复用，口径同 7.1/7.3）。
- **路径自检**：14.3 启动自检覆盖「数据/缓存目录不可写、路径含特殊字符、Windows 用户名为中文或含空格」——PyInstaller + torch 模型加载在 Windows 路径上是历史上多发故障区，处理方式是**配置自检 + 明确报错引导**（`STORAGE_ERROR`，3.4.1）而不是事后救火。
- **磁盘治理**：模型管理器（7.3）必须提供「删除已装模型 / 旧版本运行时释放空间」的操作项；14.1 磁盘满场景的可清理集合 = 模型缓存 + 日志，**音色资产与记忆数据永不自动清理**。

---

## 6. 分阶段计划

### 阶段 -1：对话质量基准（1 周）

**目标**：用数据回答「本地 LLM 在陪伴场景下差云端多少」，收敛 LLM 路线分叉。

**产出**：

- 一组 20 轮固定陪伴场景对话（人格一致性、记忆引用、情感回应三类场景），每轮附「预期要点清单」。
- 本地 Qwen2.5-7B / Qwen3-8B（量化）/ 云端 DeepSeek 三路对比。**人格一致性采用双通道评测（单人可执行，v1.4 修订）**：本人评分（1-5）+ LLM-as-judge（独立于被测路线的强模型，按「预期要点清单」打分），两通道分歧 ≥2 分的轮次由本人终审仲裁。主指标为**要点命中率**，辅以首 token 延迟、tok/s。要点清单、judge prompt 与全部评分记录入 `docs/benchmarks/`（judge prompt 入库以便复检重现）。
- **档位×模型矩阵**（8GB / 12GB / 24GB / 纯 CPU 四档 × ASR/LLM/TTS/嵌入组合，含每档显存/内存预算与量化策略），写入 `docs/benchmarks/tier_matrix.md`，成为模型管理器推荐档位与 ADR-011 的输入。
- 结论写入 `docs/decisions/ADR-001-llm-route.md`，内含「隐私模式」行为定义：隐私模式下允许云端、还是绝不出网（默认绝不出网，见 4.4/16.1）。

**验收**：报告能回答「目标硬件档位下，本地模型是否能作为默认」，并给出 provider 抽象的设计深度结论。

### 阶段 0：垂直切片（3–4 周）

**目标**：跑通「麦克风 → ASR → LLM → TTS → 扬声器」全链路，且克隆声音在对话中被真实使用。

**范围**：

- Tauri 2 壳 + Vue 3 最小聊天界面（按住说话；音频播放 + 转写文本）。麦克风由壳侧采集：getUserMedia → Rust 重采样 48k→16k → WS 二进制帧；播放用 rodio + 3.4 打断协议。
- Python sidecar：StdioTransport + LocalWS、单 Session、faster-whisper ASR、CosyVoice2 TTS（原仓库搬运）、Ollama provider。
- 克隆闭环：录制 3–6 秒 → 生成音色（路线按 ADR-009，含 `clone_progress`）→ `voice_id` → 绑定当前会话 → 后续回复全用该音色。引擎级校验失败明确报错，不静默回退（2.5）。

> **ADR-009 兜底规则（v1.3 写入）**：第一周 spike；结论满足「fine-tune 质量 ≥ zero-shot + 可感知阈值，或优势场景有产品价值」且「训练时长 ≤5 分钟（目标硬件）」才采用 fine-tune，否则采用 zero-shot；spike 48 小时无结论 → 默认 zero-shot 上线，fine-tune 转入阶段 2 优化项。该规则不再需要重新讨论。

- 音色资产表、session 表、persona 表；打断三跳协议全程落地（含两侧缓冲上限）。
- **打包探测（v1.3 前置）**：第一周内完成 PyInstaller ONEDIR「无 torch + 带 torch」两次实测体积与可运行性，结果作为 ADR-011 的定稿输入（原属阶段 3 的风险前置）。
- 骨架内建：13.2 契约测试、mock 引擎、`hello` 握手（不是"以后再补测试"）。

**验收标准**：

1. 分级就绪：双击打开到 UI 可交互 ≤3s；ASR+LLM 就绪（开麦）≤8s；TTS 就绪（可完整对话）≤25s，就绪前禁用语音按钮并显示「引擎就绪中」，不黑屏。阈值允许阶段 0 实测一次性校准 ±20%（记入 ADR-012）。
2. 端到端延迟预算（本机 P50，实测校准）：

   | 指标 | 预算 |
   | --- | --- |
   | PTT 松开 → `asr_final` | ≤600ms |
   | `asr_final` → 首 token | ≤700ms（模型预载后） |
   | 首 token → 首音频块 | ≤500ms |
   | 端到端出声 | P50 ≤2.5s / P95 ≤4s |

3. 克隆全程无命令行、文案中性、有进度反馈（`clone_progress`），无"假死"。
4. 克隆完成后每句回复使用该音色；噪声样本触发失败时 UI 显示明确错误（码表命中），音色落 `failed`，无任何默认音色回复替换成功轮次。
5. 对话中途打断（PTT）：音频 300ms 内停止（三跳口径），新输入被正确处理，被打断 turn 收到 `turn_complete(status=CANCELLED)`。
6. 断网全链路可用（本地 LLM + TTS/ASR）。
7. 3.5 状态机非法迁移为零（13.2.5 契约测试守护）。

**不做**：记忆检索、主动开口、多 Session、远程接入、打包安装器、多音色管理、说话人相似度质检（阶段 2）。

### 阶段 1：记忆与人设（2–3 周）

**目标**：隔天再聊，它记得你。

**范围**：`memory_fact` + 抽取 + 检索接入编排（走 5.2 隐私约束与 13.3 评测门禁）；`session_summary`；人设卡 UI；sqlite-vec（默认 bge-small-zh，512 维）；Settings 页（provider 切换、隐私模式、API key 配置）。

**验收标准**：

- 第一天聊「我下周有面试」，第二天说「我有点紧张」，回复引用面试事实。
- 切换 provider 后人格与记忆行为不变（仅质量差异）。
- 隐私模式下记忆抽取不出网（抓包/连接审计验证）。
- 摘要与事实 prompt 占比可配置，首 token 延迟增幅 ≤200ms。

### 阶段 2：克隆 UX 完善 + 远程大脑（2–3 周）

**目标**：克隆 UX 达到「非技术用户可用」；局域网玩具终端可作为第二音频端点接入。

**范围**：克隆质检（承接 2.4 分层，`CLONE_QUALITY_LOW` 引导重录）；音色槽位轻量管理（列表+切换，ADR-008）；LanWebSocketTransport + 设备配对（IP + 一次性 token）；玩具终端协议最小实现（树莓派或 PC 模拟，验收协议而非硬件）；fine-tune 路线若为阶段 0 兜底选项，在此评估质量升级。

**验收标准**：

- 非技术用户不看文档完成「录音 → 克隆 → 绑定 → 对话」。
- 第二终端接入后与桌面端共享同一 profile 记忆。
- 终端断网重连后，同一 turn 不重复回复。
- 切换绑定音色后新回复用新音色，旧回复不受影响。

**明确不做**：多终端并发对话、公网接入、完整设备管理 UI。

### 阶段 3：打包与分发（3–4 周，真正的硬仗）

**目标**：非技术用户双击安装可用。

**范围**：

- GitHub Actions 三平台矩阵构建 sidecar（Windows x64 必做；macOS arm64 / Linux x64 可选）。
- Tauri 安装器：主程序 + sidecar 基础运行时；torch/CUDA 与模型权重走运行时下载（ADR-011 定稿后执行）。
- 模型管理器（7.3 扩展版：多源下载、校验、缓存、Ollama 复用扫描）。
- 首次启动引导：硬件检测 → 档位推荐（`docs/benchmarks/tier_matrix.md`）→ 下载。

**验收标准**：

- 干净 Windows 机器：安装包下载完成 → 首次对话 ≤15 分钟（含 torch/模型下载，取决于网速）。
- **基础安装包（主程序+sidecar 基础运行时）≤400MB**（v1.3 修订：原 ≤300MB 未计 torch 现实，见 7.1）；torch/CUDA 与模型权重独立于主程序版本更新。
- 低配/无 GPU 机器：启动时明确提示「当前硬件仅支持 CPU 模式，对话质量与速度受限」，不崩溃。

**风险**：「死亡区」。阶段 3 开始前必须完成阶段 0–2 稳定运行，否则打包会掩盖架构问题。

---

## 7. 打包与分发策略

### 7.1 split-binary 原则（v1.3 按现实修正）

| 组件 | 分发方式 | 体积量级 |
| --- | --- | --- |
| Tauri 主程序 + Vue 前端 | 安装包内置 | < 50MB |
| Python sidecar 基础运行时（PyInstaller ONEDIR，**不含 torch/CUDA**） | 安装包内置 | 100–300MB |
| torch + CUDA 运行时包 | 运行时按需下载（GPU 档位） | 1.5–2.5GB |
| 模型权重（ASR / TTS / LLM / 嵌入） | 运行时按需下载 | 数 GB（嵌入默认 ~100MB） |
| 音色资产 | 用户本地生成 | 量级随 ADR-009 路线定：zero-shot ≈ KB 级嵌入缓存；LoRA ≈ 数十 MB；全量 checkpoint ≈ 数百 MB（按落地路线写实，不预设统一上限） |

> **ADR-011（决策待定，阶段 0 第一周定稿）**：「分体 torch 运行时包」vs「接受 1–2.5GB 安装包」。**默认建议：分体**——torch 包由模型管理器按档位下载（CPU 轮子或 CUDA 轮子），主程序安装包保持小体积、更新解耦。阶段 0 的 PyInstaller 实测数据（6/阶段 0 范围）是本 ADR 定稿依据。

### 7.2 构建矩阵

```yaml
# .github/workflows/build-sidecar.yml（示意）
strategy:
  fail-fast: false
  matrix:
    include:
      - os: windows-latest
        target: x86_64-pc-windows-msvc
      - os: macos-latest
        target: aarch64-apple-darwin
      - os: ubuntu-latest
        target: x86_64-unknown-linux-gnu
```

**CI 边界**：runner 无 GPU，CI 只验证「CPU 路径冒烟 + transport/session 单测 + schema 对拍（13.2）」；GPU 冒烟（CosyVoice2 推理、克隆）走本机脚本 `sidecar/scripts/gpu_smoke.py`，阶段 3 打包前目标平台本机全量跑通。禁止把 CUDA torch 构建塞进 CI。

### 7.3 模型管理器

- 模型清单（JSON）随主程序发布：名称、大小、sha256、**多下载源**（HF 官方 / 国内镜像 / 直链 CDN，同一 sha256 校验）、推荐硬件档位、隐私属性（是否必需出网）。
- 下载断点续传、sha256 校验、失败重试与换源重试；校验失败自动重下（配合 14.2）。
- 已缓存模型扫描：优先复用 `~/.cache/huggingface/hub/` 与 Ollama 模型目录。
- **网络探测**：启动时探测各源连通性并按延迟排序，不给用户"选哪个源"的负担。

---

## 8. 远程大脑预留边界

### 8.1 现在做（成本≈0）

- Transport 抽象（4.1，含一致性测试义务）+ AudioStream 抽象（4.2）。
- Session 带 `profile_id`（5.1）；音色资产用 ID 引用（4.5）。
- 编排入口接受 TriggerSource（4.3）；schema 预留 `profile_id`（5.1）。

### 8.2 阶段 2 做

- LanWebSocketTransport 实现；设备配对（IP + token）；断线重连的 turn 去重（基于 `turn_seq`）。

### 8.3 现在不做，且不预留代码路径

- 多终端并发调度；公网穿透/中继/账号体系；完整设备管理 UI；端到端加密（局域网阶段 2 不做，公网另立项）。

---

## 9. 风险清单与缓解

| # | 风险 | 等级 | 缓解 |
| --- | --- | --- | --- |
| 1 | 本地 7B–8B 模型人格一致性不足 | 高 | 阶段 -1 基准量化；provider 抽象保证云端可切；UX 区分「隐私/高质量模式」；抽取跟随隐私模式（5.2） |
| 2 | 硬件门槛（12GB VRAM 基线可能不够） | 高 | 阶段 -1 三档基准 + **档位×模型矩阵交付物**；模型管理器按矩阵推荐档位 |
| 3 | CosyVoice2 冷启动慢 | 中 | 分级就绪（验收：ASR+LLM 先就绪开麦，TTS 单独指标 ≤25s）；预热顺序 whisper→LLM→CosyVoice2；就绪前只禁语音按钮 |
| 4 | 打包（阶段 3）失败 | 高 | split-binary + ADR-011 定稿；**PyInstaller 体积/可运行性探测前置到阶段 0**；CI 限定 CPU 路径；GPU 冒烟本机脚本 |
| 5 | 克隆质量参差 | 中 | 分层质检：阶段 0 引擎级校验兜底，阶段 2 相似度质检 + 引导重录；全程「报错而非降级」（2.5） |
| 6 | 嵌入模型选型与体积 | 低 | 已定：默认 bge-small-zh（~100MB/512 维），bge-m3 质量档；维度参数化，切档走 migrations |
| 7 | macOS Metal 下 TTS 延迟未验证 | 中 | 阶段 0 macOS smoke test；不达标则 macOS 默认云端 TTS 作临时方案（需产品决策） |
| 8 | 主动开口的产品定义仍未决 | 中 | 架构预留 TriggerSource，决策延后到阶段 2 结束 |
| 9 | 多音色管理边界蔓延 | 中 | 2.4 单槽位；阶段 2 列表+切换；不引入对象元数据 |
| 10 | 壳侧麦克风采集的平台权限差异 | 中 | 阶段 0 第一周在目标平台验证采集链路；失败显式报 `MIC_NOT_AVAILABLE` |
| 11 | torch/依赖体积与打包现实（ADR-011 失败） | 中 | 分体方案保底（7.1 关键错误已按现实修正）；探测数据先行，不接受"阶段 3 才发现装不进去" |
| 12 | 记忆抽取质量退化（错误事实写入记忆） | 高 | **13.3 评测门禁**：precision ≥0.85 / recall ≥0.7（阈值随阶段 1 校准）不达标不合入；fact 可人工删除（16.2） |

---

## 10. 从原仓库的迁移清单

| 原资产 | 处置 | 迁移动作 |
| --- | --- | --- |
| Echoes-AI（CosyVoice2 封装、ASR、.pt 克隆训练与加载、TTS 分句流式） | ✅ 原样搬运 | 放入 `sidecar/echoes_sidecar/engines/`，接口适配到 4.5 |
| echoes-langgraph（guardrail→retrieve→rank→generate） | ✅ 保留，砍到最小 | 只保留 retrieve→prompt→generate 三节点，放入 `orchestration/graph.py` |
| 音色资产强约束（禁止静默回退） | ✅ 作为原则继承 | 写入 2.5 状态机与 4.5 clone 契约 |
| Java 六服务、Nacos、MySQL/MongoDB/Redis、Qdrant 服务端 | ❌ 放弃 | 不迁移 |
| SSE + turn_id 幂等协议 | ❌ 放弃（远程仅保留 turn_seq 去重） | 不迁移 |
| 多租户鉴权、admin、错误码 CONTACT_SUPPORT | ❌ 放弃 | 不迁移 |
| Vue 3 + Vite + Pinia 前端 | ✅ 保留 | 迁移到 `src/`，IPC 层重写为 `lib/ipc.ts` + `ipc_types.ts`（生成物） |

---

## 11. 决策记录索引

| ADR | 主题 | 状态 | 产出阶段 |
| --- | --- | --- | --- |
| ADR-001 | LLM 路线（本地默认 + 云端可选 + 隐私模式定义） | 待阶段 -1 基准后定稿 | 阶段 -1 |
| ADR-002 | Tauri 2 vs PyQt | 已定：Tauri 2 | v1.0 |
| ADR-003 | sqlite-vec vs LanceDB | 已定：sqlite-vec | v1.0 |
| ADR-004 | 声音克隆 MVP 范围界定（单槽位、无对象元数据） | 已定：见 2.4 | v1.1 |
| ADR-005 | 远程大脑预留边界 | 已定：见第 8 节 | v1.0 |
| ADR-006 | 嵌入模型选型 | 已定：默认 bge-small-zh，bge-m3 质量档 | v1.2 |
| ADR-007 | 主动开口的产品定义 | 待定 | 阶段 2 结束前 |
| ADR-008 | 多音色管理引入时机 | 已定：阶段 2，轻量 | v1.1 |
| ADR-009 | 克隆技术路线（zero-shot vs fine-tune） | 决策待定；**兜底规则已写入（zero-shot 保底，见 6/阶段 0）** | 阶段 0 第一周 |
| ADR-010 | 音频播放实现（rodio vs Web Audio） | 已定：rodio | v1.2 |
| ADR-011 | 打包分体策略（torch 运行时包 vs 大安装包） | 决策待定，默认建议分体；依据 7.1 + 阶段 0 探测 | 阶段 0 第一周 |
| ADR-012 | 阶段 0 阈值校准记录（就绪/延迟 ±20%） | 占位 | 阶段 0 第四周 |
| ADR-013 | 用户数据导出/删除语义 | 已定：见 16.2 | v1.3 |
| ADR-014 | CosyVoice2 搬运环境（裸装 uv + vendored 范围 + torch 口径 + 权重通路） | 已定：见 docs/decisions/ADR-014；pynini 侦察闭环已过 | v1.4.2 |

---

## 12. 下一步动作（按顺序）

1. **启动阶段 -1**：基准脚本 + 20 轮场景（含预期要点清单）+ 交叉评分，产出 ADR-001 与档位×模型矩阵。
2. **冻结第 4 节与 3.4/3.5**：v1.4 起可冻结（唯一保留项：ADR-001 定稿后对 4.4 provider 抽象做一次复核，复核变更走变更记录）。把 4.1–4.6 签名写入代码骨架（空实现），错误码建档为 `core/errors.py` 枚举常量；骨架必须包含 mock 引擎与契约测试（13.2）。
3. **阶段 0 第一周**：Tauri 壳 + sidecar 骨架 + StdioTransport「文本→LLM→文本」；壳侧采集链路验证（风险 10）；ADR-009 spike（兜底规则生效）；**PyInstaller 体积探测（ADR-011 输入）**。
4. **阶段 0 第二周**：接 ASR + TTS（`builtin:default`），WS 二进制帧跑通「麦克风→扬声器」与分级预热；3.5 状态机上线。
5. **阶段 0 第三周**：克隆闭环（`clone_progress` + 状态机 + 错误码），替换内置音色。
6. **阶段 0 第四周**：打断三跳、分级预热、延迟预算实测校准（ADR-012）、验收逐条过（含状态机零非法迁移）。

本文档不解决「陪伴是主动还是被动」这个产品问题，但它确保：无论答案是什么，TriggerSource 抽象已经在那里。

---

## 13. 测试与质量保障（v1.3 新增）

### 13.1 测试金字塔

| 层 | 对象 | 是否依赖模型 | 运行时机 |
| --- | --- | --- | --- |
| L1 单测 | chunker 分句（4.5 纯函数）、seq 分配、2.5 状态机、prompt 组装/截断、memory store SQL、错误码映射 | 否（纯逻辑） | 每次提交（CI） |
| L2 契约测试 | IPC schema 对拍、Transport 一致性套件、mock 引擎下 orchestration 全流程、3.5 状态机迁移| 否（mock 引擎） | 每次提交（CI） |
| L3 CPU 集成 | 真实 faster-whisper（tiny 档）+ mock TTS 的全链路（含打断时序） | 半（ASR 真实 CPU 模型） | CI（可选标记）+ 每日本机 |
| L4 GPU 冒烟 | 真实 CosyVoice2 合成/克隆、档位矩阵下延迟实测 | 是 | 本机脚本 `gpu_smoke.py`（7.2） |

### 13.2 契约测试与 schema 单一来源

1. **单一来源**：3.4 全部消息以 pydantic 模型定义在 `echoes_sidecar/ipc/schema.py`；TS 类型由 `datamodel-code-generator` 生成到 `src/lib/ipc_types.ts`（生成物入库、禁止手改）。CI 里跑 schema-drift job：重新生成并 `git diff --exit-code`，漂移即失败——TS 手改与 Python 改 schema 不同步，当场红。
2. **golden 样例**：`tests/golden/` 存每类消息的正例/反例 JSON 行，双向校验（serve 与 client 变体）。
3. **Transport 一致性套件**：同一组用例参数化跑 `Stdio` 与 `LocalWS` 实现一致性（序列、关闭、背压）。4.1 的「远程只需换 Transport」由它背书。
4. **状态机守护**：3.5 合法迁移表与用户动作矩阵机器可读化（JSON fixture），L2 断言非法迁移为零（6/阶段 0 验收 7 条）。
5. **打断基准自动化**：fixtures 中注入时延的 mock TTS + mock LLM，断言三跳预算（100/50/150ms）与总 300ms；消息级断言 `CANCELLED` 事件与音频 seq 丢弃。

### 13.3 记忆抽取评测门禁

- 评测集：≥50 条对话轮次（含偏好/事件/身份/干扰/需要替代更新的旧事实），标注期望抽取结果，放 `tests/fixtures/memory_eval/`。
- 指标与阈值：precision ≥0.85、recall ≥0.7、旧事实替代正确率 ≥0.9（阈值随阶段 1 校准，修订走 ADR）。
- 时机：任何对 extractor prompt/模型/策略的改动在合入前跑评测集；低于阈值不合入（风险 12 的执行机制）。

### 13.4 延迟与打断的现场测量

- 数据源：3.4 观测字段（`t`、`timings`）。sidecar 把每 turn 的闭环耗时写入本地日志（14.4），壳把播报侧时间戳并入。
- 本机基准脚本：`gpu_smoke.py --latency` 按档位矩阵输出 P50/P95 报告，作为 6/阶段 0 验收 2 的测量手段——**不靠肉眼掐表**。

### 13.5 覆盖率门禁

- transport / session / orchestration / memory / core：行覆盖 ≥80%（CI 强制）。
- engines：以一致性套件 + 冒烟为准，不设行覆盖硬指标（推理代码用覆盖率考💯会造出假测试）。

---

## 14. 故障与恢复语义（v1.3 新增）

### 14.1 场景 × 行为表

| 场景 | 检测 | 立即行为 | 恢复 | 用户可见 |
| --- | --- | --- | --- | --- |
| sidecar 进程崩溃 | 壳监听退出码 | 会话未落库 turn 丢弃（WAL 保护已落库数据）；UI 显示重连中 | 指数退避重启，≤3 次/2min；成功后 `hello` 重新握手，UI 回 ready。**Session 重建（v1.4）**：SessionManager 依 DB 最近 session 记录（`profile_id`/`persona_id`/`voice_id`）重建 Session 并沿用原 `session_id`——丢失的仅为未落库 turn 与滚动会话上下文（摘要与 facts 已落库，不受影响） | 非致命提示条；注入修复引导入口 |
| sidecar 连续崩溃超限 | 壳计数 | 停止重启 | 不再自动恢复 | fatal 错误卡 + 日志路径 + 「导出诊断包」按钮 |
| 克隆中断（kill/断电） | 启动自检 14.3 | 扫描 `status='training'` 孤儿行 | 置 `failed`，清理临时文件 | 引导「重录」 |
| 模型下载中断/文件损坏 | sha256 校验失败 | 删损坏文件 | 换源重试（7.3） | 下载进度条 + 重试提示 |
| 磁盘满 | SQLite/写盘 `STORAGE_ERROR` | 停止写入、保常态 | 用户清理后重试 | 明确报`STORAGE_ERROR`（3.4.1），不静默丢数据 |
| WS 意外断开（本地） | 心跳/写失败 | 关闭该 session 流 | 壳重建连接；turn 丢弃、`turn_seq` 重新对齐 | 无感/微提示 |
| GPU 驱动重置（TDR） | 引擎调用异常 | 取消当前 turn | 引擎按需重载（`MODEL_NOT_LOADED`） | 「引擎重载中」提示 |
| 强杀/断电（落库正确性） | — | SQLite WAL 回滚未提交事务 | 下次启动自检 | 无数据损坏提示 |

### 14.2 数据原子性

- SQLite **WAL 模式**常开；写操作均走 SessionManager 串行（单写者），事务边界：单个 fact/摘要/状态变更为一个事务。
- 资产文件**全部 temp+rename** 原子落盘（克隆 .pt、样本、下载文件）。
- migrations 幂等，带 `schema_version`；打开即校验版本，不符引导而非静默迁移。

### 14.3 启动自检（booting 阶段执行）

孤儿资产扫描（克隆孤儿清理）、磁盘剩余空间阈值提示、模型清单校验（可选 async 事后校验）。

### 14.4 日志与诊断

- sidecar 结构化日志（JSON lines，stdlib logging + handler），INFO 轮转保留最近 5×5MB；`t` 时钟贯穿。
- 一键导出诊断包（16.3），含日志尾部、当前设置（**脱敏**，排除 API key/样本音频）、模型清单与档位、最近 turn 的 `timings`。

---

## 15. 工程规范与技术选型（v1.3 新增）

### 15.1 版本锚定表（全部精确锁定，应用锁清单提交）

| 层 | 组件 | 锁定策略 | 备注 |
| --- | --- | --- | --- |
| sidecar | Python | **3.13.x**（ADR-014 修订） | 实际环境 = miniconda base 3.13.5，四闸/冒烟证据链全出自该解释器；torch 2.7 cp313 官方轮子在位 |
| sidecar | 环境与锁 | **uv**（`uv.lock` 入库） | 禁用 floating range：ML 依赖一律 `==` 精确锁 |
| sidecar | CosyVoice2 | vendored 钉死：上游 main `074ca6d` + Matcha-TTS pin `dd9105b3`（ADR-014） | 不追上游 HEAD；落位 `sidecar/vendor/cosyvoice2/` |
| sidecar | faster-whisper + ctranslate2 | `==` 锁定 | |
| sidecar | torch | CUDA 12.6 轮子，`==` 锁定（manifest 与锁文件同源） | 打包口径见 ADR-011 |
| sidecar | IPC/配置 | pydantic 2.x、websockets（**不引入 FastAPI**——sidecar 无 REST 面，纯 asyncio 足够，减少打包体积和依赖面） | |
| sidecar | 向量 | sqlite-vec | |
| 壳 | Rust/Tauri 2、rodio、tokio、serde | Cargo.lock 入库 | |
| 前端 | Vue 3、Vite、Pinia、TS strict | lockfile 入库 | |
| 工具链 | ruff（lint+format，100 列）、mypy（core strict / engines relaxed）、pytest、import-linter；Rust：clippy `-D warnings`、rustfmt；TS：eslint flat + prettier + vue-tsc | 配置随仓库 | |

### 15.2 依赖方向（import-linter 强制执行）

```text
main(组合根) → session/orchestration → engines/providers/memory → core
transport   → core, ipc   （与 session 平级，由 main 装配注入）
audio       → core        （AudioChunk 权威定义在 core；chunker 为纯函数模块）
ipc         → core        （唯一依赖例外：允许 pydantic）
session/orchestration/engines → audio   （消费 AudioChunk / chunker）
```

- `core/`：零第三方依赖（错误码、事件类型、AudioChunk）。
- `audio/` 与 `ipc/` 显式入图（v1.4 补缺）：`audio/` 同样零第三方依赖并进 strict 边界；`ipc/` 持有 3.4 的 pydantic 模型，是全工程唯一 pydantic 例外层。
- engines/providers/memory **禁止** import session/orchestration——保证引擎可独立测试与替换。
- orchestration **禁止** import 具体引擎模块，只允许 ABC——3.2「Provider/Engine 可替换」的静态强制。
- 禁止事项与 3.2 症状表一一对应，违规在 CI 直接红（不是 code review 靠自觉）。

### 15.3 语言规范要点

- **Python**：公共 API 100% 类型注解（mypy strict 边界 = `core/ ipc/ transport/ audio/ session/ orchestration/ memory/`）；引擎实现内部放宽但接口签名必须 strict。docstring 用中文；公共 API 的 docstring 标注对应文档小节（如 `# 契约见文档 4.5`）。无 mutable 全局状态。**推理调用一律 `asyncio.to_thread`/线程池，事件循环内禁止长阻塞**（3.2 的执行约束）。
- **Rust**：错误用 `thiserror`，采集/播放路径禁止 panic；`unwrap` 仅测试。
- **TS/Vue**：`stores` 承接 sidecar 事件归一化；组件只做渲染，不做协议解析（协议错误在 stores 层转用户文案）。
- **契约同步**：任何与本文档契约关联的代码，注释引用文档小节号；文档改契约必须同步改注释（与原仓库「文档/代码同步提交」原则同源）。

### 15.4 提交与版本化

- Conventional Commits（feat/fix/docs/refactor/test/chore）；`main` 受保护；验收条款在 PR 模板逐条勾选并引用本文档小节。
- sidecar 协议与 hello 的 `protocol_version` 走 semver：**新增消息类型/字段 = minor**（接收方必须忽略未知项，兼容）；**语义变更/删除 = major**（触发 `PROTOCOL_MISMATCH` 引导）。
- 应用语义版本在阶段 3 起用（0.x 期间以 commit 短哈希构造侧车二进制名）。

---

## 16. 隐私边界与数据可携带（v1.3 新增）

### 16.1 三模式数据去向矩阵（产品对外承诺的唯一出处）

| 数据 | 隐私模式（默认） | 混合模式 | 云端模式 |
| --- | --- | --- | --- |
| 音色样本 / 克隆产物 | 仅本机 | 仅本机 | 仅本机 |
| 对话转写（asr_final 文本） | 仅本机 | 出网（经 LLM provider 调用打包在 prompt 内） | 出网 |
| 记忆事实 / 摘要 | 仅本机 | 若抽取调用走云端 provider 则出网（跟随 4.4/5.2 规则，prompt 内含既往记忆） | 出网 |
| 嵌入/检索 | 仅本机 | 仅本机 | 仅本机 |
| 崩溃日志 / 诊断包 | 仅本机，手动导出 | 仅本机，手动导出 | 仅本机，手动导出 |

- 模式切换在 Settings 显式选择并持久化；默认 = 隐私模式。
- 云端模式下 UI 常显一行状态：「当前对话内容将发送至 <provider>」；provider 的数据政策版本号记录于设置（可追溯）。
- 本 16.1 矩阵是 6/阶段 1 验收「隐私模式下不出网」的判定依据。

### 16.2 导出 / 导入 / 删除（ADR-013 已定）

- **导出**：Settings 一键打包 zip（schema 带 `export_version`）：persona + 全部 memory_fact + 各 session_summary + voice 资产 + 设置（脱敏）。
- **导入**：校验 `export_version` 逐条合并（fact 追加、同名设置覆盖前提示）。
- **删除语义**：单条 fact 删除 = `deleted=1` + 同步移除向量行（软删，可撤销）；「忘掉一切」= 对该 profile 的硬删（向量、摘要、事实全部清除，二次确认）。导出包不含已软删除项。

### 16.3 诊断包（联动 14.4）

手动触发；内容见 14.4；**永不自动上传**。

### 16.4 半双工交互与隐私（产品说明的边角）

按住说话（PTT）是 MVP 默认：既是打断语义的来源（3.5），也回避了免提场景的回声消除（AEC）与本地回环。全双工免提（VAD+AEC）列为非目标（2.3），阶段 2 若评估需先解决终端侧 AEC。
