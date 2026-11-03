-- 迁移 0006：Grounding 异步质检结果（R4 4.3）
--
-- 为什么是列而不是新表：一条 turn 最多一份质检结果，1:1；新表只会让
-- `turn` 的每次读取多一次 JOIN。`grounding_claims` 存 JSON 数组文本
-- （unsupported claims），前端/诊断按需解析。
--
-- verdict 取值：'faithful' / 'unfaithful'；NULL = 未质检（无注入记忆、
-- judge 不可用、或质检失败）。score 为 0–1，便于后续统计分布。

ALTER TABLE turn ADD COLUMN grounding_score REAL;
ALTER TABLE turn ADD COLUMN grounding_verdict TEXT;
ALTER TABLE turn ADD COLUMN grounding_claims TEXT;
ALTER TABLE turn ADD COLUMN grounding_checked_at REAL;
