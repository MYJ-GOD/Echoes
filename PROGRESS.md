# Echoes 开发进度与剩余工作（2026-10-23）

> 本文是截至 **2026-10-23** 的进度快照，按「只推进开发、暂不做验收」的口径统计。  
> 权威依据：[docs/architecture.md](docs/architecture.md)（§2.3 MVP 定义、§6 分阶段计划、§12 下一步动作、§15 工程规范）。  
> 详细执行账本：`.superpowers/sdd/echoes-skeleton/progress.md`（本地文件，gitignored，R1–R21）。  
> **完成度 = 代码 + 自动化测试到位**；不含真机麦克风/扬声器、延迟实测与产品验收。

## 1. 结论

| 范围                | 开发完成度        | 剩余开发（单人，中值）   |
| ----------------- | ------------ | ------------- |
| **阶段 0：垂直切片**     | **约 55–60%** | **约 2 周**     |
| **MVP：阶段 0–1**    | **约 42%**    | **约 5 周**     |
| **全路线：阶段 -1 → 3** | **约 22–27%** | **约 10 周**    |

口径说明：

- 分母取母文档排期中点：阶段 -1（1 周）+ 阶段 0（3.5 周）+ 阶段 1（2.5 周）+ 阶段 2（2.5 周）+ 阶段 3（3.5 周）≈ **13 周**。
- **2026-10-23 追加**：持久化运行层落地（§3.4），阶段 0 完成度由 50–55% 上调至 55–60%，剩余由 2.5–3 周收敛到约 2 周（克隆 ≈1 周 + 打断 ≈0.5 周 + 联调 ≈0.5 周）。
- 已完成开发量 ≈ 3 周（阶段 -1 的 1 周 + 阶段 0 前两周）；3 / 13 ≈ 23%，故全路线取 20–25%。
- 阶段 0 单独看：前两周已代码闭环（按 3.5 周排期约 57%）；但剩余包含克隆、持久化、打断、联调，实际密度高于排期，故完成度取 50–55%，剩余按 2.5–3 周估算。
- 剩余工作量**不是线性的**：克隆闭环（含持久化）、三跳打断、联调三块比排期更密，这是完成度回落到 50–55% 的原因。
- MVP 定义见母文档 §2.3：阶段 0–1。

## 2. 母文档 §12 步骤对照

| 步骤 | 内容                                                  | 状态                          |
| -- | --------------------------------------------------- | --------------------------- |
| 1  | 阶段 -1：对话质量基准 + ADR-001                              | ✅ 完成                        |
| 2  | 冻结 §4 / 3.4 / 3.5 + 代码骨架 + mock 引擎 + 13.2 契约测试      | ✅ 完成                        |
| 3  | 阶段 0 第一周：壳 + sidecar 骨架 + 文本链 + 采集 + ADR-009/011 输入 | ✅ 完成                        |
| 4  | 阶段 0 第二周：ASR + TTS + WS 麦克风→扬声器 + 分级预热 + 3.5 状态机    | ✅ 代码完成（真机验收未做）              |
| 5  | 阶段 0 第三周：克隆闭环（`clone_progress` + 状态机 + 错误码 + 换音色）   | ❌ 未开工（前置：持久化运行层 ✅，见 3.4） |
| 6  | 阶段 0 第四周：三跳打断 + 延迟校准（ADR-012）+ 7 条验收                | ⚠️ 部分（状态机/预热已提前；打断/校准/验收未做） |

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
| turn 收尾落库（活跃时间 + 音色绑定，不存轮次明细） | ✅ | `main.py::_persist_session`（`to_thread`，5.1/3.2） |

验证：`ruff` / `mypy`（含 db 4 文件）/ `lint-imports` 全绿；临时目录运行时自检通过（迁移→CRUD→孤儿收敛→重开 version=1、journal=wal）。

**未做**：`memory_vec`（vec0 虚表，等 sqlite-vec 依赖，移入阶段 1 的 `0002_*.sql`）；`SessionManager.serialize_turn` 仍未接线（编排层收敛见 4.5）。

### 3.5 分句纯函数（2026-10-23 落地）

`audio/chunker.py::split_sentences`（4.5 定案的 L1 对象）已实现：

- `punct`（默认）：句末标点切分，收尾符号（`」`/`"`/`）`）与连写标点（`……`/`？！`）随前句，小数点不切；
- `none`：整段一句；未知策略名 → `ValueError`（3.2 报错而非降级）；
- 单句软上限 60 字符：先按次级停顿（`，、：`）切，仍超则硬切，保证不丢字。

**未接线**：CosyVoice2 `synthesize` 仍整段 `inference_zero_shot`。逐句合成的收益（TTFA 3.7s → 预算 2.5s）必须真机实测确认，接线归下一步「真机延迟基线」。

## 4. 未完成

### 4.1 阶段 0 收尾（约 2 周）

1. **克隆闭环（约 1 周）**  
   zero-shot 路线（ADR-009 兜底规则）：  
   录 3–6 秒 → 样本校验（`SAMPLE_TOO_SHORT` / `SAMPLE_TOO_NOISY`）→ 音色嵌入 → `voice_id` → 绑定当前会话 → 后续回复全用该音色；  
   `clone_progress` + 状态机 + 错误码；壳侧录制 / 进度 / 绑定 UI。  
   前置已就绪：`voice` 表 CRUD、`session.bind_voice`、错误码枚举、`CloneProgressMsg` 契约。
