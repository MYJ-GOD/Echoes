# Echoes 开发进度与剩余工作（2026-10-26）

> 本文是截至 **2026-10-26** 的进度快照，按「只推进开发、暂不做验收」的口径统计。
> 权威依据：[docs/architecture.md](docs/architecture.md)（§2.3 MVP 定义、§6 分阶段计划、§12 下一步动作、§15 工程规范）。
> 详细执行账本：`.superpowers/sdd/echoes-skeleton/progress.md`（本地文件，gitignored，R1–R21）。
> **完成度 = 代码 + 自动化测试到位**；不含真机麦克风/扬声器、延迟实测与产品验收。

## 1. 结论

| 范围                | 开发完成度        | 剩余开发（单人，中值）   |
| ----------------- | ------------ | ------------- |
| **阶段 0：垂直切片**     | **约 92–95%** | **约 0.5 周（延迟决策/上机）** |
| **阶段 2：克隆 UX + 远程** | **代码面 100%** | fine-tune 评估可选 |
| **阶段 3：打包分发** | **约 62%** | **约 1–1.5 周** |
| **MVP：阶段 0–1**    | **约 95–100%** | **约 0.5 周（阶段 0 收尾）** |
| **全路线：阶段 -1 → 3** | **约 85–87%** | **约 1–1.5 周** |

口径说明：

- 分母取母文档排期中点：阶段 -1（1 周）+ 阶段 0（3.5 周）+ 阶段 1（2.5 周）+ 阶段 2（2.5 周）+ 阶段 3（3.5 周）≈ **13 周**。
- **2026-10-23 追加**：持久化运行层（§3.4）、分句纯函数（§3.5）、克隆闭环（§3.6）、三跳打断（§3.7）落地。阶段 0 由 50–55% → 75% → 约 82%，剩余约 0.5–1 周 = 克隆真路 ≈0.5 周 + 联调/真机验收 ≈0.5 周。阶段 0 的**功能面已全部写完**，剩下的是真路接线与真机验收，不再是「还没写」。
- **2026-10-23 第二轮**：编排层收敛（§3.8）、克隆真路 + 分句接线（§3.9）、IPC TS 类型层与漂移守护（§3.10）落地，阶段 0 → **约 92%**。三笔技术债（编排层被绕过 / IPC TS 缺失 / 分句未接线）全部清掉。剩下 8% 不是代码：是真机数字（延迟、三跳毫秒、听感）与断网演练——**部署实际使用的 `sidecar/.venv` 实测 torch 2.7.1+cu126 / CUDA 可用**，故 TTS 侧延迟与克隆嵌入耗时本机就能采；仍缺的是 ollama（LLM 侧）与麦克风/播放设备（PTT→asr_final、三跳分摊、听感盲听）。
- **2026-10-24 实测轮**：真机整链第一次跑通（`bench_latency.py --tts cosyvoice2`），当场暴露两个只在真路才现形的 bug，都已修：① SQLite 连接跨线程（`asyncio.to_thread` 落库 → `check_same_thread` 判死）；② TTS 流式为给末段盖 `is_final` 扣住一个 chunk，把首音频推迟一整段。修后首音频 **4211 → 2727ms**、引擎级 38 字文本 **7.7 → 2.7s**。数字与判定见 [ADR-012 §4.1](docs/decisions/ADR-012-latency-baseline.md)，缺口处置见其 §9（**需产品决策**：预算是否按本地 0.5B 的物理下界校准）。
- **2026-10-24 复核**：规范环境是 `sidecar/.venv`（uv 管理，torch 2.7.1+cu126 / transformers 4.51.3 / sqlite-vec 0.1.9）。四闸复跑 **263 passed + 1 deselected**、mypy 36、`cargo test` 20、`npm run build` 通过。用仓库根 `.venv` 复跑会因缺 `sqlite-vec` 迁移依赖而红——那是旧骨架环境，不是代码回归；`uv.lock` 已补 `sqlite-vec`（原锁缺失，0002 迁移在冻结安装下无法复现）。
- **2026-10-24 第三轮（阶段 1 抽取线）**：抽取器 + 检索注入 + turn 后置异步写入 + 52 例评测管线落地（`db92e1c`）；pytest 263 → **299**；13.3 真门禁（qwen3:8b + qwen2.5 judge）P 0.917 / R 0.957 / 替代 1.000 通过（`8c4117a`）。bge-small-zh 权重已预取到 `~/.cache/echoes/models/bge-small-zh-v1.5`（512 维 / L2=1.0，真 embedder 检索命中）。阶段 1 完成约 45%，剩余 session_summary、人设卡、Settings。
- **2026-10-24 第四轮（阶段 1 摘要线）**：`session_summary` 仓储 + `SessionSummarizer` + 最近 12 轮历史 + 预算成对裁剪落地（`8697d04`）；pytest 299 → **317**；qwen3:8b 真摘要 smoke 落库成功（`用户养了一只名为豆豆的猫`）。阶段 1 完成约 60%，剩余人设卡 UI、Settings（需新增 IPC 消息，走 12.2）。
- **2026-10-24 第五轮（阶段 1 收口）**：人设卡 + Settings 按 3.4 拉取语义落地（`ab03f93`）——壳用 rusqlite 直写 `setting` 表，sidecar 每轮读取；人设覆盖走 `persona_name` / `persona_system_prompt`，provider 由 `ProviderRouter` 在 turn 边界切换。pytest 317 → **333**，cargo 20 → **25**；真机 smoke：mock 启动 → 写 settings → 下一轮切 ollama/qwen3:8b 并应用新人设。阶段 1 **代码面完成**；验收（隔天记忆引用/隐私抓包/首 token 增幅）未跑。
- **2026-10-25 第六轮（阶段 2 起步）**：音色槽位列表/切换（ADR-008）落地（`0127ee2`）——壳读 voice 表 + 写 `session.voice_id`，sidecar 每轮拉取，turn 收尾不再回写；内置音色虚拟项、只允许 ready 克隆音色；设置面板音色单选。pytest **334**，cargo **29**，npm build。阶段 2 剩余：克隆质检、LAN + 配对、终端模拟器、重连去重。
- **2026-10-25 第七轮（LAN）**：`LanWebSocketTransport` + token 配对 + 终端模拟器落地（`18e5e99`）——`--transport lan` 时 LAN WS 同时承载 JSON 与音频；hello/state 重放、断线保活；文本与 WAV 两条真机链路通过。pytest **338**。多终端并发/公网/加密不做（8.3）。
- **2026-10-25 第八轮（阶段 2 收口）**：克隆相似度质检（campplus 余弦 + `CLONE_QUALITY_LOW`）落地（`fa9f648`）；pytest 338 → **343**；npm build。阶段 2 代码面完成（音色槽位 / LAN / 终端 / 质检）；真 campplus 质检未跑（无真麦克风，用户不验收）。下一步阶段 3。
- **2026-10-25 第九轮（阶段 3 起步）**：ADR-011 split-binary 定稿 + 模型管理器落地（`686ab69`）；pytest 343 → **351**；CLI 正确识别本机 bge/CosyVoice2/qwen3。阶段 3 剩余：ONEDIR 构建、Tauri 安装器、首启引导、CI 矩阵。
- **2026-10-25 第十轮（ONEDIR + 双形态）**：sidecar ONEDIR 构建（85.3MB）+ 冻结冒烟 hello/WS + `resolve_launch`（安装包 exe / dev `sidecar/.venv`）+ Tauri bundle resource（`1d63494`）；cargo **32**；`npx tauri build --no-bundle` 通过。阶段 3 剩余：安装器、torch/CUDA 运行时下载、首启引导、CI。
- **2026-10-26 第十一轮（前端重设计）**：`App.vue` 按「安静书房 / 信纸」重做视觉与布局（信笺页眉 + 衬线正文 + 圆形按住说话 + 右侧抽屉设置），功能与 IPC 逻辑不变；补自动跟读（上翻不抢滚动）、流式光标、错误提示条、focus-visible、reduced-motion、800×600/窄屏适配。`npm run build` 通过；**未做像素级验收**（浏览器截图在当前环境不可用，仅用 DOM 度量核对 800×600 布局）。
- **2026-10-26 第十二轮（运行时包）**：`runtime.py` + `runtime_manifest.json` + `scripts/runtime_manager.py` 落地——按档位（cpu / cuda126）预构建 zip，启动注入 `sys.path` 与 DLL 目录；冻结 exe 87.5MB、有档位打印 `[runtime] injected profile=…`、无档位安静跳过；单测 351 → **372**。顺带补上 vendored cosyvoice2 未进 ONEDIR 的缺件。**未完成**：档案托管地址与真 torch 档位构建（归首启引导 + CI）。
- **2026-10-26 第十三轮（LLM 可插拔）**：ADR-016 定稿——LLM 支持「本地 Ollama / OpenAI 兼容云端」二选一，TTS/ASR/嵌入保持本地；API key 存 Windows 凭据管理器（Rust 写 / Python 读，已实测冻结 exe 取到 key 并打到真实 401）；隐私模式与云端互斥、Router 硬阻断不降级。新增 `LLM_KEY_MISSING`；设置页可填 base URL / key。pytest 372 → **388**，cargo 32 → **33**。
- MVP 定义见母文档 §2.3：阶段 0–1。

