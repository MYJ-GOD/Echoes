"""SQLite 运行层（母文档 5.1 / 14.2）：连接参数、迁移执行、版本校验。

口径：
- **WAL 常开**（14.2），外键 ON，busy_timeout 兜底；单写者由上层串行保证（14.2）。
- 迁移文件 `db/migrations/NNNN_name.sql` 按版本顺序执行，版本号记 `PRAGMA user_version`；
  **幂等**（已应用版本不再执行）。
- DB 版本高于应用支持的版本 → 报错引导（14.2「不符引导而非静默迁移」）。
- 迁移头 `-- requires: <module>` 声明扩展依赖（如 `sqlite_vec`）；扩展缺失时**明确报错**，
  不静默跳过（3.2 报错而非降级）。
- 连接**跨线程可用**（`ThreadSafeConnection`）：14.2 的「单写者」在连接上落地为一把
  可重入锁，3.2 的「写盘入线程」才能真把落库挪出事件循环。
"""
from __future__ import annotations

import importlib.util
import re
import sqlite3
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from echoes_sidecar.core.errors import EchoesError, ErrorCode

_MIGRATION_FILE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
_REQUIRES_LINE = re.compile(r"^--\s*requires:\s*([A-Za-z0-9_.]+)\s*$")

BUSY_TIMEOUT_MS = 5000
# 迁移竞争重试次数：多实例（用户双击两次）同时首次启动时，后到者会撞上
# 「table already exists」；重试后检查 user_version 即可判定「另一进程已完成」。
_MIGRATION_ATTEMPTS = 3


class ThreadSafeConnection(sqlite3.Connection):
    """单连接跨线程（3.2 写盘入线程 × 14.2 单写者）。

    **为什么需要它**：sqlite3 默认 `check_same_thread=True`，任何在 worker 线程里的
    落库（编排层 `asyncio.to_thread(storage.sessions.touch)`）都会直接抛
    `SQLite objects created in a thread can only be used in that same thread`——
    这条错误只在真机整链才暴露（单测的 storage 是桩，不碰线程）。14.2 的口径本来是
    「单写者由上层串行保证」，这里把「串行」落到连接上：所有语句经一把 `RLock`
    排队，于是「谁在哪个线程调」不再影响正确性。

    只包 `execute/executemany/executescript/commit/rollback`：`cursor()` 返回的游标
    在持锁之外迭代，WAL 下读到的是某个已提交快照（本项目的读都是短查询，够用）。
    """

    _lock: threading.RLock

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()

    def execute(self, sql: str, parameters: Any = (), /) -> sqlite3.Cursor:
        with self._lock:
            return super().execute(sql, parameters)

    def executemany(self, sql: str, parameters: Iterable[Any], /) -> sqlite3.Cursor:
        with self._lock:
            return super().executemany(sql, parameters)

    def executescript(self, sql_script: str, /) -> sqlite3.Cursor:
        with self._lock:
            return super().executescript(sql_script)

    def commit(self) -> None:
        with self._lock:
            super().commit()

    def rollback(self) -> None:
        with self._lock:
            super().rollback()


@dataclass(frozen=True)
class Migration:
    """一条迁移（版本号 = 文件名前缀，1 起连续）。"""

    version: int
    name: str
    sql: str
    requires: str | None = None


def default_migrations_dir() -> Path:
    """迁移目录随包分发（db/migrations/）。"""
    return Path(__file__).resolve().parent / "migrations"


def _parse_requires(sql: str) -> str | None:
    for line in sql.splitlines():
        match = _REQUIRES_LINE.match(line.strip())
        if match is not None:
            return match.group(1)
    return None