2. **三跳打断（约 0.5 周）**  
   已做：PTT 按下 flush 本地播放（第一跳）。  
   未做：sidecar `interrupt` / `cancel_turn`、`CANCELLED` 事件、LLM/TTS 取消、壳侧按 seq 丢弃在途音频、两侧缓冲上限、busy 期放开 PTT。
3. **联调与测试（约 0.5 周）**  
   克隆 / 打断的 L1/L2 全流程；四闸回归；错误路径（无麦克风、WS 断线、空转写、TTS 失败）。

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

- **编排层被绕过**：`orchestration/graph.py::run_turn` 与 `session/manager.py::serialize_turn` 仍是 `NotImplementedError` 且全仓无调用方；真实 turn 逻辑在 `main.py::_run_turn` + `turn_lock`。母文档 §10 要求「retrieve→prompt→generate 三节点收敛进 graph.py」、§5.2 要求上下文预算/裁剪在编排层——阶段 1 接记忆检索前必须先收口，否则会出现第二套 turn 逻辑。
- **IPC TS 类型层缺失**：`src/lib/ipc.ts` / `ipc_types.ts` 不存在，`.github/workflows/schema-drift.yml` 仍是 `echo` 占位；前端直接 `invoke` + `listen("sidecar://event")`，协议改动无漂移守护（13.2-1）。
- **CI 不覆盖真引擎**：`build-sidecar.yml` 只装 pydantic/websockets/pytest 等骨架依赖，`torch` / `faster-whisper` / `cosyvoice` 零覆盖。
- **TTS 分句**：`split_sentences` 纯函数已落地（3.5）并有 L1 覆盖，但**尚未接入引擎**——TTFA 收益需真机实测，接线前不要宣称延迟改善。

## 5. 风险与已知边界（验收暂缓，风险不会自动消失）

- **真机链路未验证**：麦克风权限 / 48k 采样率、whisper 真实转写、扬声器可听性均未上机；自动化覆盖到 mock / 接口层。
- **延迟预算**：CosyVoice2 实测 TTFA 3.7s / RTF 1.33（`a5ccc75`），另一次 6.7s / 2.09（R20，含 wetext 探测）。验收预算为端到端 P50 ≤2.5s / P95 ≤4s，存在明显差距，可能需要流式 / 分句 / 预热优化或 ADR-012 校准。
- **8G 档显存冲突**：qwen3:8b ≈5.5GB + TTS ≈3.8GB；ADR-001 需按三跳实测复核。
- **克隆路线**：ADR-009 spike 未跑，按兜底规则走 zero-shot；质量对比与说话人相似度质检推迟到阶段 2。
- **打断**：当前 busy / 非 ready 时 PTT 禁用，不具备真正 barge-in；三跳只完成第一跳。
- **持久化**：运行层已落地（3.4）；未做的是 `memory_vec`（待 sqlite-vec）与记忆抽取/检索（阶段 1）。
- **打包**：ADR-011 未定稿；干净机安装、体积、下载流程未验证。
- **平台**：当前 dev 形态绑定 Windows + 仓库内 `.venv`；跨平台打包未开始。

## 6. 下一步（建议顺序）

1. 真机延迟基线（whisper + CosyVoice2 + ollama 真路走一遍，四段耗时写进 ADR-012）——同时清掉「真机未验证」与「TTFA 超预算」两个 🔴。
2. `audio/chunker.py::split_sentences` + TTS 分句流式（缩短 TTFA 最直接的杠杆，L1 可测）。
3. 克隆闭环（zero-shot + `clone_progress` + 壳侧 UI；DB 与错误码已就绪）。
4. 三跳打断（sidecar cancel + 壳侧按 seq 丢弃 + `CANCELLED` 断言）。
5. 编排层收敛到 `graph.py`（4.5），再接阶段 1 记忆。
6. 阶段 0 开发回归（四闸 + `cargo test` + `npm run build` + L3 mock / 真 TTS）。

## 7. 关键提交（近端）

| 提交                    | 内容                                                    |
| --------------------- | ----------------------------------------------------- |
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

# 前端类型检查 + 构建（仓库根）
npm run build

# 启动（仓库根）
$env:ECHOES_SIDECAR_MOCK="1"; npm run tauri dev   # 全 mock（无模型）
npm run tauri dev                                  # 真路（需 Ollama / whisper / CosyVoice2）

# L3 冒烟（cwd = sidecar；真 CosyVoice2，mock LLM/ASR）
..\.venv\Scripts\python.exe scripts\smoke_turn_e2e.py
```

## 9. 文档关系与更新约定

- [docs/architecture.md](docs/architecture.md)：唯一执行依据；冻结契约与变更记录以它为准。
- [docs/decisions/](docs/decisions/)：ADR-001（LLM 路线）、ADR-009（克隆路线）、ADR-014（CosyVoice2 环境）。
- `.superpowers/sdd/echoes-skeleton/progress.md`：逐轮执行账本（R1–R21），含根因分析与验收证据；gitignored。
- 本文是**快照**，不是契约：每完成一个大块（克隆 / 打断 / 阶段关账）后更新第 1、4、5 节；数字会随实际实现漂移。