## 2. 母文档 §12 步骤对照

| 步骤 | 内容                                                  | 状态                          |
| -- | --------------------------------------------------- | --------------------------- |
| 1  | 阶段 -1：对话质量基准 + ADR-001                              | ✅ 完成                        |
| 2  | 冻结 §4 / 3.4 / 3.5 + 代码骨架 + mock 引擎 + 13.2 契约测试      | ✅ 完成                        |
| 3  | 阶段 0 第一周：壳 + sidecar 骨架 + 文本链 + 采集 + ADR-009/011 输入 | ✅ 完成                        |
| 4  | 阶段 0 第二周：ASR + TTS + WS 麦克风→扬声器 + 分级预热 + 3.5 状态机    | ✅ 代码完成（真机验收未做）              |
| 5  | 阶段 0 第三周：克隆闭环（`clone_progress` + 状态机 + 错误码 + 换音色）   | ✅ 代码完成（真机克隆未验收，见 3.6） |
| 6  | 阶段 0 第四周：三跳打断 + 延迟校准（ADR-012）+ 7 条验收                | ⚠️ 代码完成（三跳 ✅；ADR-012 口径与工具 ✅；七条已逐条核对见 [docs/acceptance/stage0.md](docs/acceptance/stage0.md)，仍差上机数字） |

## 3. 已完成

### 3.1 阶段 -1：对话质量基准

- 20 轮陪伴场景基准（人格一致性 / 记忆引用 / 情感回应）+ 双通道评分（本人 + LLM-as-judge）。
- 档位 × 模型矩阵：[docs/benchmarks/tier\_matrix.md](docs/benchmarks/tier_matrix.md)。
- ADR-001 定稿：默认 qwen3:8b（no-think，0.80）。
- 提交：`de18b47` / `ce7af53` / `eb9ef26`。

### 3.2 阶段 0 第一周

- Tauri 2 壳 + Vue 3 最小聊天界面；StdioTransport 文本链（`user_text` → `assistant_text` → `turn_complete`）。
- sidecar 冻结契约骨架：4.1–4.6 签名、3.4 / 3.5 schema 单一来源、mock 引擎、13.2 契约测试。
- Ollama provider 真路装配（`3d63984`）。
- 壳侧麦克风自检；PyInstaller ONEDIR 体积探测（ADR-011 输入，`d6d39b3`）。
- ADR-009 建档：兜底规则锁定（spike 48 小时无结论 → zero-shot，`238e43c`）。
- 提交：`45c710e` / `6f6adc3` / `d6d39b3` / `238e43c` / `448049e`。

### 3.3 阶段 0 第二周（代码闭环）

| 能力                                           | 状态 | 证据                                   |
| -------------------------------------------- | -- | ------------------------------------ |
| faster-whisper ASR（PTT 整段、final 帧、to_thread） | ✅  | `cdb11ac`；ASR 单测；**真实转写尚未上机**        |
| CosyVoice2 TTS（`builtin:default`、逐帧下行）       | ✅  | `a5ccc75` / `661888a`；L3 真 TTS 冒烟    |
| WS 音频面（0x01/0x02、seq、`is_final`、全双工）         | ✅  | `2705429` / `fe310f9`                |
| 壳侧采集（48k→16k FIR）/ rodio 播放 / PTT            | ✅  | `fe310f9`；13 Rust tests              |
| 分级预热 + 3.5 状态机                               | ✅  | R20；`b0e0846`                        |
| 组合根真路装配                                      | ✅  | 默认真路；`ECHOES_SIDECAR_MOCK=1` 强制 mock |

关键验证：

- sidecar 四闸：pytest **123**、ruff、mypy 39 files、lint-imports 全绿（`2705429`）。
- 壳：`cargo test` **13 passed**，含真进程 `ptt_audio_end_to_end`（PTT 帧 → `asr_final` → turn SUCCESS → 下行 0x02）。
- 前端：`npm run build`（vue-tsc + vite）通过。
- L3 端到端冒烟（真 CosyVoice2 + mock LLM/ASR）：t≈18.1s，3 帧 seq 0/1/2，`turn_complete SUCCESS`。
- 真机壳侧启动（mock profile）：解析端口 50237，日志 `WS 音频面已连接`。
- 乱码扫描（`[\u0400-\u04FF]`）0；工作树干净。

### 3.4 持久化运行层（2026-10-23 落地）

代码位置：`sidecar/echoes_sidecar/db/`（`paths.py` / `connection.py` / `repo.py` / `migrations/`）。

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| 可执行迁移（`0001_init.sql`，6 张业务表） | ✅ | `db/migrations/0001_init.sql`；`schema.sql` 保留为 5.1 文档镜像（`FLOAT[<dim>]` 不可执行） |
| 连接参数：WAL / 外键 ON / busy_timeout | ✅ | `db/connection.py::_apply_pragmas`；测试断言 journal_mode=wal、foreign_keys=1 |
| 迁移执行 + `user_version` 幂等 + 版本守卫 | ✅ | `db/connection.py::apply_migrations`（DB 版本高于应用 → `STORAGE_ERROR`，14.2） |
| 迁移扩展依赖声明（`-- requires:`） | ✅ | 缺扩展点名报错，不静默跳过（3.2） |
| persona / voice / session / setting 最小 CRUD | ✅ | `db/repo.py`；voice 三态 + `fail_orphans`（14.1 孤儿收敛） |
| 数据目录解析 + 可写性自检（5.3/14.3） | ✅ | `db/paths.py`；`ECHOES_DATA_DIR` 覆盖，非 ASCII/空格仅提示 |
| 组合根接线：会话从 DB 重建（沿用原 session_id） | ✅ | `main.py::_open_storage` / `_open_session`（14.1 v1.4） |
| turn 收尾落库（活跃时间 + 音色绑定，不存轮次明细） | ✅ | `graph.py::TurnGraph._persist_session`（`to_thread`，5.1/3.2） |

验证：`ruff` / `mypy`（含 db 4 文件）/ `lint-imports` 全绿；临时目录运行时自检通过（迁移→CRUD→孤儿收敛→重开 version=1、journal=wal）。

**未做**：`memory_vec`（vec0 虚表，等 sqlite-vec 依赖，移入阶段 1 的 `0002_*.sql`）；`SessionManager.serialize_turn` 仍未接线（编排层收敛见 4.5）。

### 3.5 分句纯函数（2026-10-23 落地）

`audio/chunker.py::split_sentences`（4.5 定案的 L1 对象）已实现：

- `punct`（默认）：句末标点切分，收尾符号（`」`/`"`/`）`）与连写标点（`……`/`？！`）随前句，小数点不切；
- `none`：整段一句；未知策略名 → `ValueError`（3.2 报错而非降级）；
- 单句软上限 60 字符：先按次级停顿（`，、：`）切，仍超则硬切，保证不丢字。

