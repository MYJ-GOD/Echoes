# Echoes 开发进度与剩余工作（2026-10-23）

> 本文是截至 **2026-10-23** 的进度快照，按「只推进开发、暂不做验收」的口径统计。  
> 权威依据：[docs/architecture.md](docs/architecture.md)（§2.3 MVP 定义、§6 分阶段计划、§12 下一步动作、§15 工程规范）。  
> 详细执行账本：`.superpowers/sdd/echoes-skeleton/progress.md`（本地文件，gitignored，R1–R21）。  
> **完成度 = 代码 + 自动化测试到位**；不含真机麦克风/扬声器、延迟实测与产品验收。

## 1. 结论

| 范围                | 开发完成度        | 剩余开发（单人，中值）   |
| ----------------- | ------------ | ------------- |
| **阶段 0：垂直切片**     | **约 92%**   | **约 0.5 周（几乎全是上机）** |
| **MVP：阶段 0–1**    | **约 58%**   | **约 3.5 周**     |
| **全路线：阶段 -1 → 3** | **约 32%**   | **约 8 周**   |

口径说明：

- 分母取母文档排期中点：阶段 -1（1 周）+ 阶段 0（3.5 周）+ 阶段 1（2.5 周）+ 阶段 2（2.5 周）+ 阶段 3（3.5 周）≈ **13 周**。
- **2026-10-23 追加**：持久化运行层（§3.4）、分句纯函数（§3.5）、克隆闭环（§3.6）、三跳打断（§3.7）落地。阶段 0 由 50–55% → 75% → 约 82%，剩余约 0.5–1 周 = 克隆真路 ≈0.5 周 + 联调/真机验收 ≈0.5 周。阶段 0 的**功能面已全部写完**，剩下的是真路接线与真机验收，不再是「还没写」。
- **2026-10-23 第二轮**：编排层收敛（§3.8）、克隆真路 + 分句接线（§3.9）、IPC TS 类型层与漂移守护（§3.10）落地，阶段 0 → **约 92%**。三笔技术债（编排层被绕过 / IPC TS 缺失 / 分句未接线）全部清掉。剩下 8% 不是代码：是真机数字（延迟、三跳毫秒、听感）与断网演练——**本机 `.venv` 无 torch，这部分只能上机**。
- 已完成开发量 ≈ 4.3 周（阶段 -1 的 1 周 + 阶段 0 近四周）；4.3 / 13 ≈ 32%。
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
克隆听感与耗时未验（本机无 torch，见 §3.9 的诚实边界）。

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

**诚实边界**：本机 `.venv` 无 torch，真合成跑不起来。以上全部是「代码 + L2 桩测试」，
**克隆听感、嵌入耗时、TTFA 收益均未实测**；`test_engines_tts_cosyvoice2.py` 用
`_FakeVendored` 锁调用面，不证明 vendored 真行为。

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
| 延迟基线工具（整链四段 P50/P95） | ✅ | `scripts/bench_latency.py`；mock 自检跑通并强制标注「mock 不代表真实延迟」 |
| 分段口径写死（绝对刻度做差） | ✅ | `ADR-012` §2 + `test_bench_latency.py` 8 例 |
| 七条验收逐条核对 | ✅ | [docs/acceptance/stage0.md](docs/acceptance/stage0.md)：3 条已证 / 4 条半证（差上机数字） |

## 4. 未完成

### 4.1 阶段 0 收尾（约 0.5 周，**只剩上机**）

代码面已全部写完，剩下四件事都必须在有 torch + 音频设备的机器上做（本机 `.venv`
`import torch` 直接 ModuleNotFoundError）：

1. **延迟基线与阈值校准（ADR-012）**：`python scripts/bench_latency.py --turns 10 --real`；
   四段 P50/P95 填进 ADR-012 §4，按 §7 的规则决定是否一次性 ±20% 校准。
2. **PTT → `asr_final` ≤600ms**：脚本不覆盖（要真麦克风），人工 + 日志时间戳。
3. **打断三跳 100/50/150ms**：需真实播放设备；协议侧已由 `cargo test interrupt_*` 与
   `test_cancel_during_*` 定性覆盖。
4. **克隆听感 + 样本电平阈值**：zero-shot 嵌入耗时与相似度听感未验；
   `MIN_RMS_DBFS` / 削波比要按实际麦克风校准；断网整链演练一并做（验收 6）。

