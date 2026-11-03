-- 迁移 0007：turn 情感标签（R4 4.7 检测落库）
--
-- 只存检测结果，不在本轮改变 TTS 的 instruct（CosyVoice2 instruct 与中文情感
-- 模型另立任务）。emotion 取值见 orchestration/emotion.py；NULL = 未检测/中性。

ALTER TABLE turn ADD COLUMN emotion TEXT;
