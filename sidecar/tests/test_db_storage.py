"""DB 运行层（5.1/14.2/14.3）：迁移幂等与版本守卫、最小 CRUD、孤儿收敛、数据目录解析。

层级：L1/L2（零模型依赖，13.1）；全部用 tmp_path 隔离，不碰用户数据目录（5.3）。
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.types import VoiceStatus
from echoes_sidecar.db import paths as db_paths
from echoes_sidecar.db.connection import (
    apply_migrations,
    connect,
    default_migrations_dir,
    load_migrations,
)
from echoes_sidecar.db.repo import Storage


def _open(tmp_path: Path) -> Storage:
    return Storage.open(tmp_path / "db" / "echoes.db")


def test_migrations_apply_once_and_are_idempotent(tmp_path: Path) -> None:
    """14.2：迁移幂等 —— 二次打开不重放，user_version 停在最新版本。"""
    db_file = tmp_path / "db" / "echoes.db"
    latest = load_migrations()[-1].version  # 别写死版本号：加迁移不该改这条测试

    conn = connect(db_file)
    version = conn.execute("PRAGMA user_version").fetchone()
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    conn.close()

    assert int(version[0]) == latest
    assert {"persona", "voice", "session", "memory_fact", "session_summary", "setting"} <= tables
    # 0002 起才有 vec0 虚表（-- requires: sqlite_vec）
    assert "memory_vec" in tables

    again = connect(db_file)
    assert int(again.execute("PRAGMA user_version").fetchone()[0]) == latest
    again.close()


def test_wal_and_foreign_keys_are_on(tmp_path: Path) -> None:
    """14.2：WAL 常开 + 外键 ON（连接参数是契约的一部分，不是可选优化）。"""
    conn = connect(tmp_path / "echoes.db")
    try:
        assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        assert int(conn.execute("PRAGMA foreign_keys").fetchone()[0]) == 1
    finally:
        conn.close()


def test_schema_version_newer_than_app_is_rejected(tmp_path: Path) -> None:
    """14.2：版本高于应用 → 报错引导，不静默迁移/降级。"""
    db_file = tmp_path / "echoes.db"
    conn = connect(db_file)
    conn.execute("PRAGMA user_version = 999")
    conn.commit()
    conn.close()

    with pytest.raises(EchoesError) as excinfo:
        connect(db_file)
    assert excinfo.value.code is ErrorCode.STORAGE_ERROR
    assert "999" in excinfo.value.message


def test_migration_requiring_missing_extension_is_reported(tmp_path: Path) -> None:
    """3.2 报错而非降级：缺扩展的迁移必须点名扩展，而不是悄悄跳过。"""
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_probe.sql").write_text(
        "-- requires: sqlite_vec_not_installed_probe\nCREATE TABLE probe (id TEXT);\n",
        encoding="utf-8",
    )

    with pytest.raises(EchoesError) as excinfo:
        connect(tmp_path / "probe.db", migrations_dir=migrations)
    assert "sqlite_vec_not_installed_probe" in excinfo.value.message


def test_migration_files_must_be_continuous(tmp_path: Path) -> None:
    """迁移缺号即报错（离线包/合并冲突导致漏文件的典型故障）。"""
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_a.sql").write_text("CREATE TABLE a (id TEXT);\n", encoding="utf-8")
    (migrations / "0003_c.sql").write_text("CREATE TABLE c (id TEXT);\n", encoding="utf-8")

    with pytest.raises(EchoesError) as excinfo:
        load_migrations(migrations)
    assert "不连续" in excinfo.value.message


def test_failed_migration_rolls_back_entire_script(tmp_path: Path) -> None:
    """迁移半途失败不能留下半张表；user_version 也不能前进。"""
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_bad.sql").write_text(
        "CREATE TABLE partial (id TEXT);\n"
        "INSERT INTO no_such_table (id) VALUES ('boom');\n",
        encoding="utf-8",
    )
    db_file = tmp_path / "bad.db"

    with pytest.raises(EchoesError):
        connect(db_file, migrations_dir=migrations)

    conn = sqlite3.connect(db_file)
    try:
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "partial" not in tables
        assert int(conn.execute("PRAGMA user_version").fetchone()[0]) == 0
    finally:
        conn.close()


def test_pending_migration_creates_backup(tmp_path: Path) -> None:
    """升级前必须有 VACUUM INTO 备份；新装库（无待执行迁移）不备份。"""
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_base.sql").write_text(
        "CREATE TABLE base (id TEXT);\n", encoding="utf-8"
    )
    db_file = tmp_path / "db" / "echoes.db"
    conn = connect(db_file, migrations_dir=migrations)
    conn.close()

    (migrations / "0002_extra.sql").write_text(
        "CREATE TABLE extra (id TEXT);\n", encoding="utf-8"
    )
    conn = connect(db_file, migrations_dir=migrations)
    conn.close()

    backups = list((tmp_path / "backup").glob("v*.db"))
    assert len(backups) == 1
    backup = sqlite3.connect(backups[0])
    try:
        assert int(backup.execute("PRAGMA user_version").fetchone()[0]) == 1
    finally:
        backup.close()


def test_existing_data_survives_0003_0004(tmp_path: Path) -> None:
    """旧库（0001/0002）升级：voice/session/summary/fact 数据不能丢。"""
    old_migrations = tmp_path / "old-migrations"
    old_migrations.mkdir()
    source = default_migrations_dir()
    for name in ("0001_init.sql", "0002_memory_vec.sql"):
        shutil.copy(source / name, old_migrations / name)

    db_file = tmp_path / "db" / "echoes.db"
    conn = connect(db_file, migrations_dir=old_migrations)
    conn.execute(
        "INSERT INTO persona (id, name, system_prompt, created_at, updated_at)"
        " VALUES ('default', '旧人设', '旧 prompt', 1, 1)"
    )
    conn.execute(
        "INSERT INTO voice"
        " (id, display_name, sample_path, model_path, status, quality_score, created_at)"
        " VALUES ('v1', '旧音色', 'voices/v1.wav', 'voices/v1.pt', 'ready', 0.9, 2)"
    )
    conn.execute(
        "INSERT INTO session"
        " (id, profile_id, persona_id, voice_id, started_at, last_active_at)"
        " VALUES ('s1', 'default', 'default', 'v1', 3, 4)"
    )
    conn.execute(
        "INSERT INTO session_summary (session_id, summary, up_to_turn, updated_at)"
        " VALUES ('s1', '旧摘要', 37, 5)"
    )
    conn.execute(
        "INSERT INTO memory_fact"
        " (id, profile_id, fact, category, source_session_id, source_turn,"
        "  created_at, last_seen_at, superseded_by, deleted)"
        " VALUES ('f1', 'default', '用户喜欢猫', 'preference', 's1', 37, 6, 6, NULL, 0)"
    )
    conn.commit()
    conn.close()

    upgraded = connect(db_file)
    try:
        voice = upgraded.execute(
            "SELECT sample_path, engine FROM voice WHERE id = 'v1'"
        ).fetchone()
        assert tuple(voice) == ("voices/v1.wav", "cosyvoice2")

        summary = upgraded.execute(
            "SELECT summary, up_to_turn FROM session_summary WHERE session_id = 's1'"
        ).fetchone()
        assert tuple(summary) == ("旧摘要", 0)

        fact = upgraded.execute(
            "SELECT source_turn, source_turn_id FROM memory_fact WHERE id = 'f1'"
        ).fetchone()
        assert tuple(fact) == (37, None)
    finally:
        upgraded.close()


def test_apply_migrations_returns_current_version(tmp_path: Path) -> None:
    conn = connect(tmp_path / "echoes.db")
    try:
        assert apply_migrations(conn) == load_migrations()[-1].version
    finally:
        conn.close()


def test_persona_sync_creates_then_refreshes_prompt(tmp_path: Path) -> None:
    """prompt 单一来源在代码侧：DB 里的旧 prompt 随 sync 更新，created_at 不变。"""
    storage = _open(tmp_path)
    try:
        created = storage.personas.sync(
            persona_id="default", name="默认人设", system_prompt="v1", now=100.0
        )
        assert created.created_at == 100.0
        assert storage.personas.get("default") == created

        updated = storage.personas.sync(
            persona_id="default", name="默认人设", system_prompt="v2", now=200.0
        )
        assert updated.system_prompt == "v2"
        assert updated.created_at == 100.0
        assert updated.updated_at == 200.0
        assert storage.personas.get("default") == updated

        unchanged = storage.personas.sync(
            persona_id="default", name="默认人设", system_prompt="v2", now=300.0
        )
        assert unchanged.updated_at == 200.0  # 无变化不写库
    finally:
        storage.close()


def test_voice_lifecycle_and_orphan_cleanup(tmp_path: Path) -> None:
    """2.5 三态 + 14.1 孤儿收敛：training 残留启动即置 failed。"""
    storage = _open(tmp_path)
    try:
        row = storage.voices.insert_training(
            voice_id="v1", display_name="音色 1", sample_path="voices/v1.wav", now=10.0
        )
        assert row.status is VoiceStatus.TRAINING
        assert storage.voices.fail_orphans() == 1
        orphaned = storage.voices.get("v1")
        assert orphaned is not None and orphaned.status is VoiceStatus.FAILED

        storage.voices.mark_ready("v1", model_path="voices/v1.pt")
        ready = storage.voices.get("v1")
        assert ready is not None
        assert ready.status is VoiceStatus.READY
        assert ready.model_path == "voices/v1.pt"

        storage.voices.mark_failed("v1")  # 失败不抹已有资产（2.5）
        failed = storage.voices.get("v1")
        assert failed is not None
        assert failed.status is VoiceStatus.FAILED
        assert failed.model_path == "voices/v1.pt"

        assert [voice.id for voice in storage.voices.list_all()] == ["v1"]
    finally:
        storage.close()


def test_voice_unknown_id_raises_voice_error(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        with pytest.raises(EchoesError) as excinfo:
            storage.voices.mark_ready("ghost", model_path="x.pt")
        assert excinfo.value.code is ErrorCode.VOICE_NOT_AVAILABLE
    finally:
        storage.close()


def test_session_latest_follows_touch_and_binds_voice(tmp_path: Path) -> None:
    """14.1 v1.4：重启按「最近活跃」重建；音色绑定落在 session.voice_id。"""
    storage = _open(tmp_path)
    try:
        storage.personas.sync(
            persona_id="default", name="默认人设", system_prompt="s", now=1.0
        )
        first = storage.sessions.create(session_id="s1", persona_id="default", now=10.0)
        second = storage.sessions.create(session_id="s2", persona_id="default", now=20.0)
        assert first.voice_id is None
        assert storage.sessions.latest() == second

        storage.sessions.touch("s1", now=30.0)
        latest = storage.sessions.latest()
        assert latest is not None and latest.id == "s1"
        assert latest.last_active_at == 30.0

        # FK 生效：voice_id 必须指向已存在的音色行（5.1 外键），故先建 voice
        storage.voices.insert_training(
            voice_id="v1", display_name="音色 1", sample_path="voices/v1.wav", now=40.0
        )
        storage.sessions.bind_voice("s1", "v1")
        bound = storage.sessions.get("s1")
        assert bound is not None and bound.voice_id == "v1"

        with pytest.raises(EchoesError):
            storage.sessions.bind_voice("ghost", "v1")
    finally:
        storage.close()


def test_session_foreign_key_is_enforced(tmp_path: Path) -> None:
    """外键 ON 的实际收益：孤儿 persona_id 写不进去（映射为 STORAGE_ERROR，不静默）。"""
    storage = _open(tmp_path)
    try:
        with pytest.raises(EchoesError) as excinfo:
            storage.sessions.create(session_id="s1", persona_id="ghost", now=1.0)
        assert excinfo.value.code is ErrorCode.STORAGE_ERROR
    finally:
        storage.close()


def test_setting_roundtrip_json(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        assert storage.settings.get("privacy") is None
        storage.settings.set("privacy", {"mode": "local", "outbound": False})
        assert storage.settings.get("privacy") == {"mode": "local", "outbound": False}
        storage.settings.set("privacy", "changed")
        assert storage.settings.get("privacy") == "changed"
    finally:
        storage.close()


def test_setting_rejects_broken_json(tmp_path: Path) -> None:
    """setting.value 是 JSON 契约：脏数据要报 STORAGE_ERROR，不能当空设置静默吞掉。"""
    db_file = tmp_path / "echoes.db"
    storage = Storage.open(db_file)
    storage.conn.execute("INSERT INTO setting (key, value) VALUES ('bad', '{')")
    storage.conn.commit()
    storage.close()

    reopened = Storage.open(db_file)
    try:
        with pytest.raises(EchoesError) as excinfo:
            reopened.settings.get("bad")
        assert excinfo.value.code is ErrorCode.STORAGE_ERROR
    finally:
        reopened.close()


def test_resolve_prefers_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """5.3：ECHOES_DATA_DIR 覆盖根目录（测试/便携部署），子目录固定为 db/assets/logs。"""
    monkeypatch.setenv(db_paths.ENV_DATA_DIR, str(tmp_path / "portable"))
    paths = db_paths.resolve()
    assert paths.root == tmp_path / "portable"
    assert paths.db_dir == paths.root / "db"
    assert paths.assets_dir == paths.root / "assets"
    assert paths.logs_dir == paths.root / "logs"
    assert paths.db_file == paths.db_dir / "echoes.db"


def test_ensure_writable_creates_tree(tmp_path: Path) -> None:
    paths = db_paths.resolve(tmp_path / "data")
    db_paths.ensure_writable(paths)
    assert paths.db_dir.is_dir()
    assert paths.assets_dir.is_dir()
    assert paths.logs_dir.is_dir()
    assert db_paths.path_risk_note(paths.root) is None


def test_path_risk_note_flags_space_and_non_ascii(tmp_path: Path) -> None:
    """5.3：Windows 路径风险只提示不硬失败（中文用户名是主流场景）。"""
    risky = tmp_path / "用户 目录"
    note = db_paths.path_risk_note(risky)
    assert note is not None
    assert "非 ASCII" in note
    assert "空格" in note


def test_json_payload_is_readable_after_reopen(tmp_path: Path) -> None:
    """WAL 落盘（14.1/14.2）：关连接再开，数据仍在。"""
    db_file = tmp_path / "db" / "echoes.db"
    storage = Storage.open(db_file)
    storage.settings.set("tier", {"gpu": 8})
    storage.close()

    reopened = Storage.open(db_file)
    try:
        assert reopened.settings.get("tier") == {"gpu": 8}
        assert json.dumps(reopened.settings.get("tier"), ensure_ascii=False) == '{"gpu": 8}'
    finally:
        reopened.close()
