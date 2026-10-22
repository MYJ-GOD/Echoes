# 档位×模型矩阵（阶段 -1 交付物，ADR-011 与模型管理器输入）

> 文档依据：6/阶段 -1。数据为本机实测（gpu_smoke.py + 基准脚本）；未实测格填 TBD 不许编造。
> 显存预算列 = 模型推理 + KV cache 的实际占用估算，量化策略列写实际所选量化 tag。

## 档位定义

| 档 | 硬件画像 | 说明 |
| --- | --- | --- |
| T-8G | 8GB VRAM（如 RTX 4060/3060 Ti） | 主流用户 |
| T-12G | 12GB VRAM（如 RTX 4070/3060 12G） | 基线档 |
| T-24G | 24GB VRAM（如 RTX 3090/4090） | 高质量档 |
| T-CPU | 纯 CPU（无/低 VRAM） | 保底档，明确提示受限（7/验收：不崩溃） |

## 矩阵（LLM 通道为主行；ASR/TTS/嵌入为补充行）

| 档 | LLM 候选 | 显存预算 | 量化策略 | 首token P50（热轮） | tok/s | 结论（默认/可行/不行） |
| --- | --- | --- | --- | --- | --- | --- |
| T-8G  | qwen2.5:7b-instruct（默认） | ~4.7GB | 内建 4bit | 0.59s | 55.7 | 可行-待质量证据（无 thinking 负担） |
| T-8G  | qwen3:8b 默认 thinking | ~5.2GB | 内建 4bit | 8.2s | 39.8 | **不可用**（thinking 延迟） |
| T-8G  | qwen3:8b think:false   | ~5.2GB | 内建 4bit | 0.66s | 42.4 | 可行-待质量证据 |
| T-8G  | qwen3:4b think:false   | ~2.5GB | 内建 4bit | 0.66s | 69.9 | 可行-待质量证据 |
| T-12G | qwen3:8b q8/Q5    | TBD | TBD | TBD | TBD | TBD |
| T-24G | qwen3:8b q16 + 长上下文 | TBD | none/q8 | TBD | TBD | TBD |
| T-24G | 云端 DeepSeek 对照 | n/a | n/a | 实测网络 | n/a | 参照系 |
| T-CPU | qwen2.5:7b q4 CPU | RAM | q4_K_M | TBD | TBD | TBD |

## 补充行（其余引擎，供 13.1 与 ADR-011 体积核算）

| 档 | 组件 | 模型 | 占用 | 备注 |
| --- | --- | --- | --- | --- |
| 全档 | ASR | faster-whisper（base/small 级按档） | TBD | CPU 路径可跑（阶段 0 接入） |
| 全档 | TTS | CosyVoice2 | TBD | VRAM 大头（阶段 0 搬运后实测） |
| 全档 | 嵌入 | bge-small-zh（默认）/ bge-m3（质量档） | ~100MB / TBD | ADR-006 已定 |

## 实测记录（T-8G：RTX 4060 Laptop 8GB，2026-10-22）

环境：Ollama 0.24.0 / 显存 8188MiB / 题集 docs/benchmarks/scenarios.json（20 轮，persona system 提示）。

- 冷载入（首 token 含模型载入）：qwen3:8b 29-39s、qwen3:4b 11s —— 分级就绪 gate 的实测依据。
- thinking 口径：qwen3 默认开 thinking，Ollama 0.24 将推理放独立字段（content 干净），但
  推理时间全部计入首 token：8b P50 8.2s / 4b P50 11.6s —— **语音场景不可用**。
  `think:false` 后 8b/4b 首 token P50 均 0.66s ✅（产品硬前提：qwen3 系必须显式关 thinking）。
- 吞吐：8b ~42 tok/s、4b ~70 tok/s（no-think 口径）；qwen2.5:7b-instruct ~56 tok/s
  （无 thinking 负担，首 token 冷热样本均稳定 ~0.59-0.69s，延迟最优的原生候选）。
- judge 通道：Ollama Cloud 免费账号调用 deepseek-v3.1:671b-cloud / qwen3-vl:235b-cloud
  均 410 Gone（登录有效但免费档不放行）—— judge 需 DeepSeek 官方 API key（DEEPSEEK_API_KEY）
  或 Ollama 订阅；本地 8B 当 judge 有同源偏差，不采用。
- 质量观察（无 judge，人工抽查）：三路本地模型都自称「通义千问/Qwen」（P02 身份先验
  压过 persona 提示）；P03（编病假条）三路均给出话术 —— qwen3:4b 教「如何不被怀疑」、
  qwen3:8b 列模板、qwen2.5 说教后仍给借口清单 —— 安全边界靠现有人设提示不可达，需要
  prompt 工程正式化（阶段 0 落 demonstration + 输出格式约束 + 安全条款）。
- 输出格式：回复普遍带 markdown/emoji/列表 —— **TTS 前文本清洗是产品刚需求**（sidecar 层职责）。

## 填写协议

1. 每格数据来自 `speedy_bench`（Ollama 内建）与 `scripts/bench_llm.py run`（对话指标）
   交叉核对；大字段（显存占用）用任务管理器/nvidia-smi 记录。
2. 结论列只允许三值：`默认`（该档推荐默认路线）/`可行-非默认`/`不满足`。
3. 本矩阵改动走 ADR-011/ADR-001 变更记录；不许无实测改档位结论。