**已接线**（2026-10-23 第二轮，见 §3.9）：CosyVoice2 `synthesize` 先切句再逐句推理。
TTFA 的收益仍须 ADR-012 实测确认——**接线 ≠ 延迟已改善**，没有数字就不宣称。

### 3.6 克隆闭环（2026-10-23 落地，整链贯通）

代码位置：`sidecar/echoes_sidecar/orchestration/clone.py`（服务）、`transport/local_ws.py`（样本帧分流）、`main.py`（命令接入）、壳侧 `lib.rs`/`ws_audio.rs`/`App.vue`。

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| WS bit2 克隆样本帧与 PTT 帧分流 | ✅ | `local_ws.py::_feed_audio`（独立 `_clone_in` 队列）+ `collect_clone_sample`；测试断言双向不污染 |
| 引擎级样本校验（时长 / 静音 / 削波） | ✅ | `clone.py::check_sample`（≥3s、RMS ≥ -45dBFS、削波 ≤5%）→ `SAMPLE_TOO_SHORT` / `SAMPLE_TOO_NOISY` |
| `clone_progress` 三段（recording→training→checking） | ✅ | `CloneService._emit_progress`；`App.vue` 进度条 + 取消按钮 |
| 样本 temp+rename 落资产目录 | ✅ | `_atomic_write_wav`（16k 单声道 WAV，5.1 存相对路径） |
| 开工落 `training` 行 + 孤儿收敛 | ✅ | `insert_training` → `adopt_id`（引擎返回的 voice_id 接管行 ID）→ `mark_ready` |
| 成功后绑定会话，后续回复用该音色 | ✅ | `session.voice_id` + `sessions.bind_voice`；`TurnGraph._speak` 按 `voice_id or builtin:default` 取音色 |
| 失败置 failed、报错不降级 | ✅ | `_fail`：`mark_failed` + `error` 事件 + 清理样本，`2.5` 不回退 |
| 取消（`clone_cancel`） | ✅ 协作取消 | 阶段边界与引擎返回后检查；引擎内部推理不可中断（诚实边界） |
| 壳侧录音 3–6 秒 + 自动收尾 + 取消 | ✅ | `App.vue` clone 按钮/进度/错误；`lib.rs` 四个 `clone_*` 命令 |
| 克隆期间不开新 turn | ✅ | `main.py` 对 `user_text`/PTT 的 `is_cloning` 门控 |

验证：pytest 由 123 → **167 passed**（新增克隆 15、分句 12、DB 17）；`cargo test` **14 passed**（新增克隆帧 flags 用例，含真进程 `ptt_audio_end_to_end`）；`npm run build` 通过；ruff/mypy/lint-imports 全绿。

**未做**：真机录音的样本电平阈值需按实际麦克风校准（`MIN_RMS_DBFS` / 削波比）；
克隆听感与耗时未验（听感要人耳 + 播放设备，见 §3.9 的诚实边界；嵌入耗时可在本机采）。

### 3.7 三跳打断（2026-10-23 落地，阶段 0 最后一块功能）

代码位置：`sidecar/echoes_sidecar/core/cancel.py`（取消原语）、`orchestration/turn.py`（turn 任务槽）、`main.py`（接线）、壳侧 `audio.rs`（播放缓冲）/`ws_audio.rs`（下行闸门）/`lib.rs`（两条 control 命令）/`App.vue`（busy 期放开 PTT）。

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| turn 改为后台任务（stdio 主循环得以继续读 `control`） | ✅ | `TurnRunner`；打断消息不再排在 turn 之后 |
| 协作式取消（不强杀异步生成器） | ✅ | `CancelToken` + `TurnCancelled`；`turn_complete` 一定写得出去 |
| 取消可插队到 pending 取项（≤150ms 预算） | ✅ | `core/cancel.py::pull`（令牌与 `__anext__` 竞速）；`test_pull_preempts_pending_anext` |
| 取消后立即停止向 WS 产出音频 | ✅ | `TurnGraph._speak` 的 TTS 循环按 `pull` 收束；`test_cancel_during_speaking_stops_audio_and_returns_ready` 断言取消后零新帧 |
| `turn_complete(status=CANCELLED)` + 恒回 `ready` | ✅ | 收尾统一走 `finally`（异常也不会把 UI 锁在 generating） |
| `interrupt` / `cancel_turn` 两动词 | ✅ | sidecar 侧同义（都收束为 CANCELLED），差异在壳：是否立即开采集（3.4 定案） |
| 壳侧打断首跳（≤100ms 静音） | ✅ | `interrupt_turn`：关闸门 → 清播放缓冲 → 发 `control`；不等 sidecar 确认 |
| 丢弃打断前已在管道里的旧帧 | ✅ | `OutputGate`（timings 之外的第二个"在途"口径）；`turn_complete`/`state(ready\|generating)` 开门 + 超时自释放 |
| 壳侧在途缓冲上限 600ms + 背压丢弃 | ✅ | `audio.rs`：自持 `VecDeque<f32>` + `MAX_BUFFERED_SAMPLES=14400`；满则等 250ms 再丢帧并记 warn |
| busy 期放开 PTT（真 barge-in） | ✅ | `pttEnabled` 覆盖 generating/speaking；按下即 `interrupt_turn` |
| 文本输入打断（3.5 动作矩阵） | ✅ | `runner.start()` 内先打断旧 turn；`App.vue::send` 在 busy 时先发 interrupt |
| 停止播放按钮 | ✅ | `cancel_turn` 命令 + `App.vue` 停止按钮；被打断气泡标「已打断」 |
| mock 时延注入（13.3 打断基准前置） | ✅ | `MockLLMProvider` 读 `ECHOES_MOCK_CHUNK_DELAY_MS`（默认 0） |

验证：pytest 由 167 → **182 passed**（新增三跳 15 例）；`cargo test` 由 14 → **20 passed**（新增闸门丢弃、缓冲上限/背压、真进程 `interrupt_cancels_in_flight_turn`、空闲 `control` 忽略）；`npm run build` 通过；ruff/mypy(33 files)/lint-imports(2 contracts) 全绿。

**诚实边界**：sidecar 侧的"出队缓冲 300ms"以**拉取式消费**满足（TTS→WS 之间没有中间队列，`send_audio` 的 await 即节流，无缓冲故无溢出）；壳侧 600ms 是硬上限，单帧若超过上限仍整帧接收（帧是原子的，截半帧比短暂超限更糟），实际是「600ms + 至多一帧」。

### 3.8 编排层收敛到 graph.py（2026-10-23 第二轮，清技术债）

审计头号技术债：`run_turn` 是 `NotImplementedError` 而真实逻辑在 `main._run_turn`。
留着两条路径，阶段 1 接记忆检索时必然长出第二套 turn 逻辑。

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| turn 顺序的唯一实现搬进编排层 | ✅ | `orchestration/graph.py`：compose → generate → speak；`main.py` 删掉 `_run_turn` |
| 收尾不变式（恒一条 turn_complete + 恒回 ready + 落库） | ✅ | 统一 `finally`；`test_orchestration_graph.py` 13 例 |
| 4.6 串行化守卫落地 | ✅ | `SessionManager.serialize_turn`（同步 contextmanager，不变式断言）；`TurnInFlightError` |
| 编排层不认具体实现 | ✅ | `transport/base.py::AudioEgress` Protocol；`TurnDeps.egress` 可为 None |
| 取消相关用例覆盖 | ✅ | `test_orchestration_turn.py` 20 例（原语 / 任务槽 / CANCELLED 收尾三条路径） |
| 组合根只剩装配 | ✅ | `_turn_factory(graph, session, text)` 薄适配 + 固定三项 `EngineState` |

验证：pytest 182 → **198**（新增编排 33 例，删除已被覆盖的 `test_main_turn_audio.py`）；
ruff / mypy(33) / lint-imports(2) 全绿。

