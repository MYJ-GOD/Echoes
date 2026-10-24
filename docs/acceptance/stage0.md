# 阶段 0 验收逐条核对（2026-10-23）

对照 docs/architecture.md 6/阶段 0「验收标准」七条。判定分三档：

- ✅ **已证**：有可重跑的自动化证据，且判据本身不需要真实硬件；
- ⚠️ **半证**：协议/流程侧已证，但判据里的**秒数或听感**要真机（麦克风/播放设备/ollama）；
- ⛔ **未证**：无任何证据。

> 本机环境（诚实前置，2026-10-24 实测更正）：部署实际使用的 `sidecar/.venv` **有
> torch 2.7.1+cu126（CUDA 可用）**，`~/.cache/echoes/models/CosyVoice2-0.5B` 权重就位，
> 故**真合成能跑**，TTS 侧延迟与克隆嵌入耗时**本机可采**。仍缺的是：
> ollama 未在 11434 运行（LLM 侧整链）、麦克风与播放设备（PTT、三跳、听感盲听）。
> 凡涉及这几项的秒数与听感一律 ⚠️，不以桩测试替代，也不写"应该没问题"。

## 汇总

| # | 验收条 | 判定 | 一句话 |
| --- | --- | --- | --- |
| 1 | 分级就绪 3s / 8s / 25s | ⚠️ 半证 | TTS 档实测 36.1s 冷 / 21.6s 热（冷启 ❌）；ASR 档与 UI 3s 未测 |
| 2 | 端到端延迟预算（四段） | ❌ 未达标 | 首音频 P50 2727ms（预算 500ms）、端到端 4705ms（预算 2500ms）；缺口见 ADR-012 §9 |
| 3 | 克隆无命令行 / 有进度 / 无假死 | ✅ 已证 | 三段 `clone_progress` + `clone_start/_cancel` 全程 UI 驱动 |
| 4 | 克隆后每句用该音色 / 失败不回退 | ✅ 已证 | 会话绑定生效；样本不合格即报错落 `failed`，不替换 |
| 5 | 打断 300ms + `turn_complete(CANCELLED)` | ⚠️ 半证 | 收尾与断流已证（含真进程）；300ms 分摊待真播放设备 |
| 6 | 断网全链路可用 | ⚠️ 半证 | 离线红线（权重/wetext 零网）已证；整链断网演练未做 |
| 7 | 状态机非法迁移为零 | ✅ 已证 | 合法迁移表 fixture 化，非法迁移参数化断言全拒 |

## 逐条证据

### 1. 分级就绪：3s 可交互 / 8s 开麦 / 25s 完整对话

判据要点：`hello` 是就绪的唯一载体、必需引擎齐了才放开语音按钮、就绪前不黑屏。

- `sidecar/tests/test_main_gate_ready.py`（新增 4 例）
  - `test_gate_resends_hello_and_flips_ready`：warmup 完成 → 该引擎 ready 翻真 →
    重发 `hello` + 紧跟一份 `state`（壳以最后一份为准）
  - `test_gate_blocks_booting_until_required_engines_ready` /
    `test_gate_enters_ready_when_last_required_engine_arrives`：ASR/LLM 是必需集合
    （3.5），TTS 就绪不进 gate
  - `test_warmup_failure_keeps_booting_and_does_not_lie`：warmup 失败**不发** hello、
    保持 booting（3.4.1 报错不降级）
- `sidecar/tests/test_main_preload.py::test_serve_preloads_after_handshake_before_main_loop`：
  首发 hello/booting/ready 先写出，再主线程预热（R20 loader-lock 顺序）
- `src/App.vue`：`engineState` 来自 `state` 帧，`asrReady` 来自 `hello.engines`，
  `pttEnabled` 依赖二者——UI 侧无「本地猜就绪」

**实测（2026-10-24，`hello.engines` 翻转时刻）**：TTS 档 **36.1s（冷）/ 21.6s（热）**
——冷启超 25s 预算 1.44×，热启达标。其中引擎 `warmup()` 本身 20.2–22.8s，其余是
vendored/torch 导入 + ORT CUDA EP + wetext 快照校验。详见 ADR-012 §4.1 与 §9 备选 3。