进度逐条见 [docs/acceptance/stage0.md](docs/acceptance/stage0.md)（3 已证 / 4 半证）。

### 4.2 阶段 1：记忆与人设（2–3 周）

- `memory/extractor.py`、`memory/store.py` 均仍为 `NotImplementedError`；`memory_vec` 表待 sqlite-vec 依赖落地（`0002_*.sql`）。
- 需要：memory_fact 抽取 + 检索接入编排（§5.2 隐私约束）、session_summary、sqlite-vec + bge-small-zh（512 维）、人设卡 UI、Settings（provider / 隐私模式 / API key）、50 条记忆评测门禁（13.3）。

### 4.3 阶段 2：克隆 UX + 远程（2–3 周）

- 克隆质检（`CLONE_QUALITY_LOW`）、音色槽位列表 / 切换（ADR-008）。
- LanWebSocketTransport + IP / 一次性 token 配对、终端协议最小实现、断线重连去重。
- fine-tune 质量升级评估（若需要）。

### 4.4 阶段 3：打包与分发（3–4 周）

- 三平台 CI、sidecar split-binary 打包、Tauri 安装器。
- torch / CUDA / 模型权重运行时下载，模型管理器（多源 / 校验 / 缓存 / Ollama 复用扫描）。
- 首次启动硬件检测 → 档位推荐 → 下载引导。
- 现状：仅完成 PyInstaller 体积探测（`d6d39b3`）；ADR-011 未定稿。

### 4.5 技术债（2026-10-23 审计发现，不阻塞但会在阶段 1 反噬）

- ~~**编排层被绕过**~~：**已清**（§3.8，`f01bc22`）。`graph.py::run_turn` 是唯一实现，
  `serialize_turn` 落地为守卫；阶段 1 的 retrieve 接在 `_compose_messages` 即可。
- ~~**IPC TS 类型层缺失**~~：**已清**（§3.10，`d6b93a3`）。类型由 sidecar 模型生成，
  CI 与本地四闸都判漂移；前端不再手抄协议。
- **CI 不覆盖真引擎**：`build-sidecar.yml` 只装 pydantic/websockets/pytest 等骨架依赖，`torch` / `faster-whisper` / `cosyvoice` 零覆盖。
- ~~**TTS 分句未接线**~~：**已接**（§3.9，`d5821ad`）。但 TTFA 收益仍未实测——
  接线不代表变快，ADR-012 出数前不许宣称延迟改善。
- **多实例共享一个数据库**：迁移已做「竞争重试 + user_version 复核」（6 进程并发首启实测全通过），但两个 sidecar 同时跑仍会共享同一 session 行；14.1 预设单实例，未做实例锁。
- **打断的宽限与自释放**（3.7 引入的三处兜底，都是"引擎/协议不配合"时的止损，不是正常路径）：① `TurnRunner` 置令牌后等 2s，超时即让旧 turn 跑完（引擎卡在模型里时）；② 壳侧下行闸门关超 1.5s 自动放行（打断时 sidecar 已无在途 turn，就不会有 `turn_complete` 来开门）；③ ASR 在途不可打断（whisper 是阻塞 CPU 调用），只保证 turn 侧可打断。
- **PTT 音频在 turn 期间靠 control 打断**：`_asr_loop` 等 turn 结束才回到 `next_utterance`，所以「turn 中途的 PTT」完全依赖壳侧按下即发 `control(interrupt)`；若哪天壳不发这条消息，音频只会堆在队列里等 turn 结束（阶段 1 做 VAD/免提时需要重看这条假设）。

## 5. 风险与已知边界（验收暂缓，风险不会自动消失）

