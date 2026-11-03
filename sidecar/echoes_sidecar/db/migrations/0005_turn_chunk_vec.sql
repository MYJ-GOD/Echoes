-- 迁移 0005：原文 chunk 向量索引（R3b 3.3b）
-- requires: sqlite_vec
--
-- 为什么单独一张 vec 表：`turn_chunk` 在 0003 建了业务列与 embedding BLOB，
-- 但「BLOB 全表扫 + Python 逐条 cosine」在历史变长后不可接受；vec0 负责 KNN，
-- 业务列仍归 `turn_chunk`。两表按 chunk_id 成对维护（同 memory_vec 口径）。
--
-- 维度与 memory_vec 一致：默认档 bge-small-zh 512（ADR-006）。切档时新建迁移，
-- vec0 不能 ALTER（见 0002 头注释）。
--
-- 无外键（vec0 不支持）：turn 删除时 `turn_chunk` 级联清掉，vec 行由 sidecar
-- 启动清洗 `ChunkRepo.purge_orphans` 兜底；检索 JOIN `turn_chunk` 也不会漏出来。

CREATE VIRTUAL TABLE turn_chunk_vec USING vec0(
    chunk_id  TEXT PRIMARY KEY,
    embedding FLOAT[512]
);
