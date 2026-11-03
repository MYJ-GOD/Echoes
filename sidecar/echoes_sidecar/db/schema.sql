-- Echoes sidecar 数据库（文档 5.1 Schema v1 原样镜像；修改需先改母文档并走变更记录）
-- 接线时机：阶段 0 第二周（§12 步骤 4）；数据目录治理见文档 5.3。

-- 人设
CREATE TABLE persona (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);

-- 音色资产（元数据；克隆产出文件在资产目录下，以 id 命名，格式视 ADR-009）
-- 无「归属人」「关系」等字段，MVP 不引入克隆对象概念
CREATE TABLE voice (
    id            TEXT PRIMARY KEY,          -- uuid；保留 ID builtin:default 不落库
    display_name  TEXT NOT NULL,             -- 自动生成，如「音色 1」
    sample_path   TEXT NOT NULL,             -- 相对资产目录的路径（3.2：仅资产解析层读写）
    model_path    TEXT,                      -- 克隆产出文件，未生成成功为 NULL
    status        TEXT NOT NULL,             -- 'training'|'ready'|'failed'（录音中为 UI 态）
    quality_score REAL,                      -- 阶段 2 起的相似度，此前为 NULL
    created_at    REAL NOT NULL
);

-- 会话（轮次原文见 migrations/0003_turn.sql；摘要与事实也落库）
CREATE TABLE session (
    id            TEXT PRIMARY KEY,
    profile_id    TEXT NOT NULL DEFAULT 'default',
    persona_id    TEXT NOT NULL,
    voice_id      TEXT,
    started_at    REAL NOT NULL,
    last_active_at REAL NOT NULL,
    FOREIGN KEY (persona_id) REFERENCES persona(id),
    FOREIGN KEY (voice_id)   REFERENCES voice(id)
);

-- 记忆事实（用户偏好、事实、事件）
CREATE TABLE memory_fact (
    id            TEXT PRIMARY KEY,
    profile_id    TEXT NOT NULL DEFAULT 'default',
    fact          TEXT NOT NULL,             -- "用户下周有面试"
    category      TEXT NOT NULL,             -- 'preference'|'event'|'identity'|'other'
    source_session_id TEXT,                  -- 来自哪个会话（可追溯）
    source_turn   INTEGER,                   -- 来自该会话第几轮
    created_at    REAL NOT NULL,
    last_seen_at  REAL NOT NULL,
    superseded_by TEXT,                      -- 被新事实取代时指向新 id
    deleted       INTEGER NOT NULL DEFAULT 0 -- 删除语义见 16.2（真删时向量同步移除）
);

-- 对话滚动摘要
CREATE TABLE session_summary (
    session_id    TEXT PRIMARY KEY,
    summary       TEXT NOT NULL,
    up_to_turn    INTEGER NOT NULL,
    updated_at    REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES session(id)
);

-- 向量索引（sqlite-vec）
-- 维度参数化：默认 bge-small-zh（512 维）；质量档 bge-m3（1024 维）。
-- vec0 表不可 ALTER——切档 = migrations 重建本表。
CREATE VIRTUAL TABLE memory_vec USING vec0(
    fact_id TEXT PRIMARY KEY,
    embedding FLOAT[<dim>]
);

-- 设置（键值，含 LLM provider 选择、嵌入档位、隐私模式等）
CREATE TABLE setting (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL                      -- JSON 编码
);
