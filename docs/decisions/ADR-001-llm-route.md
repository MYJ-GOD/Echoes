# ADR-001：LLM 路线（本地默认 + 云端可选 + 隐私模式定义）

- 状态：**待阶段 -1 基准数据**（依据：docs/architecture.md 6/阶段 -1、§12 步骤 3、§11 索引）
- 日期：待定稿

## 背景

Echoes 是全离线优先的语音陪伴应用；LLM 是对话质量的决定因素。候选：
本地 Ollama(Qwen2.5-7B / Qwen3-8B 量化) 与云端 DeepSeek（选择云端则隐私口径变化）。

## 待填：三路对比结果（阶段 -1 跑完即填，数据链 docs/benchmarks/results/）

| 通道 | 要点命中率（主指标） | 首token P50 | tok/s | 人工均分 | 仲裁轮次 |
| --- | --- | --- | --- | --- | --- |
| Qwen2.5-7B（本地） | TBD | TBD | TBD | TBD | TBD |
| Qwen3-8B 量化（本地） | TBD | TBD | TBD | TBD | TBD |
| DeepSeek（云端，judge=deepseek-chat 本人仲裁复核） | TBD | TBD | TBD | TBD | TBD |

## 待填：目标硬件下的结论

- 阶段 -1 验收的问题：「**目标硬件档位下，本地模型是否能作为默认**」→ 本地默认（TBD 档）
  或云端默认（TBD）。
- provider 抽象设计深度结论（4.4 复核唯一保留项，12.2）：TBD——本地/云端是否需要
  差异化接口？当前判断：不需要（TBD 复核后回写）。

## 隐私模式行为定义（本 ADR 内定案，默认后被写进 4.4/16.1）

- 默认：**隐私模式 = 绝不出网**（禁用云端 provider；记忆抽取本地执行）。
- 若云端默认成立：隐私模式 = 明确提示并禁用云端调用 + 抽取本地化（跟随 provider，5.2）。

## 依据与风险评估（结论后回填）

- 档位矩阵：docs/benchmarks/tier_matrix.md
- 评分证据：docs/benchmarks/results/（judge prompt 版本：见同一目录 judge_prompt.md 的 git 历史）
- 风险 1（人格一致性不足）：双通道评测覆盖率 20/20 轮；低于人工均分 3.5 不采用本地默认。
