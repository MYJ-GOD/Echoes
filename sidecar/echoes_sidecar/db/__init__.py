"""db/：SQLite schema、migrations 与最小 CRUD（3.3）。

- `schema.sql`：母文档 5.1 的**文档镜像**（含 `FLOAT[<dim>]` 维度占位，不可直接执行）；
- `migrations/NNNN_*.sql`：可执行 DDL（14.2 幂等 + `user_version` 校验）；
- `connection.py`：连接参数（WAL / 外键 / busy_timeout）与迁移执行；
- `paths.py`：数据目录解析与可写性自检（5.3/14.3）；
- `repo.py`：persona / voice / session / setting 最小 CRUD 与 `Storage` 门面。
"""
from echoes_sidecar.db.connection import (
    Migration,
    apply_migrations,
    connect,
    default_migrations_dir,
    load_migrations,
)
from echoes_sidecar.db.paths import DataPaths, ensure_writable, path_risk_note, resolve
from echoes_sidecar.db.repo import (
    PersonaRepo,
    SessionRepo,
    SessionRow,
    SessionSummary,
    SettingRepo,
    Storage,
    VoiceRepo,
    VoiceRow,
)

__all__ = [
    "DataPaths",
    "Migration",
    "PersonaRepo",
    "SessionRepo",
    "SessionRow",
    "SessionSummary",
    "SettingRepo",
    "Storage",
    "VoiceRepo",
    "VoiceRow",
    "apply_migrations",
    "connect",
    "default_migrations_dir",
    "ensure_writable",
    "load_migrations",
    "path_risk_note",
    "resolve",
]