### 3.9 克隆真路 + 分句接线（2026-10-23 第二轮）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| `cosyvoice2.clone` 真路（替换 `NotImplementedError`） | ✅ 代码就绪 | 样本 → `voices/clone_<hex>.wav`（temp+rename）→ `add_zero_shot_spk` 算嵌入 → 返回 `clone:<hex>` |
| 无人转写样本的合成路线 | ✅ | 走 `inference_cross_lingual`（zero-shot 要求的 prompt_text ↔ wav 配对在这里不成立） |
| 音色特征只算一次 | ✅ | `_register_voices`：内置音色 + `voices/clone_*.wav` 在 warmup/启动时注册进 spk2info |
| 重启可恢复 | ✅ | 按 `voices/*.wav` 重建嵌入；**不写** `{model_dir}/spk2info.pt`（权重目录是 7.3 下载边界，保持只读） |
| 单个克隆坏了不牵连全局 | ✅ | 重建失败记 stderr 跳过，只有点它的会话拿 `VOICE_NOT_AVAILABLE` |
| `split_sentences` 接入 `synthesize` | ✅ | 逐句推理，长句按次级停顿拆到 60 字内；chunk seq 跨句连续，仅流尾 `is_final` |
| 引擎资产被记录成 `model_path` | ✅ | `clone.py::_existing_model_rel` 不再跳过 `.wav`；`test_engine_written_prompt_asset_is_recorded_as_model_path` |

验证：pytest 由 198 → **211**（引擎 +10、克隆编排 +1）。

**诚实边界**：`torch 2.7.1+cu126`（CUDA 可用）与 `~/.cache/echoes/models/CosyVoice2-0.5B`
权重本机就位，真合成能跑；缺的是**听感判据**（要人耳盲听）与**样本电平阈值**（要真麦克风）。
`test_engines_tts_cosyvoice2.py` 仍用 `_FakeVendored` 锁调用面——它证明「调用姿势对」，
不证明 vendored 的音质与 RTF；后者归 `scripts/gpu_smoke.py` 与 ADR-012 的口径。

### 3.10 IPC TS 类型层 + schema-drift 真接（2026-10-23 第二轮，清技术债）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| TS 类型由 sidecar 模型生成 | ✅ | `ipc/tsexport.py` → `src/lib/ipc_types.ts`（12 条消息 + ErrorCode + 两条方向联合） |
| 漂移守护 | ✅ | `node scripts/gen-ipc-types.mjs --check`；CI `.github/workflows/schema-drift.yml` 真接线（不再 echo） |
| 本地四闸也守 | ✅ | `test_ipc_tsexport.py::test_generated_file_matches_models` |
| 前端不再手抄协议 | ✅ | `src/lib/ipc.ts` 门面；`App.vue` 删掉本地 `SidecarFrame` 与 10 处 `invoke("字面量")` |
| 构建期拦截 | ✅ | `npm run build` 前置 `ipc:check`；`vue-tsc --noEmit` |

验证：pytest 由 211 → **231**（导出器 8 例、就绪 gate 4 例、延迟口径 8 例）；
手工追加一行后 `ipc:check` 确实非零退出（守护有牙）；`npm run build` 通过。

### 3.11 验收脚手架（2026-10-23 第二轮）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| 延迟基线工具（整链四段 P50/P95） | ✅ | `scripts/bench_latency.py`；**真机已跑**（`--tts cosyvoice2`，见 §3.12） |
| 分段口径写死（绝对刻度做差） | ✅ | `ADR-012` §2 + `test_bench_latency.py` 8 例 |
| 七条验收逐条核对 | ✅ | [docs/acceptance/stage0.md](docs/acceptance/stage0.md)：3 条已证 / 3 条半证 / **1 条实测未达标**（验收 2） |

### 3.12 真机实测轮：两个只有真路才现形的 bug（2026-10-24）

| 缺陷 | 症状 | 根因 | 证据 |
| --- | --- | --- | --- |
| SQLite 跨线程 | 每轮收尾抛 `SQLite objects created in a thread…`，turn 任务异常退出 | 3.2 要求落库入线程（`asyncio.to_thread`），而连接是主线程建的；单测 storage 是桩，CI 永远绿 | `ThreadSafeConnection`（RLock 串行）+ `check_same_thread=False`；`test_db_connection_threads.py` 5 例 |
| 流式扣帧 | 首音频要等**第二个** chunk，TTFA = 整段合成时间 | 为「末段带 is_final」扣住一个 chunk（one-chunk lookahead） | 改成「真 chunk 即发 + 零长度 `is_final` 收尾」；引擎级 7.7s→2.7s |
| （配套）首句短切 | 长回复首句可到 60 字 ≈ 12s 音频 ≈ 12s TTFA | 分句软上限只管「别太长」，没人管「首句要短」 | `split_sentences(first_max_chars=20)`；A/B 实测 -55% TTFA |

验证：pytest 239 → **243**（跨线程 5、短切 4、warmup 闸门 2、末帧语义改 2）；
`ruff` / `mypy`（34 文件）/ `lint-imports` 全绿。
报告：`sidecar/scripts/_bench_out/latency_20261024_{105459,110756}.md`（修复前/后）。

### 3.13 记忆存储层（阶段 1 第一块，2026-10-24）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| `memory_vec` 向量索引 | ✅ | `db/migrations/0002_memory_vec.sql`（头注 `-- requires: sqlite_vec`，vec0 `FLOAT[512]`） |
| sqlite-vec 扩展装载 | ✅ | `db/connection.py::_load_vec_extension`（`enable_load_extension` → load → 立刻关回） |
| 事实仓储 + 向量成对写 | ✅ | `db/memory_repo.py`（insert/supersede/touch/delete/search，事务内成对） |
| 取代语义（历史可追溯） | ✅ | `superseded_by` 只藏不删；检索面 `superseded_by IS NULL AND deleted = 0` |
| 删除即不可检索（16.2） | ✅ | 软删标记 + **向量真删**（`DELETE FROM memory_vec`） |
| 检索（KNN + profile 隔离） | ✅ | `MemoryRepo.search`：`k*4` 候选池后置过滤再截断（vec0 的 `k` 先生效） |
| `MemoryStore`（写/查/提示词） | ✅ | `memory/store.py`：`retrieve/remember/active/forget/compose_hint`；空 query 不跑前向 |
| 嵌入 provider（bge-small-zh 512） | ✅ 代码就绪 | `memory/embedding.py`：`transformers` 直载 + CLS 池化 + L2 归一化（不引 `sentence-transformers`，守住 15.1 精确锁） |
| 权重边界（7.3） | ✅ | 目录缺失 → `MODEL_NOT_LOADED`，先查目录再 import（防 hub 回退联网） |

验证：pytest 243 → **264**（仓储 11、store/嵌入 10）；
`mypy` 由 34 → **36** 文件（新增 `db/memory_repo.py`、`memory/embedding.py`、`memory/store.py`）。
**未做**（已由 §3.14 接续）：真模型 13.3 门禁、session_summary、人设卡 UI、Settings。

### 3.14 记忆抽取与检索接线（2026-10-24，阶段 1 主线）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| LLM 事实抽取（严格 JSON、四类、replaces） | ✅ | `memory/extractor.py`；`test_memory_extractor.py` 14 例 |
| 解析层隐私/敏感过滤 + 隐私模式跳过云端 | ✅ | 密码/证件/11 位数字/助手发言过滤；`cloud:*` 在隐私模式不调用 |
| 检索注入 system prompt（5.2） | ✅ | `TurnGraph._compose_messages`；`test_orchestration_memory.py` |
| 检索失败降级为无记忆 | ✅ | `MODEL_NOT_LOADED` / 库错只记 stderr，turn 仍 SUCCESS |
| turn 成功后异步抽取（不占本轮延迟） | ✅ | `_schedule_memory` + 自持任务；FAILED/CANCELLED 不写 |
| 组合根 `--memory auto/on/off` | ✅ | auto：mock 或 bge 权重缺失时关闭；`test_main_memory.py` 6 例 |
| 13.3 评测集 + 指标/门禁 | ✅ 管线 | 52 例（46 事实 / 6 替代 / 9 干扰）；`scripts/eval_memory.py`；scripted 1.000 PASS |
| 真 bge 嵌入/检索 | ✅ | 权重已预取；512 维 L2=1.0；临时库检索命中「上海出差」 |
| 真模型 13.3 门禁 | ✅ | qwen3:8b 抽取 + qwen2.5:7b judge：P 0.917 / R 0.957 / 替代 1.000（52 例，2026-10-24） |

