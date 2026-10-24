-- 迁移 0002：记忆向量索引（母文档 5.1 / 阶段 1 / ADR-006）
-- requires: sqlite_vec
--
-- 为什么单独一条迁移：vec0 是**扩展虚表**，没有 sqlite-vec 就建不出来；把它和
-- 0001 放一起会让「只想启动一次」的阶段 0 也被扩展硬依赖。迁移头 `-- requires:`
-- 让 connection.apply_migrations 在缺扩展时**明确报错**（3.2 报错而非降级），
-- 而不是静默跳过一个功能。
--
-- 维度：默认档 bge-small-zh 512（ADR-006）。vec0 表**不能 ALTER**，切到质量档
-- （bge-m3 1024）时的做法是新建 0003 迁移：建新表 → 回填 → 删旧表 → 改名，
-- 不在这里做参数化（迁移文件必须可重放、可审计）。
--
-- fact_id 与 memory_fact.id 同步维护（无外键：vec0 不支持外键约束，由
-- MemoryRepo 在一个事务里成对写/删，见 db/memory_repo.py）。

CREATE VIRTUAL TABLE memory_vec USING vec0(
    fact_id   TEXT PRIMARY KEY,
    embedding FLOAT[512]
);
