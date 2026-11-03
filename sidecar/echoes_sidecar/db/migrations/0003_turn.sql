-- ============================================================
-- 0003_turn.sql —— 原文落盘（推翻 §5.1「轮次明细不落库」）
--
-- 约定：本脚本不含 BEGIN/COMMIT/PRAGMA foreign_keys；事务与外键开关由
--      db/connection.py 的迁移 runner 统一管理（见 §2.6）。
-- ============================================================

CREATE TABLE turn (
    rowid          INTEGER PRIMARY KEY,   -- FTS5 external content 依赖 rowid 稳定
    turn_id        TEXT NOT NULL UNIQUE,
    session_id     TEXT NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    profile_id     TEXT NOT NULL DEFAULT 'default',
    seq            INTEGER NOT NULL,
    user_text      TEXT NOT NULL,
    assistant_text TEXT,
    tokens         TEXT NOT NULL DEFAULT '',
    status         TEXT NOT NULL CHECK (status IN ('pending', 'complete', 'cancelled', 'failed')),
    fail_reason    TEXT,
    voice_id       TEXT,
    model          TEXT,
    persona_id     TEXT,
    latency_ms     INTEGER,
    started_at     REAL NOT NULL,
    ended_at       REAL,
    superseded_by  TEXT REFERENCES turn(turn_id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX idx_turn_session_seq ON turn(session_id, seq);
CREATE INDEX        idx_turn_started     ON turn(started_at DESC);
CREATE INDEX        idx_turn_profile     ON turn(profile_id, started_at DESC);
CREATE INDEX        idx_turn_superseded  ON turn(superseded_by)
    WHERE superseded_by IS NOT NULL;

CREATE VIRTUAL TABLE turn_fts USING fts5(
    user_text,
    tokens,
    content='turn',
    content_rowid='rowid',
    tokenize='unicode61'
);

CREATE TRIGGER turn_ai AFTER INSERT ON turn BEGIN
    INSERT INTO turn_fts(rowid, user_text, tokens)
    VALUES (new.rowid, new.user_text, new.tokens);
END;

CREATE TRIGGER turn_ad AFTER DELETE ON turn BEGIN
    INSERT INTO turn_fts(turn_fts, rowid, user_text, tokens)
    VALUES ('delete', old.rowid, old.user_text, old.tokens);
END;

CREATE TRIGGER turn_au AFTER UPDATE ON turn BEGIN
    INSERT INTO turn_fts(turn_fts, rowid, user_text, tokens)
    VALUES ('delete', old.rowid, old.user_text, old.tokens);
    INSERT INTO turn_fts(rowid, user_text, tokens)
    VALUES (new.rowid, new.user_text, new.tokens);
END;

CREATE TABLE turn_chunk (
    chunk_id        TEXT PRIMARY KEY,
    turn_id         TEXT NOT NULL REFERENCES turn(turn_id) ON DELETE CASCADE,
    chunk_idx       INTEGER NOT NULL,
    text            TEXT NOT NULL,
    embedding       BLOB NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dim   INTEGER NOT NULL,
    created_at      REAL NOT NULL
);

CREATE INDEX idx_turn_chunk_turn ON turn_chunk(turn_id);

CREATE TABLE turn_memory_ref (
    turn_id TEXT NOT NULL REFERENCES turn(turn_id) ON DELETE CASCADE,
    fact_id TEXT NOT NULL REFERENCES memory_fact(id) ON DELETE CASCADE,
    weight  REAL,
    PRIMARY KEY (turn_id, fact_id)
);
CREATE INDEX idx_turn_memory_ref_fact ON turn_memory_ref(fact_id);

ALTER TABLE session ADD COLUMN title TEXT;
ALTER TABLE session ADD COLUMN archived_at REAL;

ALTER TABLE memory_fact ADD COLUMN source_turn_id TEXT
    REFERENCES turn(turn_id) ON DELETE SET NULL;

-- session_summary 外键补 ON DELETE CASCADE（0001 未带；重建表）
CREATE TABLE session_summary_new (
    session_id    TEXT PRIMARY KEY,
    summary       TEXT NOT NULL,
    up_to_turn    INTEGER NOT NULL,
    updated_at    REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES session(id) ON DELETE CASCADE
);
INSERT INTO session_summary_new (session_id, summary, up_to_turn, updated_at)
SELECT session_id, summary, up_to_turn, updated_at FROM session_summary;
DROP TABLE session_summary;
ALTER TABLE session_summary_new RENAME TO session_summary;

-- 旧序号归零：turn 表 seq 从 1 重来；旧摘要文本保留
UPDATE session_summary SET up_to_turn = 0;