验证：pytest 263 → **299 passed**；mypy 37；ruff / lint-imports（2 contracts）；cargo 20；npm build。
**未做**：session_summary；人设卡 UI；Settings。

### 3.15 会话滚动摘要（2026-10-24，阶段 1）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| `session_summary` 仓储 | ✅ | `SessionRepo.get_summary/save_summary`（upsert、空摘要拒绝）；`test_db_summary.py` |
| 滚动摘要器 | ✅ | `session/summary.py`：10 轮/30 分钟、旧摘要+新轮次、隐私跳过、600 字上限；`test_session_summary.py` |
| 摘要注入 + 最近 N 轮历史 | ✅ | `TurnGraph._compose_messages`：system=人设+fact+摘要，随后 12 轮历史；`test_orchestration_summary.py` |
| 预算成对裁剪 | ✅ | 先丢最旧 user+assistant，本轮输入永不裁 |
| 组合根 | ✅ | 摘要与记忆共用功能门；mock 不启用 |
| 真机摘要 | ✅ | qwen3:8b 临时库：`用户养了一只名为豆豆的猫` 落库 |

验证：pytest 299 → **317 passed**；mypy 38；ruff / lint-imports（2 contracts）。
**未做**：人设卡 UI、Settings（需新增 IPC 契约，走 12.2 变更记录）。

### 3.16 人设卡 + Settings（2026-10-24，阶段 1 收口）

按 3.4 **拉取语义**落地，**无 IPC 契约变更**：壳写 SQLite，sidecar 每轮读取。

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| `RuntimeSettings`（provider/model/privacy/persona 覆盖） | ✅ | `session/runtime.py`；`test_runtime_settings.py` |
| `ProviderRouter`（turn 边界切换 + 关闭旧客户端） | ✅ | `engines/llm/router.py`；`test_llm_router.py` |
| 每轮应用设置 + 人设覆盖 | ✅ | `TurnGraph._apply_runtime_settings`；`test_orchestration_settings.py` |
| 壳侧固定 SQL（rusqlite） | ✅ | `src-tauri/src/profile.rs`；25 Rust tests |
| 四条 Tauri 命令 | ✅ | `get_persona` / `save_persona` / `get_settings` / `save_settings` |
| 前端面板 | ✅ | `App.vue` 人设名字/提示词 + provider/model/隐私；`ipc.ts` 门面 |
| API key | ⏸ | 当前仅 mock/ollama，本地 provider 无需 key；接云端时按 16.1 走系统凭据 |
| 真机拉取 smoke | ✅ | mock 启动 → 写 settings → 下一轮 ollama/qwen3:8b + 新人设 |

验证：pytest **333 passed**；mypy 39；ruff / lint-imports；cargo **25 passed**；`npm run build`。
**边界**：切换 provider/model 首轮会冷加载（实测 qwen3:8b 切后首 token 32.9s）；隐私模式已持久化，但当前无云端 provider，实际不触发网络分支。

### 3.17 音色槽位（2026-10-25，阶段 2 起步）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| 内置音色虚拟项 + 克隆列表 | ✅ | `voices.rs::list_voices`；未就绪/失败项 UI 置灰 |
| 只允许 ready 音色选中 | ✅ | `select_voice` 校验 status；`builtin:default` 写 NULL |
| 壳写 `session.voice_id` + sidecar 每轮拉取 | ✅ | `TurnGraph._apply_runtime_settings`；`test_orchestration_settings` |
| turn 收尾不回写 voice | ✅ | `_persist_session` 只 touch，避免覆盖轮间切换 |
| 前端音色单选 + 刷新 | ✅ | 设置面板；克隆完成自动刷新 |
| 质检 `CLONE_QUALITY_LOW` | ✅ | §3.19：campplus 余弦 + 阈值 0.6 |

验证：pytest **334 passed**；cargo **29 passed**；`npm run build`。
**边界**：`quality_score` 由 §3.19 质检写入；音色切换只影响新 turn 的 TTS，旧回复不变。

### 3.18 LAN 传输 + 配对 + 终端模拟器（2026-10-25，阶段 2）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| `LanWebSocketTransport` | ✅ | `transport/lan_ws.py`；0.0.0.0 + token≥16 |
| token 配对 | ✅ | `?token=`；错误 token 1008；单活动端点 |
| JSON + 音频同信道 | ✅ | `--transport lan`；同时实现 Transport + AudioEgress |
| hello/state 重放 | ✅ | 晚接入/重连拿到最新 hello/state |
| 终端模拟器 | ✅ | `scripts/lan_terminal.py`：文本 + 16k WAV；`turn_seq` 去重 |
| 断线保活 | ✅ | `keep_alive`：客户端断开不杀 sidecar |
| 多终端并发/公网/加密 | ❌ | 8.3 明确不做 |

真机：文本 mock 回复 + WAV 6 帧 → `asr_final` → `TURN SUCCESS` → 下行 PCM。
验证：pytest **338 passed**；ruff / mypy / lint-imports。
**边界**：token 在 URL/日志明文（局域网阶段不做 TLS，8.3）；断线期间事件不重放，turn 去重是终端侧 `turn_seq`。

### 3.19 克隆相似度质检（2026-10-25，阶段 2 收口）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| campplus 相似度 | ✅ | `CosyVoice2TtsEngine.speaker_similarity`：16k 原样本 vs 24k 合成 2/3 重采样 |
| 参考文本合成 | ✅ | `CloneService._collect_reference`（用克隆音色合成一句质检文本） |
| 阈值门禁 | ✅ | <0.6 → `CLONE_QUALITY_LOW`；音色 `failed`、不绑定、清样本 |
| 质量分入库 | ✅ | `VoiceRepo.set_quality`；设置面板显示相似度百分比 |
| mock 引擎跳过 | ✅ | `getattr` 探测；旧克隆测试进度不变 |
| 真机校准 | ⬜ | 无真麦克风；阈值 0.6 待真机样本校准 |

验证：pytest **343 passed**；ruff / mypy / lint-imports；`npm run build`。
**边界**：质检只在真 CosyVoice2 路径启用；0.6 是保守初值，可能误拒/漏放。

### 3.20 ADR-011 + 模型管理器（2026-10-25，阶段 3 起步）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| ADR-011 split-binary | ✅ | `docs/decisions/ADR-011-packaging-split.md`；ONEDIR 34.9MB 基线 |
| 模型清单 | ✅ | `models/manifest.json`：bge / CosyVoice2 / whisper / Ollama |
| repo 多源 | ✅ | ModelScope → HuggingFace fallback；`test_model_manager.py` |
| file 断点 + sha256 | ✅ | Range 续传、sha 校验、`.part` 原子 rename |
| Ollama 复用 / pull | ✅ | `/api/tags` 扫描 + `/api/pull` 流式进度 |
| 缓存扫描 / CLI | ✅ | `list` / `status` / `ensure` / `verify` |
| Whisper 本地路径 | ✅ | 优先 `~/.cache/echoes/models/faster-whisper-small` |
| ONEDIR 构建 / 安装器 / 首启引导 | ⬜ | 阶段 3 后续 |

验证：pytest **351 passed**；mypy 42；ruff / lint-imports。
**边界**：模型清单未列 wetext（当前 wetext 仍走 HF cache，待接线）；torch/CUDA 运行时包下载未实现。

