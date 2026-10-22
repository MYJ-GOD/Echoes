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

| 档 | LLM 候选 | 显存预算 | 量化策略 | 首token P50 | tok/s | 结论（默认/不行） |
| --- | --- | --- | --- | --- | --- | --- |
| T-8G  | qwen2.5:7b q4_K_M | TBD | q4_K_M | TBD | TBD | TBD |
| T-8G  | qwen3:8b q4_K_M   | TBD | q4_K_M | TBD | TBD | TBD |
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

## 填写协议

1. 每格数据来自 `speedy_bench`（Ollama 内建）与 `scripts/bench_llm.py run`（对话指标）
   交叉核对；大字段（显存占用）用任务管理器/nvidia-smi 记录。
2. 结论列只允许三值：`默认`（该档推荐默认路线）/`可行-非默认`/`不满足`。
3. 本矩阵改动走 ADR-011/ADR-001 变更记录；不许无实测改档位结论。
