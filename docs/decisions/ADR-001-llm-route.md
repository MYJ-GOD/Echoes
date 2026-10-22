# ADR-001：LLM 路线（本地默认 + 云端可选 + 隐私模式定义）

- 状态：**待阶段 -1 基准数据**（依据：docs/architecture.md 6/阶段 -1、§12 步骤 3、§11 索引）
- 日期：待定稿

## 背景

Echoes 是全离线优先的语音陪伴应用；LLM 是对话质量的决定因素。候选：
本地 Ollama(Qwen2.5-7B / Qwen3-8B 量化) 与云端 DeepSeek（选择云端则隐私口径变化）。

## 待填：三路对比结果（阶段 -1 跑完即填，数据链 docs/benchmarks/results/）

| 通道 | 要点命中率（主指标） | 首 token P50（热轮） | tok/s | 人工均分 | 仲裁轮次 |
| --- | --- | --- | --- | --- | --- |
| Qwen2.5-7B（本地，Ollama 内建 4bit） | 待 judge | 0.59s | 55.7 | 待本人 | — |
| Qwen3-8B 量化（本地，think:false） | 待 judge | 0.66s | 42.4 | 待本人 | — |
| DeepSeek（云端通道，待 DEEPSEEK_API_KEY） | 待跑 | 待跑 | 待跑 | 待本人 | — |

### 首跑阶段性结论（2026-10-22，RTX 4060 Laptop 8GB = T-8G 档实测）

1. **thinking 硬前提**：qwen3 系默认开 thinking，首 token P50 8.2-11.6s，语音场景不可用；
   `think:false` 后回到 0.66s。Qwen3 作为候选必须以 think:false 口径评测与部署。
2. **qwen2.5:7b-instruct 是延迟最优原生候选**（0.59s / 55.7 tok/s，无 thinking 负担）。
3. **prompt 工程是系统性刚需（与模型无关）**：三路本地模型在 P02（身份）自称 Qwen/通义；
   P03（编病假条）均给出话术 —— 人设与安全要靠正式的 system prompt 工程 + 输出格式约束
   （markdown/emoji 需 TTS 前清洗），不能指望换模型解决。细节见 tier_matrix 实测记录。
4. judge：Ollama Cloud 免费档 410 不放行；judge 通道待 DeepSeek 官方 key（温度 0 已实现）。

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