### 3.21 ONEDIR 构建 + 双形态 spawn（2026-10-25，阶段 3）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| PyInstaller ONEDIR | ✅ | `scripts/build_sidecar.py`：**85.3MB**，排除 torch/ML，带 migrations/assets/manifest |
| 冻结 exe 冒烟 | ✅ | `--smoke`：hello protocol 1.0 + WS 音频面 |
| dev spawn | ✅ | `<sidecar>/.venv/python -m echoes_sidecar.main`（修正此前误用根 `.venv`） |
| 安装包 spawn | ✅ | `resolve_launch` 优先 `sidecar/echoes-sidecar.exe`；release 从 resource_dir 取 |
| Tauri resource | ✅ | `bundle.resources` 映射 `sidecar/`；`beforeBuildCommand` 调 `npm run sidecar:build` |
| 安装器 / 首启 / CI | ⬜ | 阶段 3 后续 |

验证：cargo **32 passed**；`npm run sidecar:build`；`npx tauri build --no-bundle`。

### 3.22 前端重设计：安静书房 / 信纸（2026-10-26）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| 视觉方向 | ✅ | 暖纸 `#F6F1E8` + 墨 `#23201B` + 陶土 `#95512F`；全系统字体栈（离线，不加载 Google Fonts） |
| 信息层级 | ✅ | 信笺页眉（名字衬线 + 状态灯 + 音色胶囊）→ 衬线正文 → 落款式输入区 |
| 主操作 | ✅ | 84px（矮窗 72px）圆形「按住说话」；录音时细光环 2.4s 旋转 + 泛光 |
| 设置 | ✅ | 右侧抽屉（人设 / 引擎 / 音色 / 设备四段），遮罩点击与 Esc 关闭；克隆录音并入音色段 |
| 正文体验 | ✅ | 自动跟读（距底 >64px 时不再抢滚动）、流式光标、错误提示条（不再伪装成她的话）、已打断留痕 |
| 可访问性 | ✅ | 全控件 `:focus-visible`、PTT 支持键盘 Space 按住/松开、`prefers-reduced-motion` 全停 |
| 响应式 | ✅ | ≤700px 去页边界与内边距；≤620px 缩小圆钮与留白 |
| 像素级验收 | ⬜ | 当前环境浏览器截图不可用；已用同源 iframe 量 800×600：页眉 70 / 正文 349 / 输入 181，无横纵溢出 |

验证：`npm run build`（ipc:check + vue-tsc + vite）通过。**功能与 IPC 逻辑未改**，仅新增两处交互修正：
① 按住期间按钮不再置灰（disabled 元素收不到 mouseup，旧实现会一直录到上限）；
② 克隆入口从主界面移入抽屉，主界面只保留一个主动作。

### 3.23 运行时包：档位档案 + 启动注入（2026-10-26，阶段 3）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| 档位清单 | ✅ | `runtime_manifest.json`：`cpu` / `cuda126`，Python 3.13 / win_amd64，依赖与 pyproject 有漂移守卫 |
| 发现/激活 | ✅ | env `ECHOES_RUNTIME_PROFILE` > `active` 指针 > 唯一已装 > 最近安装 |
| 启动注入 | ✅ | `serve()` 首句 `inject()`：`sys.path[0]` + `torch/lib`/`nvidia/*/bin`/`*.libs` + PATH；Python 主次版本不符则跳过 |
| 档案安装 | ✅ | `install_bundle`：zip-slip 校验、sha256、暂存目录、`os.replace` 换档与回滚、写 `active` |
| 下载 | ✅ | 断点续传 + sha256，落 `<runtime>/.downloads/` |
| CLI | ✅ | `list` / `export` / `install` / `verify`（`scripts/runtime_manager.py`） |
| 冻结形态 | ✅ | 87.5MB；有档位 `[runtime] injected profile=cpu site=…`，无档位安静跳过 |
| 档案托管 + 真档位构建 | ⬜ | `bundles[].url` 仍为空；归首启引导/CI |

验证：pytest **372 passed**（新增 20）；ruff / mypy 43 files / lint-imports 2 contracts；
`npm run sidecar:build` + 冻结冒烟通过；真进程跑通 `list → export → install → inject → import`。

**顺带修复**：vendored `cosyvoice2`（2.1MB）此前没进 ONEDIR，而 `_ensure_vendor_boot()`
按 `_MEIPASS/vendor/cosyvoice2` 解析——不补的话，装上 torch 也会在 `import cosyvoice` 处失败。

### 3.24 LLM 可插拔：本地 / 云端二选一（2026-10-26，ADR-016）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| OpenAI 兼容客户端 | ✅ | `engines/llm/openai_compat.py`：SSE 流式、非流式、401/429/5xx → 契约错误码 |
| 本地兼容端点 | ✅ | 同一客户端，base_url 环回时实例名报 `openai`（非 `cloud:`），摘要/记忆不被误压 |
| 云端 key | ✅ | Windows 凭据管理器：壳 `secrets.rs` 写，sidecar `secrets.py` 读；前端只见 `hasKey` |
| 跨语言口径 | ✅ | `Entry::new_with_target(SERVICE, SERVICE, ACCOUNT)` ↔ `keyring.get_password`；实测双向 |
| 冻结形态 | ✅ | 88.0MB；`--collect-submodules keyring.backends/win32ctypes`；冻结 exe 取 key 打到真实 401 |
| 设置键 | ✅ | `llm_base_url` 新增；provider 扩 `openai`；读写校验（URL/隐私互斥） |
| 隐私矩阵 | ✅ | 写入拒绝 + Router `generate` 阻断 + 前端自动取消勾选；不静默降级 |
| 错误码 | ✅ | 追加 `LLM_KEY_MISSING`（3.4.1 只追加） |
| 首启向导 / 安装器 | ⬜ | 见 §4.4 |

验证：pytest **388 passed**（新增 14：客户端 9、密钥 4、设置 1）；ruff / mypy 43 files /
lint-imports 2 contracts；cargo **33 passed**；`npm run build`；冻结 exe 端到端取 key。

**取舍记录**：TTS/ASR/嵌入保持本地（云端克隆会让阶段 0–2 的克隆归零，语音样本出网是另一个
隐私故事）；torch 是本地 TTS 与 bge 的共同前置，所以不做「按组件分层下载」——省不掉，只添乱。

## 4. 未完成

### 4.1 阶段 0 收尾（**一半已实测，一半卡在设备/决策**）

已实测（2026-10-24）：TTS 侧延迟与三级就绪（ADR-012 §4.1）。结论是**不达标**——
首音频 2727ms（预算 500）、端到端 4705ms（预算 2500）、冷启就绪 36.1s（预算 25s）。
按 ADR-012 §7.3 不改预算，缺口处置建议在其 §9，**需要产品/母文档决策**。

仍缺的三块是 ollama（LLM 侧整链）与麦克风/播放设备（PTT、三跳、听感）：

1. **延迟基线补齐「输入 → 首 token」段**：起 ollama（11434）→
   `python scripts/bench_latency.py --turns 10 --real`。
2. **PTT → `asr_final` ≤600ms**：脚本不覆盖（要真麦克风），人工 + 日志时间戳。
3. **打断三跳 100/50/150ms**：需真实播放设备；协议侧已由 `cargo test interrupt_*` 与
   `test_cancel_during_*` 定性覆盖。
4. **克隆听感 + 样本电平阈值**：zero-shot 嵌入耗时与相似度听感未验；
   `MIN_RMS_DBFS` / 削波比要按实际麦克风校准；断网整链演练一并做（验收 6）。

进度逐条见 [docs/acceptance/stage0.md](docs/acceptance/stage0.md)（3 已证 / 3 半证 / 1 未达标）。

### 4.2 阶段 1：记忆与人设（2–3 周）

- ✅ 存储（§3.13）、抽取（§3.14）、检索（§3.14）、摘要（§3.15）、人设/Settings（§3.16）——**代码面完成**。
- ⬜ 验收未跑（按当前决定暂缓）：隔天引用事实、隐私模式抓包、首 token 增幅 ≤200ms。

