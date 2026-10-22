# ADR-001：LLM 路线（本地默认 + 云端可选 + 隐私模式定义）

- 状态：**已定稿（首跑基线 2026-10-22；阶段 0 prompt 工程后二轮复测回填）**
- 依据：docs/architecture.md 6/阶段 -1、§12 步骤 3、§11 索引；证据链 docs/benchmarks/results/（judge=deepseek-flash 温度 0，单通道口径）

## 背景

Echoes 是全离线优先的语音陪伴应用；LLM 是对话质量的决定因素。候选：
本地 Ollama(Qwen2.5-7B / Qwen3-8B 量化) 与云端 DeepSeek（选择云端则隐私口径变化）。

## 待填：三路对比结果（首跑 2026-10-22，数据链 docs/benchmarks/results/）

| 通道 | 要点命中率（judge 主指标） | 首 token P50（热） | tok/s | 人工均分（已取消） | 仲裁轮次（已取消） |
| --- | --- | --- | --- | --- | --- |
| Qwen2.5-7B（本地，Ollama 内建 4bit） | **0.40** | 0.59s | 55.7 | 取消 | — |
| Qwen3-8B 量化（本地，think:false） | **0.60** | 0.66s | 42.4 | 取消 | — |
| Qwen3-4B 量化（本地，think:false，补充位） | **0.62** | 0.66s | 69.9 | 取消 | — |
| deepseek-flash（云端；judge 为同源自评，0.75 有正偏差风险） | **0.75** | 2.27s | 61.5（字符/s 近似） | 取消 | — |

### 二轮复测（2026-10-22，prompt 工程层 v2 落地后；judge=deepseek-flash 同口径）

| 通道 | 首跑 | 二轮 | 首 token P50（热） | tok/s | 判定 |
| --- | --- | --- | --- | --- | --- |
| Qwen3-8B no-think（v2） | 0.60 | **0.80** | 0.26s | 44.0 | ✅ **≥0.7 门槛通过** |
| Qwen3-4B no-think（v2） | 0.62 | **0.70** | 0.26s | 64.5 | ✅ 踩线通过（备用） |
| Qwen2.5-7B（v2） | 0.40 | 0.57 | 0.27s | 53.0 | ❌ 未达标（退役出主候选） |

> 数据链：results/<provider-model>-v2/（replies + judge_scores + summary）；
> v2 system prompt 单一来源 engines/llm/persona.py（与题集对拍锁定）。
> 注记：4b 存在「推理草稿漏入回复」形态（小模型指令遵循弱），judge 以要点命中计分
> 仍踩线——若三线阶段实测形态恶化，回 `--no-think` 之外的口子再议；8b 无此形态。

## 结论（验收问题回答：「目标硬件档位下，本地模型是否能作为默认」）

1. ~~当前 prompt 形态下本地不能作默认~~ → **二轮复测推翻（2026-10-22）**：prompt 工程层
   （v2：身份锁/诚实红线/短句口语/纯格式，单一来源 engines/llm/persona.py）落地后，
   qwen3:8b(no-think) 命中率 **0.80 ≥ 0.7** ——**条件分支命中第一支：
   T-8G 档 qwen3:8b(think:false) 本地默认成立**；qwen3:4b 0.70 备用；qwen2.5 退役出主候选。
   首跑判定（本地全线 <0.7、云端 0.75）成立前提是「无 system prompt 裸跑」，二轮已覆盖。
2. **决策（更新）**：本地默认实现路径按第 1 条交割；云端路线降为**可选 fallback**
   （用户显式授权 + 隐私模式强制禁用，下条定义生效）。命中质量随上下文增长需阶段 1
   回归（记忆抽取会话后同题集三查：record.v2 → v2.x）。
3. **provider 抽象设计深度结论（4.4 只保留项，阶段 -1 验收）**：保持 Local/Cloud 二分抽象，
   增加**能力协商位**——`think` 开关（qwen3 系）、延迟域（本地 ms 级 vs 云端秒级）、
   吞吐口径（token/s vs 字符/s 近似）在 provider 能力描述中显式声明，orchestra 不假设。
   （二轮同结论不变：OllamaLLMProvider 已按此落地 `think` 协商位，3d63984。）
4. **首跑基线价值**：judge 判分流程、题集、summary 链已端到端可复现（温度 0 + prompt 入库），
   二轮复测零额外工程。

## 隐私模式行为定义（本 ADR 定案，写进 4.4/16.1）

- **隐私模式 = 绝不出网**（默认）：禁用云端 provider、禁记忆抽取走云端、UI 明示状态。
- 云端仅作为非隐私模式的可选路线（用户显式无数值感知授权），OpenAI 兼容通道 key 不入库。

## 依据与风险评估

- 档位矩阵：docs/benchmarks/tier_matrix.md
- 评分证据：docs/benchmarks/results/（judge prompt 版本：见同一目录 judge_prompt.md 的 git 历史）
- 风险 1（人格一致性不足）：judge 单通道覆盖率 20/20 轮 × 4 路；首跑本地最高 0.62，
  低于 0.7 二轮复测门槛不采用本地默认（见结论 2 的条件分支）。