- **真机链路未验证**：麦克风权限 / 48k 采样率、whisper 真实转写、扬声器可听性均未上机；自动化覆盖到 mock / 接口层。
- **延迟预算**：CosyVoice2 实测 TTFA 3.7s / RTF 1.33（`a5ccc75`），另一次 6.7s / 2.09（R20，含 wetext 探测）。验收预算为端到端 P50 ≤2.5s / P95 ≤4s，存在明显差距。口径与工具已就绪（[ADR-012](docs/decisions/ADR-012-latency-baseline.md) + `bench_latency.py`），§3.9 的音色缓存与逐句合成是候选杠杆，**但都未实测**。
- **8G 档显存冲突**：qwen3:8b ≈5.5GB + TTS ≈3.8GB；ADR-001 需按三跳实测复核。
- **克隆路线**：闭环与真路代码均就绪（3.6 / 3.9），但 zero-shot 的**听感与耗时未验证**（本机无 torch）；相似度质检（`CLONE_QUALITY_LOW`）按计划推迟到阶段 2。
- **打断**：三跳已落地（3.7），busy 期 PTT 可按下即打断；但 100/50/150ms 分摊只在 mock 下定性验证过，真机数字要等 ADR-012 的延迟实测一起量。
- **持久化**：运行层已落地（3.4）；未做的是 `memory_vec`（待 sqlite-vec）与记忆抽取/检索（阶段 1）。
- **打包**：ADR-011 未定稿；干净机安装、体积、下载流程未验证。
- **平台**：当前 dev 形态绑定 Windows + 仓库内 `.venv`；跨平台打包未开始。

## 6. 下一步

代码面的五件事已全部落地（编排层收敛 → 克隆真路 + 分句 → 验收脚手架 → IPC 类型层）。

**A. 上机（阶段 0 收尾，阻塞在硬件/环境，不在代码）**

1. 装 torch（`cd sidecar && uv sync`）→ `python scripts/bench_latency.py --turns 10 --real`；
   四段 P50/P95 填 ADR-012 §4，按 §7 规则决定校准。
2. 真麦克风：PTT→`asr_final` ≤600ms；真播放设备：三跳 100/50/150ms 分摊。
3. 克隆听感盲听 + 样本电平阈值校准；拔网线跑整链（验收 6）。
4. 每项结果回填 [docs/acceptance/stage0.md](docs/acceptance/stage0.md)，逐条从 ⚠️ 转 ✅/❌。

**B. 阶段 1（记忆与人设，2–3 周）**

5. `memory/extractor.py` + `memory/store.py`（现为 `NotImplementedError`）；retrieve 接在
   `TurnGraph._compose_messages`（预算裁剪已在那里，5.2）。
6. sqlite-vec + bge-small-zh（512 维）、session_summary、人设卡 UI、Settings、50 条记忆评测门禁。

## 7. 关键提交（近端）

| 提交                    | 内容                                                    |
| --------------------- | ----------------------------------------------------- |
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

```powershell
# sidecar 四闸（cwd = sidecar）
..\.venv\Scripts\pytest.exe
..\.venv\Scripts\ruff.exe check .
..\.venv\Scripts\mypy.exe
..\.venv\Scripts\lint-imports.exe

# 壳测试（cwd = src-tauri；假代理残留时先置 NO_PROXY）
$env:NO_PROXY="*"; cargo test

# 前端类型检查 + 构建（仓库根；build 前置 ipc:check）
npm run build
npm run ipc:types    # 协议改了就重新生成 src/lib/ipc_types.ts

# 延迟基线（cwd = sidecar；--real 需权重 + ollama）
python scripts/bench_latency.py --turns 5
python scripts/bench_latency.py --turns 10 --real

# 启动（仓库根）
$env:ECHOES_SIDECAR_MOCK="1"; npm run tauri dev   # 全 mock（无模型）
npm run tauri dev                                  # 真路（需 Ollama / whisper / CosyVoice2）

# L3 冒烟（cwd = sidecar；真 CosyVoice2，mock LLM/ASR）
..\.venv\Scripts\python.exe scripts\smoke_turn_e2e.py
```

## 9. 文档关系与更新约定

- [docs/architecture.md](docs/architecture.md)：唯一执行依据；冻结契约与变更记录以它为准。
- [docs/decisions/](docs/decisions/)：ADR-001（LLM 路线）、ADR-009（克隆路线）、ADR-012（延迟/就绪阈值校准）、ADR-014（CosyVoice2 环境）。
- [docs/acceptance/stage0.md](docs/acceptance/stage0.md)：阶段 0 七条验收逐条核对（判据 / 自动化证据 / 上机待验）。
- `.superpowers/sdd/echoes-skeleton/progress.md`：逐轮执行账本（R1–R21），含根因分析与验收证据；gitignored。
- 本文是**快照**，不是契约：每完成一个大块（克隆 / 打断 / 阶段关账）后更新第 1、4、5 节；数字会随实际实现漂移。