### 4.3 阶段 2：克隆 UX + 远程（2–3 周）

- ✅ 音色槽位（§3.17）、LAN + token 配对 + 终端模拟器 + 断线保活（§3.18）、克隆质检（§3.19）。
- ⬜ fine-tune 质量升级评估（可选，不阻塞阶段 3）。
- 不做：多终端并发 / 公网 / 端到端加密（8.3）。

### 4.4 阶段 3：打包与分发（3–4 周）

- ✅ ADR-011 split-binary（§3.20）；✅ 模型管理器（§3.20）；✅ ONEDIR 构建 + 双形态 spawn + Tauri resource（§3.21）；✅ 运行时档位档案 + 启动注入 + 管理 CLI（§3.23）；✅ LLM 本地/云端可插拔 + 凭据管理器（§3.24，ADR-016）。
- ⬜ 运行时档案托管（`bundles[].url`）与真 torch/cpu、torch/cu126 档位构建。
- ⬜ Tauri 安装器（NSIS/MSI）与基础包体积检查。
- ⬜ 首次启动向导：硬件检测 → 档位推荐 → 运行时/模型下载 → LLM 选择（Ollama 或云端 key）→ 写 `first_run_done`。
- ⬜ 三平台 CI（CPU 面）。
- 现状：注入链路、档案机制、LLM 双后端与密钥链路已通；档案未上传，首启与安装器未做。

### 4.5 技术债（2026-10-23 审计发现，不阻塞但会在阶段 1 反噬）

- ~~**编排层被绕过**~~：**已清**（§3.8，`f01bc22`）。`graph.py::run_turn` 是唯一实现，
  `serialize_turn` 落地为守卫；阶段 1 的 retrieve 接在 `_compose_messages` 即可。
- ~~**IPC TS 类型层缺失**~~：**已清**（§3.10，`d6b93a3`）。类型由 sidecar 模型生成，
  CI 与本地四闸都判漂移；前端不再手抄协议。
- **CI 不覆盖真引擎**：`build-sidecar.yml` 现在装 CPU-safe 依赖并跑 `-m "not heavy"`；`torch` / `cosyvoice` 仍零覆盖，真引擎走本机 `gpu_smoke.py`（7.2 边界）。
- ~~**TTS 分句未接线**~~：**已接**（§3.9，`d5821ad`）。但 TTFA 收益仍未实测——
  接线不代表变快，ADR-012 出数前不许宣称延迟改善。
- **多实例共享一个数据库**：迁移已做「竞争重试 + user_version 复核」（6 进程并发首启实测全通过），但两个 sidecar 同时跑仍会共享同一 session 行；14.1 预设单实例，未做实例锁。
- **打断的宽限与自释放**（3.7 引入的三处兜底，都是"引擎/协议不配合"时的止损，不是正常路径）：① `TurnRunner` 置令牌后等 2s，超时即让旧 turn 跑完（引擎卡在模型里时）；② 壳侧下行闸门关超 1.5s 自动放行（打断时 sidecar 已无在途 turn，就不会有 `turn_complete` 来开门）；③ ASR 在途不可打断（whisper 是阻塞 CPU 调用），只保证 turn 侧可打断。
- **PTT 音频在 turn 期间靠 control 打断**：`_asr_loop` 等 turn 结束才回到 `next_utterance`，所以「turn 中途的 PTT」完全依赖壳侧按下即发 `control(interrupt)`；若哪天壳不发这条消息，音频只会堆在队列里等 turn 结束（阶段 1 做 VAD/免提时需要重看这条假设）。

## 5. 风险与已知边界（验收暂缓，风险不会自动消失）

- **真机链路未验证**：麦克风权限 / 48k 采样率、whisper 真实转写、扬声器可听性均未上机；自动化覆盖到 mock / 接口层。
- **延迟预算（实测已确认不达标）**：整链首音频 P50 **2727ms** / P95 3194ms（预算 500ms）、
  端到端 P50 **4705ms** / P95 5932ms（预算 2500/4000）；引擎成本形状
  ≈ 1.4s 固定开销 + 0.65 × 音频秒数（RTF 0.83–1.4）。已做的两个杠杆（流式去扣帧、
  首句短切 20 字）把 TTFA 从 4211 压到 2727ms，但**结构上仍够不到 500ms**。
  处置建议见 [ADR-012 §9](docs/decisions/ADR-012-latency-baseline.md)（含「开场语气词
  预合成」这条唯一能进 500ms 量级的路径），**需产品决策**。
- **8G 档显存冲突**：qwen3:8b ≈5.5GB + TTS ≈3.8GB；ADR-001 需按三跳实测复核。
- **克隆路线**：闭环、真路与相似度质检均就绪（3.6 / 3.9 / 3.19）；zero-shot 的**听感未验证**（要人耳盲听 + 播放设备）；质检阈值 0.6 为保守初值，未见真机分布。
- **克隆质检阈值**：campplus 余弦 0.6 未用真麦克风样本校准（用户不验收）；可能误拒或漏放，阶段 3 前可用真实样本复核。
- **打断**：三跳已落地（3.7），busy 期 PTT 可按下即打断；但 100/50/150ms 分摊只在 mock 下定性验证过，真机数字要等 ADR-012 的延迟实测一起量。
- **记忆**：存储/抽取/检索/评测管线/滚动摘要与 13.3 真门禁已落地（3.13–3.15；P 0.917 / R 0.957 / 替代 1.000）；bge 权重为本地预取，干净机需按 7.3 bootstrap 复现。
- **设置切换冷启动**：provider/model 切换后首轮重新加载模型（实测 qwen3:8b 切后首 token 32.9s）；隐私模式已持久化，但当前无云端 provider，实际不触发网络分支。
- **LAN 安全边界**：token 在配对 URL/日志明文；局域网阶段不做 TLS/端到端加密（8.3）；单活动端点，断线期间事件不重放（turn 去重是终端侧 `turn_seq`）。
- **打包**：ADR-011 已定 split-binary；ONEDIR（88.0MB）+ 双形态 spawn + 运行时注入已通；**档案托管 / 安装器 / 首启引导 / CI 未做**，干净机流程未验证。
- **平台**：当前 dev 形态绑定 Windows + 仓库内 `.venv`；跨平台打包未开始。

## 6. 下一步

代码面的五件事已全部落地（编排层收敛 → 克隆真路 + 分句 → 验收脚手架 → IPC 类型层）。

**A. 上机（阶段 0 收尾）**

1. ~~TTS 侧延迟~~ **已跑**（ADR-012 §4.1）；剩「输入 → 首 token」段：起 ollama（11434）
   → `.venv\Scripts\python.exe scripts\bench_latency.py --turns 10 --real`。
2. **待决策**：ADR-012 §9 的预算缺口（首音频 5.5×、端到端 1.9×、冷启 1.44×）。
   实现侧建议「按实测校准预算 + 把开场语气词预合成排进阶段 2」，需产品拍板。
3. 真麦克风：PTT→`asr_final` ≤600ms；真播放设备：三跳 100/50/150ms 分摊。
4. 克隆听感盲听 + 样本电平阈值校准；拔网线跑整链（验收 6）。
5. 每项结果回填 [docs/acceptance/stage0.md](docs/acceptance/stage0.md)。

**B. 阶段 1（记忆与人设，2–3 周）**

- ✅ 存储层（§3.13）、抽取器 + 13.3 真门禁（§3.14）、检索注入（§3.14）、滚动摘要（§3.15）、人设/Settings（§3.16）——代码面完成。
- ⬜ 验收暂缓：隔天引用事实 / 隐私模式抓包 / 首 token 增幅 ≤200ms。
- 依赖：bge-small-zh-v1.5 权重已预取；干净机需按 7.3 bootstrap 复现。

**C. 里程碑排期（2026-10-24 起，单人开发，不含验收）**