未测：ASR 档、UI 可交互 3s（要壳侧打点，`bench_latency` 只量 sidecar 内部）。

### 2. 端到端延迟（PTT→asr_final / →首 token / →首音频 / 端到端）

- 口径与工具：`docs/decisions/ADR-012-latency-baseline.md` §2-§3（含
  「`timings.*` 是绝对刻度，分段要减 `state(generating).t`」这个坑）
- `sidecar/scripts/bench_latency.py`：整链四段 P50/P95 + 预算判定，产出
  `scripts/_bench_out/latency_<stamp>.md`
- `sidecar/tests/test_bench_latency.py`（8 例）：把减法口径钉住；
  FAILED/CANCELLED 的缺段留 `None` 而非 0（记 0 会把超预算变成"达标"）
- mock 自检已跑通（三段均 <1ms，报告带 ⚠️ mock 标注，不作为校准依据）

**实测（2026-10-24，真 CosyVoice2，llm/asr 仍 mock）**：首音频 P50 **2727ms** /
P95 3194ms；端到端 P50 **4705ms** / P95 5932ms。均超预算（5.5× / 1.9×）。
同轮把「首音频」从 4211ms 压到 2727ms（流式扣帧 + 首句短切，ADR-012 §5）。
**判定 ❌**：按 ADR-012 §7.3 不改预算，缺口与处置建议见该文档 §9（需产品决策）。

未测：「输入 → 首 token」（需 ollama）、PTT → `asr_final`（需麦克风）。

### 3. 克隆全程无命令行 / 文案中性 / 有进度 / 无假死

- `sidecar/tests/test_orchestration_clone.py::test_clone_success_writes_asset_binds_voice_and_reports_progress`：
  进度序列严格等于 `recording100 → training10 → training100 → checking100`（4.5「无进度即假死」）
- `test_orchestration_clone.py::test_cancel_during_clone_discards_result`：`clone_cancel`
  在阶段边界生效，结果丢弃、音色落 `failed`
- `sidecar/tests/test_ipc_schema.py::test_golden_positive_roundtrip`：`clone_progress`
  三相位是冻结契约（改相位名会在这里红）
- `src/App.vue`：克隆入口是按钮（无需命令行）；可见文案只有「录音中 / 克隆中 /
  校验中 / 样本已收到，正在生成音色…」，无「训练 / 上传 / 云端 / 模型」字样

### 4. 克隆完成后每句回复用该音色 / 噪声样本明确报错且不回退

- `test_orchestration_graph.py::test_graph_uses_session_voice_when_bound`：会话绑了音色就用它
- `test_orchestration_graph.py::test_unbound_session_falls_back_to_builtin_voice`：**未绑**才用内置
- `test_orchestration_clone.py::test_invalid_sample_never_creates_voice_row`：样本不合格（过短/静音/削波）
  → `SAMPLE_TOO_SHORT` / `SAMPLE_TOO_NOISY`，连 voice 行都不建
- `test_orchestration_clone.py::test_engine_clone_error_marks_voice_failed_and_cleans_sample`：
  引擎失败 → `failed` + `error` 事件 + 清样本，**没有**"成功轮次被内置音色顶替"
- `sidecar/tests/test_engines_tts_cosyvoice2.py::test_cloned_voice_missing_wav_raises`：
  音色资产被删也不静默回退内置（2.5）
- `sidecar/tests/test_orchestration_clone.py::test_engine_written_prompt_asset_is_recorded_as_model_path`：
  ADR-009 真路的 `clone_<hex>.wav` 被认成 `model_path`（资产归属可审计）

### 5. 中途打断：音频 300ms 内停止 + 被打断 turn 收到 CANCELLED

- 壳侧首跳：`src-tauri/src/lib.rs::interrupt_turn`（关闸门 → flush 播放缓冲 → 发 control，不等确认）
- `src-tauri/src/ws_audio.rs::OutputGate`：闸门关闭期间丢弃下行帧（不播旧 turn 的新音频）；
  `src-tauri/src/audio.rs`：在途缓冲 600ms 上限 + 背压丢弃
- `cargo test` 20 passed，其中
  - `interrupt_cancels_in_flight_turn`：真进程 + 1500ms 片间时延，断言 `CANCELLED` 且取消早于引擎吐完
  - `shut_gate_drops_downstream_frames` / 缓冲上限与背压用例