def load_migrations(directory: Path | None = None) -> list[Migration]:
    """读取并校验迁移清单：命名合法、版本从 1 起连续（缺号即报错，不猜）。"""
    target = directory if directory is not None else default_migrations_dir()
    if not target.is_dir():
        raise EchoesError(ErrorCode.STORAGE_ERROR, f"迁移目录不存在：{target}")

    migrations: list[Migration] = []
    for path in sorted(target.glob("*.sql")):
        match = _MIGRATION_FILE.match(path.name)
        if match is None:
            raise EchoesError(
                ErrorCode.STORAGE_ERROR,
                f"迁移文件名不合规（应为 NNNN_name.sql）：{path.name}",
            )
        sql = path.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=int(match.group(1)),
                name=match.group(2),
                sql=sql,
                requires=_parse_requires(sql),
            )
        )

    for expected, migration in enumerate(migrations, start=1):
        if migration.version != expected:
            raise EchoesError(
                ErrorCode.STORAGE_ERROR,
                f"迁移版本不连续：期望 {expected:04d}，实际 {migration.version:04d}"
                f"（{migration.name}）",
            )
    return migrations


def _current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row is not None else 0


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """14.2：WAL 常开、外键 ON、busy_timeout 兜底（并发写者等待而非立刻失败）。"""
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")


def apply_migrations(conn: sqlite3.Connection, directory: Path | None = None) -> int:
    """顺序应用未执行的迁移，返回最终版本号（幂等：已应用版本跳过）。"""
    migrations = load_migrations(directory)
    latest = migrations[-1].version if migrations else 0
    current = _current_version(conn)

    if current > latest:
        raise EchoesError(
            ErrorCode.STORAGE_ERROR,
            f"数据库 schema 版本 {current} 高于应用支持的 {latest}："
            "请升级应用，或备份后重建数据目录（14.2 不符引导，不做静默降级）",
        )

    for migration in migrations:
        if migration.version <= current:
            continue
        if migration.requires is not None and not _module_available(migration.requires):
            raise EchoesError(
                ErrorCode.STORAGE_ERROR,
                f"迁移 {migration.version:04d}_{migration.name} 需要扩展 "
                f"{migration.requires}，当前环境未安装（阶段依赖未就位）",
            )
        _run_migration(conn, migration)
        current = migration.version

    return current


def _run_migration(conn: sqlite3.Connection, migration: Migration) -> None:
    """执行单条迁移；另一实例已完成同一迁移时视作成功（不覆盖、不报假错）。

    纯单实例时这段退化为「执行一次即返回」，重试分支只在首次并发启动时触发。
    """
    last_error: sqlite3.Error | None = None
    for attempt in range(_MIGRATION_ATTEMPTS):
        try:
            conn.executescript(migration.sql)
            conn.execute(f"PRAGMA user_version = {migration.version}")
            conn.commit()
            return
        except sqlite3.Error as exc:
            last_error = exc
            conn.rollback()
            if _current_version(conn) >= migration.version:
                return  # 竞争失败但结果已达成：另一进程建好了表
            time.sleep(0.05 * (attempt + 1))
    raise EchoesError(
        ErrorCode.STORAGE_ERROR,
        f"迁移 {migration.version:04d}_{migration.name} 执行失败：{last_error}",
    ) from last_error


def _module_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):  # 缺失父包 / 具名非法都视作不可用
        return False


def connect(db_file: Path, *, migrations_dir: Path | None = None) -> sqlite3.Connection:
    """打开（必要时创建）数据库并应用迁移；失败一律映射 STORAGE_ERROR（3.4.1）。"""
    try:
        db_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise EchoesError(
            ErrorCode.STORAGE_ERROR, f"无法创建数据库目录：{db_file.parent}（{exc}）"
        ) from exc

    try:
        conn = sqlite3.connect(
            db_file,
            timeout=BUSY_TIMEOUT_MS / 1000,
            isolation_level="DEFERRED",
            # 落库挪进 worker 线程（3.2）就得放弃「只许创建线程使用」：
            # 串行由 ThreadSafeConnection 的锁保证（14.2 单写者）。
            check_same_thread=False,
            factory=ThreadSafeConnection,
        )
    except sqlite3.Error as exc:
        raise EchoesError(ErrorCode.STORAGE_ERROR, f"打开数据库失败：{db_file}（{exc}）") from exc

    conn.row_factory = sqlite3.Row
    try:
        _apply_pragmas(conn)
        apply_migrations(conn, migrations_dir)
    except EchoesError:
        conn.close()
        raise
    except sqlite3.Error as exc:
        conn.close()
        raise EchoesError(
            ErrorCode.STORAGE_ERROR, f"数据库初始化失败：{db_file}（{exc}）"
        ) from exc
    return conn