| 里程碑 | 窗口 | 主要交付 | 出口条件（自动化） |
| --- | --- | --- | --- |
| **P0 基线** | 10/24–10/27 | 规范环境/README、`uv.lock` 补 sqlite-vec、CI CPU-safe 依赖、延迟预算决策输入 | 四闸 + `cargo test` 20 + `npm run build` 全绿 |
| **阶段 1 记忆与人设** | 10/28–11/13（约 2.5 周） | `memory/extractor.py` + 50 条评测门禁、检索接入 `_compose_messages`、session_summary、人设卡 UI、Settings（provider/隐私/API key） | 评测集达标 + 四闸 + 记忆 e2e（隔天引用事实） |
| **阶段 2 克隆 UX + 远程** | 已完成（10/25） | 音色槽位 + LanWS/配对/终端/保活 + 克隆质检 | 四闸 + 配对/去重测试已过；真机验收暂缓 |
| **阶段 3 打包分发** | 进行中 | ADR-011/模型管理器/ONEDIR/双形态（已完成）、安装器、首启引导、CI | 安装包构建 + 打包后 sidecar 冷启 + 体积/离线冒烟 |

- **决策门**（不阻塞当前编码，但要在对应窗口前拍板）：
  ① ADR-012 §9 延迟预算（当前首音频 2727ms / 端到端 4705ms，预算 500/2500ms）；
  ② 8G 档 LLM+TTS 显存冲突（阶段 2 前）；
  ③ ADR-011 split-binary（阶段 3 前）。
- **并行可选项**：延迟优化（开场语气词预合成 + 首句更短 + 预热）约 1–2 周，可与阶段 1 并行；不做则接受「当前预算不达标」的产品风险。
- **阶段 1（10/24）**：代码面完成（含人设/Settings）；验收按当前决定暂缓。下一步阶段 2。
- 每个里程碑结束都跑四闸 + 壳测试 + 构建，并回填本文与 [docs/acceptance/stage0.md](docs/acceptance/stage0.md)。

## 7. 关键提交（近端）

| 提交                    | 内容                                                    |
| --------------------- | ----------------------------------------------------- |
| `1d63494`             | ONEDIR sidecar + 双形态 spawn + Tauri resource（ADR-011） |
| `686ab69`             | ADR-011 split-binary + 模型管理器（7.3） |
| `fa9f648`             | 克隆相似度质检（campplus 余弦 + CLONE_QUALITY_LOW） |
| `18e5e99`             | LAN transport + token 配对 + 终端模拟器（8.2） |
| `0127ee2`             | 音色槽位列表/切换（ADR-008） |
| `ab03f93`             | 人设卡 + Settings 拉取语义（壳直写 SQLite / 每轮应用 / provider 路由） |
| `8697d04`             | 滚动摘要 + 最近 N 轮历史 + 预算成对裁剪（5.2） |
| `8c4117a`             | 13.3 真门禁通过：独立 judge + 抽取 prompt 收紧 |
| `db92e1c`             | 记忆抽取 + 检索注入 + 后置异步写入 + 52 例评测管线 |
| `d6b93a3`             | IPC TS 类型层由 sidecar 模型生成 + schema-drift CI 真接 |
| `d5821ad`             | 分句接入引擎 + 克隆真路（zero-shot 嵌入）               |
| `f01bc22`             | 编排层收敛：turn 流程搬进 `graph.py`                     |
| `fe310f9`             | 壳侧 PTT 语音面真路：真路 spawn / WS 音频 / rodio 播放 / 48k→16k 采集 |
| `2705429`             | sidecar PTT 语音入口：WS 整段音频 → ASR → `asr_final` → turn   |
| `cef78b2`             | L3 端到端冒烟脚本入库 + ADR-014 修订 11                          |
| `b0e0846`             | 主线程预热：规避 Windows loader-lock × OpenBLAS 死锁            |
| `fe6dcc5`             | wetext 快照运行期零网（`local_files_only`）                    |
| `661888a`             | turn 音频真链接线：CosyVoice2 逐帧出壳                           |
| `a5ccc75`             | CosyVoice2 冒烟首跑：ORT-CUDA + fp16，TTFA / RTF 实测         |
| `238e43c` / `d6d39b3` | ADR-009 兜底规则 / PyInstaller 体积探测                       |
| `eb9ef26`             | 阶段 -1 关账 + ADR-001 定稿                                 |

## 8. 常用命令

> 规范环境 = `sidecar/.venv`（uv 管理，含 torch/CUDA）；仓库根 `.venv` 是旧骨架环境，勿用。

```powershell
# 依赖变更后（cwd = sidecar）
uv sync --extra dev

# sidecar 四闸（cwd = sidecar）
.venv\Scripts\pytest.exe -m "not heavy"
.venv\Scripts\ruff.exe check .
.venv\Scripts\mypy.exe
.venv\Scripts\lint-imports.exe

# 壳测试（cwd = src-tauri；假代理残留时先置 NO_PROXY）
$env:NO_PROXY="*"; cargo test

# 前端类型检查 + 构建（仓库根；build 前置 ipc:check）
npm run build
npm run ipc:types    # 协议改了就重新生成 src/lib/ipc_types.ts

# 延迟基线（cwd = sidecar；--real 需权重 + ollama）
.venv\Scripts\python.exe scripts\bench_latency.py --turns 5
.venv\Scripts\python.exe scripts\bench_latency.py --turns 10 --real

# 启动（仓库根）
$env:ECHOES_SIDECAR_MOCK="1"; npm run tauri dev   # 全 mock（无模型）
npm run tauri dev                                  # 真路（需 Ollama / whisper / CosyVoice2）

# L3 冒烟（cwd = sidecar；真 CosyVoice2，mock LLM/ASR）
.venv\Scripts\python.exe scripts\smoke_turn_e2e.py

# 13.3 记忆抽取评测（scripted=管线自检；ollama=真门禁）
.venv\Scripts\python.exe scripts\eval_memory.py --provider scripted
.venv\Scripts\python.exe scripts\eval_memory.py --provider ollama

# LAN 终端（headless sidecar；单活动端点；URL 从 stderr 取）
.venv\Scripts\python.exe -m echoes_sidecar.main --transport lan --llm mock --asr mock --tts mock
.venv\Scripts\python.exe scripts\lan_terminal.py --url "ws://<ip>:<port>/?token=..."

# 模型管理器（7.3）
.venv\Scripts\python.exe scripts\model_manager.py list
.venv\Scripts\python.exe scripts\model_manager.py ensure bge-small-zh-v1.5 cosyvoice2-0.5b

# 运行时档位（ADR-011 补充：cpu / cuda126）
.venv\Scripts\python.exe scripts\runtime_manager.py list
.venv\Scripts\python.exe scripts\runtime_manager.py export cpu --hint   # 构建机产档案用
.venv\Scripts\python.exe scripts\runtime_manager.py install cpu --from-bundle D:\runtime-cpu.zip
.venv\Scripts\python.exe scripts\runtime_manager.py verify cpu

# sidecar ONEDIR（ADR-011；仓库根 / cwd=sidecar）
npm run sidecar:build
.venv\Scripts\python.exe scripts\build_sidecar.py --smoke
```

## 9. 文档关系与更新约定

- [docs/architecture.md](docs/architecture.md)：唯一执行依据；冻结契约与变更记录以它为准。
- [README.md](README.md)：规范环境与四闸命令（`sidecar/.venv`；根 `.venv` 是旧骨架环境）。
- [docs/decisions/](docs/decisions/)：ADR-001（LLM 路线）、ADR-009（克隆路线）、ADR-012（延迟/就绪阈值校准）、ADR-014（CosyVoice2 环境）。
- [docs/acceptance/stage0.md](docs/acceptance/stage0.md)：阶段 0 七条验收逐条核对（判据 / 自动化证据 / 上机待验）。
- `.superpowers/sdd/echoes-skeleton/progress.md`：逐轮执行账本（R1–R21），含根因分析与验收证据；gitignored。
- 本文是**快照**，不是契约：每完成一个大块（克隆 / 打断 / 阶段关账）后更新第 1、4、5 节；数字会随实际实现漂移。