- `sidecar/tests/test_orchestration_turn.py`：
  `test_cancel_during_speaking_stops_audio_and_returns_ready`（断流 + 仅一条 CANCELLED + 回 ready + 不发 error）、
  `test_cancel_during_generation_jumps_pending_pull`（30s 片间等待被抢掉）、
  `test_cancel_before_start_yields_cancelled_close`
- `sidecar/tests/test_orchestration_graph.py`：收尾不变式（任何路径恒一条 `turn_complete`）

待上机：100/50/150ms 三跳分摊的**毫秒数**（需真实播放设备，听 + 日志时间戳）。

### 6. 断网全链路可用（本地 LLM + TTS/ASR）

- 离线红线①：`test_engines_tts_cosyvoice2.py::test_warmup_missing_weights_raises_model_not_loaded`
  ——权重缺失只报 `MODEL_NOT_LOADED`，绝不触发 vendored 的联网 `snapshot_download`
- 离线红线②：`test_wetext_offline_patch_forces_local_files_only`（把 wetext 的
  `snapshot_download` 钉成 `local_files_only=True`）、
  `test_load_engine_weights_gate_precedes_wetext_patch`（权重闸先于 wetext 补丁）
- `test_wetext_cache_missing_raises_model_not_loaded`：fst 缺件报错而非联网补拉
- provider 面：LLM 只有 mock / ollama（本地），无云 API 分支（`_assemble_llm`）

待上机：拔网线跑完整对话（含克隆），并抓一次连接审计——自动化只能证明
"代码路径不会主动联网"，证明不了"整链在断网下仍可用"。

### 7. 3.5 状态机非法迁移为零

- `sidecar/tests/test_state_machine.py::test_illegal_transition_rejected`：合法迁移表
  （`tests/fixtures/` JSON）以外的组合**参数化全拒**
- `test_runtime_table_matches_fixture`：代码里的迁移表与 fixture 一致（改表必改 fixture）
- `test_state_machine_raises_and_keeps_state`：抛错后状态不被污染
- `test_ipc_schema.py::test_state_enum_matches_app_state`：协议里的 state 字面量与
  `AppState` 同源（不会出现"壳认识、sidecar 不认识"的状态名）

## 回归证据（本次全跑）

| 闸 | 结果 |
| --- | --- |
| `pytest -m "not heavy"` | **263 passed**, 1 deselected |
| `ruff check` | All checks passed |
| `mypy` | no issues in **36** source files |
| `lint-imports` | 2 contracts kept, 0 broken |
| `cargo test` | **20 passed** |
| `npm run build`（含 `ipc:check` + `vue-tsc`） | 通过 |
| `bench_latency.py --turns 5 --tts cosyvoice2` | 真机跑通（数字见验收 2） |

> 2026-10-24 复核（记忆存储层后）：规范环境 `sidecar/.venv`；pytest 263 + 1 deselected、mypy 36、cargo 20、`npm run build` 全通过。仓库根 `.venv` 是旧骨架环境，缺 sqlite-vec/torch，勿用于复跑。

## 未过 / 未验清单（按阻塞原因分组）

1. **验收 2 未达标（实测超预算）**：首音频 2727ms vs 500ms、端到端 4705ms vs 2500ms。
   不是「没测」，是「测了不够」——处置建议见 ADR-012 §9（需产品决策）
2. **冷启就绪超预算**：36.1s vs 25s（热启 21.6s 达标），路径见 ADR-012 §9 备选 3
3. **LLM 侧未就绪（ollama 未运行）**：整链四段的「首 token」段要 ollama；
   TTS 侧的「首 token→首音频」已本机采
4. **无音频设备**：PTT→`asr_final`、打断三跳毫秒数、克隆听感盲听（验收 2/4/5）
5. **无断网演练环境**：验收 6 的整链验证
6. 验收 4 的"每句都用该音色"在真机上还要**听**确认（代码已证绑定，听感待验）

> 复核命令见仓库根 README / PROGRESS §8「常用命令」。本文件随每次验收更新，
> 不写"预计""应该"——只有跑过的才算。
