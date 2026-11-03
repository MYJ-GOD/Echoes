-- ============================================================
-- 0004_voice_kind.sql —— 支持云端音色（sample_path 可空 + engine）
--
-- 约定：本脚本不含 BEGIN/COMMIT/PRAGMA foreign_keys；事务与外键开关由
--      db/connection.py 的迁移 runner 统一管理（见 §2.6）。
-- ============================================================

CREATE TABLE voice_new (
    id            TEXT PRIMARY KEY,
    display_name  TEXT NOT NULL,
    sample_path   TEXT,
    model_path    TEXT,
    status        TEXT NOT NULL,
    quality_score REAL,
    created_at    REAL NOT NULL,
    kind          TEXT NOT NULL DEFAULT 'cloned',
    provider      TEXT,
    engine        TEXT NOT NULL DEFAULT 'cosyvoice2'
);

INSERT INTO voice_new
    (id, display_name, sample_path, model_path, status, quality_score, created_at, kind, provider, engine)
SELECT
    id, display_name, sample_path, model_path, status, quality_score, created_at, 'cloned', NULL, 'cosyvoice2'
FROM voice;

DROP TABLE voice;
ALTER TABLE voice_new RENAME TO voice;
