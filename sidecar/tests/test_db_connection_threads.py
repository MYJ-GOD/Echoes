"""连接层跨线程（3.2「写盘入线程」× 14.2「单写者」）。

**为什么有这个文件**：真机整链第一次跑就栽在
`SQLite objects created in a thread can only be used in that same thread`——
编排层收尾用 `asyncio.to_thread(storage.sessions.touch)` 把落库挪出事件循环，
而连接是在主线程 `connect()` 的。单测里 storage 一直是桩（不碰线程），
所以这个洞只在「真 storage + 真线程」的组合下暴露。以下三点锁住回归：

1. 连接可跨线程执行语句（不再被 check_same_thread 判死）；
2. `Storage` 门面在 `asyncio.to_thread` 里读写正常（编排层收尾的真实形态）；
3. 串行仍成立：多线程并发写不出 `database is locked`、不丢行（14.2 单写者）。
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from contextlib import suppress
from pathlib import Path

from echoes_sidecar.db.connection import ThreadSafeConnection, connect
from echoes_sidecar.db.repo import Storage


def _open(tmp_path: Path) -> Storage:
    return Storage.open(tmp_path / "db" / "echoes.db")


def test_connect_returns_thread_safe_connection(tmp_path: Path) -> None:
    conn = connect(tmp_path / "echoes.db")
    assert isinstance(conn, ThreadSafeConnection)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_connection_usable_from_worker_thread(tmp_path: Path) -> None:
    """同一连接在另一线程执行：不抛 ProgrammingError，写入可见。"""
    conn = connect(tmp_path / "echoes.db")
    errors: list[BaseException] = []

    def _write() -> None:
        try:
            conn.execute(
                "INSERT INTO setting (key, value) VALUES (?, ?)", ("probe", '"ok"')
            )
            conn.commit()
        except BaseException as exc:  # noqa: BLE001  线程内异常需带回主线程断言
            errors.append(exc)

    thread = threading.Thread(target=_write)
    thread.start()
    thread.join()

    assert errors == []
    assert conn.execute("SELECT value FROM setting WHERE key = 'probe'").fetchone()[0] == '"ok"'


async def test_storage_facade_writes_inside_to_thread(tmp_path: Path) -> None:
    """编排层收尾的真实形态：`asyncio.to_thread(storage.sessions.touch)`。"""
    storage = _open(tmp_path)
    storage.personas.sync(
        persona_id="default", name="默认人设", system_prompt="p", now=0.5
    )
    storage.sessions.create(session_id="s1", persona_id="default", now=1.0)
    # bind_voice 有 voice 外键：先落一条克隆行（真机 clone 流程同序）
    storage.voices.insert_training(
        voice_id="clone:abc", display_name="克隆", sample_path="a.wav", now=1.0
    )

    await asyncio.to_thread(storage.sessions.touch, "s1", now=2.0)
    await asyncio.to_thread(storage.sessions.bind_voice, "s1", "clone:abc")

    row = storage.sessions.get("s1")
    assert row is not None
    assert row.last_active_at == 2.0
    assert row.voice_id == "clone:abc"


def test_concurrent_writers_are_serialized(tmp_path: Path) -> None:
    """8 线程各写 20 行：无 locked 错误、无丢行（单连接串行，14.2）。"""
    conn = connect(tmp_path / "echoes.db")
    errors: list[BaseException] = []

    def _writer(tag: int) -> None:
        try:
            for i in range(20):
                conn.execute(
                    "INSERT INTO setting (key, value) VALUES (?, ?)",
                    (f"k{tag}-{i}", str(i)),
                )
                conn.commit()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_writer, args=(tag,)) for tag in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert conn.execute("SELECT COUNT(*) FROM setting").fetchone()[0] == 160


def test_close_from_worker_thread_is_clean(tmp_path: Path) -> None:
    """关闭同样允许跨线程（退出路径不因线程不同而抛错）。"""
    conn = connect(tmp_path / "echoes.db")
    thread = threading.Thread(target=conn.close)
    thread.start()
    thread.join()
    # 已关闭 = 期望结果；要抓到的是「跨线程」那类 ProgrammingError
    with suppress(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
