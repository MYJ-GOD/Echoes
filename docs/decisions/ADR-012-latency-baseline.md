# ADR-012：阶段 0 阈值校准记录（就绪 / 延迟）

- 状态：**测量脚手架就绪，真机数字待采**（阶段 0 第四周）
- 依据：docs/architecture.md 6/阶段 0 验收 1、2、5；3.4 观测字段；13.4 自动测量
- 日期：2026-10-23

## 1. 待校准的阈值（母文档原文）

| 指标 | 预算 |
| --- | --- |
| 双击打开 → UI 可交互 | ≤3s |
| ASR+LLM 就绪（可开麦） | ≤8s |
| TTS 就绪（可完整对话） | ≤25s |
| PTT 松开 → `asr_final` | ≤600ms |
| `asr_final` → 首 token | ≤700ms（模型预载后） |
| 首 token → 首音频块 | ≤500ms |
| 端到端出声 | P50 ≤2.5s / P95 ≤4s |
| 打断三跳（壳 flush / control 往返 / sidecar 取消） | ≤100 / ≤50 / ≤150ms，合计 ≤300ms |

母文档允许「阶段 0 实测一次性校准 ±20%」，校准结果记入本文档。**校准是双向的**：
实测明显优于预算时也应下调（预算放太松等于没有预算）。

## 2. 测量口径（关键，最容易算错）

`t` 与 `timings.*` 都是 sidecar 单调时钟的**绝对刻度**（自进程启动起算，3.4），
不是「本段耗时」。分段必须做差，起点用同轮的 `state(generating).t`：

```
首 token      = llm_first_token_ms - state(generating).t
首 token→音频 = tts_first_audio_ms - llm_first_token_ms
turn 总耗时   = total_ms            - state(generating).t
```

`state(generating)` 每轮必发，所以任何客户端都能算，无需给 `Timings` 加字段
（改冻结协议要走 12.2 变更记录）。

`turn_complete.timings` 的 `n` 可能小于轮数：FAILED/CANCELLED 没有首音频，
该段留空不参与统计——**不许记成 0ms**，那会让超预算看起来像达标。

## 3. 测量手段（对应关系）

| 段 | 手段 | 现状 |
| --- | --- | --- |
| 三级就绪（3/8/25s） | `hello.engines` 的 ready 翻转时刻 − 进程启动（`scripts/bench_latency.py` 日志 + `smoke_turn_e2e.py` 的 t 打印） | 脚手架就绪，**待上机** |
| `asr_final` → 首 token | `scripts/bench_latency.py`（整链，含编排/IPC） | 脚手架就绪，**待上机** |
| 首 token → 首音频 | 同上 | 脚手架就绪，**待上机** |
| 端到端出声 | 同上（`turn_total` 的 P50/P95） | 脚手架就绪，**待上机** |
| PTT → `asr_final` | 需真麦克风：`smoke_turn_e2e.py` 只走 `user_text`，不含采集与 ASR 整段上送 | **待上机（无人化不了）** |
| 打断三跳 | 协议侧：`cargo test interrupt_cancels_in_flight_turn`（真进程，断言取消早于 1500ms 片间时延）+ Python `test_cancel_during_*`（断流与收尾） | 定性 ✅ / 毫秒数 **待上机** |
| 引擎单点（TTFA / RTF） | `scripts/gpu_smoke.py --latency` | 已有历史数据（见 §4） |

> 为什么整链基准跑 `--ws off`：本基准量的是「消息面 → 引擎 → 消息面」的调度链路。
> 音频面（WS 0x02 帧、rodio 播放、三跳 flush）另行测量，混在一起无法归因。

## 4. 已落数据（历史单点，非整链）

| 来源 | 数字 | 说明 |
| --- | --- | --- |
| `a5ccc75`（T-4060 fp16） | TTFA **3.7s**，RTF **1.33** | CosyVoice2 单条合成，整段 `inference_zero_shot` |
| R20（含 wetext 探测） | TTFA **6.7s**，RTF **2.09** | 同链路 + 文本正则化探测，非稳态 |
| mock 整链（本机，2026-10-23） | 三段均 <1ms | **只证明脚手架通**，不代表真实延迟 |

结论：TTFA 3.7s 已经超过「首 token → 首音频 ≤500ms」与「端到端 P50 ≤2.5s」两项，
但这两个数都不是同口径的可比项（单条合成 vs 整链、含首次加载 vs 稳态）。因此
**本 ADR 现在不写校准结论，只锁定口径与工具**。

## 5. 本次关于 TTFA 的工程动作（未标定，不许当结论）

1. **音色特征缓存**（`engines/tts/cosyvoice2.py::_register_voices`）：vendored 在
   `zero_shot_spk_id == ''` 时**每次调用**重跑 campplus 嵌入 + speech tokenizer
   （百毫秒级）。内置音色与克隆音色都改为 warmup/clone 时注册一次 → 每轮省一次。
2. **逐句合成**（`split_sentences` 接线）：长句按次级停顿拆到 60 字内，首句更早
   出声；配合 1，逐句调用的 N 倍特征开销不存在了。
3. 两项都必须用 §3 的工具实测确认。**实测前不得对外称「延迟已改善」**
   （4.5/13.4 的口径纪律：没有数字就没有改善）。

## 6. 采集步骤（上机时照做）

```bash
# 1) 引擎单点（先确认权重就位、CUDA 可用）
cd sidecar && python scripts/gpu_smoke.py --latency

# 2) 整链四段（真引擎；LLM 需 ollama 在跑）
python scripts/bench_latency.py --turns 10 --real

# 3) 端到端连通（含 WS 音频帧）
python scripts/smoke_turn_e2e.py

# 4) 打断（真播放设备下人工：播报中按 PTT，听是否 300ms 内静音）
cd src-tauri && cargo test -- --nocapture interrupt
```

判读：`scripts/_bench_out/latency_<stamp>.md` 直接贴下表；三项都 ✅ 才算过 6.2。

## 7. 校准决策规则（预先约定，避免事后找理由）

1. 实测全绿 → **下调**明显宽松的项（例如首 token 实测 120ms，则预算降到 300ms 量级），
   记入本文档并同步母文档 6.2 表。
2. 单段超预算 ≤20% → 允许一次性校准（这是母文档给的额度），但要在本文档写清
   「为什么这 20% 是实现约束而非偷懒」。
3. 超预算 >20% → **不许改预算**，必须走优化路径（预热顺序 / 分句粒度 / 流式 chunk /
   模型档位），优化后重测。

## 8. 待办（阻塞项显式列出）

- [ ] 真机三级就绪（3/8/25s）
- [ ] 整链四段 P50/P95（`bench_latency.py --real`）
- [ ] PTT → `asr_final`（需麦克风，人工 + 日志时间戳）
- [ ] 打断三跳 100/50/150ms 分摊（需真实播放设备）
- [ ] 若 §5 两项实测无效，回退或重估分句粒度

> 环境说明（2026-10-23）：本机 `.venv` **无 torch**（`import torch` → ModuleNotFoundError），
> CosyVoice2/克隆真路只能做到「代码就绪 + L2 桩测试」，真机数字与听感必须在
> 有 torch + CUDA 的机器上采。这条限制写在这里，避免后人误以为「没测 = 没问题」。
