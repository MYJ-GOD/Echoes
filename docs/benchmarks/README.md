# 阶段 -1：对话质量基准（跑测指南）

**文档依据**：docs/architecture.md「6/阶段 -1」与 §12 步骤 3。
**目标产物**：`docs/decisions/ADR-001-llm-route.md` + `tier_matrix.md` 实测数据。

## 组成

| 文件 | 用途 |
| --- | --- |
| `scenarios.json` | 20 轮固定场景题集（人格一致性 8 / 记忆引用 6 / 情感回应 6），每轮带预期要点清单 |
| `judge_prompt.md` | LLM-as-judge 系统提示词（入库，复现复检） |
| `results/<provider-model>/` | 每路模型一轮的 replies / judge_scores / human_scores / summary |
| `tier_matrix.md` | 档位×模型矩阵（实测后定稿，ADR-011 输入） |

## 双通道评测协议（单人可执行）

1. **被测通道**：`bench_llm.py run` → `replies.jsonl`（附首 token 延迟、tok/s）。
2. **judge 通道**：`bench_llm.py judge` —— 独立强模型按要点清单打分（温度 0，
   prompt 见 judge_prompt.md）。主指标 = **要点命中率**。
3. **人工通道**：`bench_llm.py human` 生成模板 → 本人逐轮 1-5 分。
4. **仲裁**：`bench_llm.py report` 输出两通道分歧（|Δ| ≥2 的轮次）→ 本人终审，
   仲裁结果直接改写 human_scores.csv 并在 notes 标注「仲裁」。

## 被测三路（文档指定）

| 通道 | 跑法 |
| --- | --- |
| 本地 Qwen2.5-7B | 本机 Ollama：`ollama pull qwen2.5:7b-instruct` → `run --provider ollama` |
| 本地 Qwen3-8B（量化） | `ollama pull qwen3:8b` → `run --provider ollama`（量化标签按 Ollama tag 写 `${model}-q4` 等） |
| 云端 DeepSeek | `run --provider openai`（环境变量 `DEEPSEEK_API_KEY`；不入库） |

## 本机运行（cwd=sidecar）

```powershell
..\.venv\Scripts\python scripts/bench_llm.py run    --provider ollama --model qwen2.5:7b-instruct
..\.venv\Scripts\python scripts/bench_llm.py judge  --provider openai --model deepseek-chat --replies ..\docs\benchmarks\results\ollama-qwen2.5-7b-instruct\replies.jsonl
..\.venv\Scripts\python scripts/bench_llm.py human  --replies ..\docs\benchmarks\results\ollama-qwen2.5-7b-instruct\replies.jsonl
..\.venv\Scripts\python scripts/bench_llm.py report --dir ..\docs\benchmarks\results\ollama-qwen2.5-7b-instruct
```

自检（无模型依赖）：`run --provider mock` → `judge --provider mock` → `report` 全链路走通。

## 环境准备

- Ollama：安装后 `ollama list` 确认模型可用；显存不足用量化 tag（冒号后缀 q4/q5）。
- 云端 judge：导出 `DEEPSEEK_API_KEY`（PowerShell：`$env:DEEPSEEK_API_KEY="sk-..."`），绝不出现在任何入库文件。
- 结果入库：results/ 下所有 jsonl/csv/summary.json 随 git 提交（评分记录是 ADR-001 证据链）。
