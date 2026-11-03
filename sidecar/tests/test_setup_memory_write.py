"""R3b 记忆写接口（add/update/merge）：一次性进程 + 重新嵌入。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from echoes_sidecar.core.errors import EchoesError
from echoes_sidecar.db import Storage
from echoes_sidecar.setup import import_memories, write_memory


class FakeEmbedder:
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 511 for _ in texts]


def _root(tmp_path: Path) -> Path:
    return tmp_path / "data"


def _active(root: Path):
    storage = Storage.open(root / "db" / "echoes.db")
    try:
        return storage.memories.list_active()
    finally:
        storage.close()


def test_add_update_merge_round_trip(tmp_path: Path) -> None:
    root = _root(tmp_path)
    embedder = FakeEmbedder()

    added = write_memory(
        "add",
        fact="用户喜欢猫",
        category="preference",
        data_root=root,
        embedder=embedder,
    )
    [fact] = _active(root)
    assert fact.id == added["factId"]
    assert fact.fact == "用户喜欢猫"

    updated = write_memory(
        "update",
        fact="用户喜欢猫和狗",
        fact_id=fact.id,
        category="preference",
        data_root=root,
        embedder=embedder,
    )
    [current] = _active(root)
    assert current.id == updated["factId"]
    assert current.fact == "用户喜欢猫和狗"

    second = write_memory(
        "add",
        fact="用户住在杭州",
        category="identity",
        data_root=root,
        embedder=embedder,
    )
    merged = write_memory(
        "merge",
        fact="用户喜欢猫和狗，住在杭州",
        ids=[current.id, second["factId"]],
        category="preference",
        data_root=root,
        embedder=embedder,
    )
    [only] = _active(root)
    assert only.id == merged["factId"]
    assert only.fact.startswith("用户喜欢猫和狗")
    assert only.category == "preference"


def test_validation_errors_do_not_touch_db(tmp_path: Path) -> None:
    root = _root(tmp_path)
    embedder = FakeEmbedder()

    with pytest.raises(EchoesError):
        write_memory("add", fact="   ", data_root=root, embedder=embedder)
    with pytest.raises(EchoesError):
        write_memory("add", fact="x" * 501, data_root=root, embedder=embedder)
    with pytest.raises(EchoesError):
        write_memory("add", fact="喜欢猫", category="mood", data_root=root, embedder=embedder)
    with pytest.raises(EchoesError):
        write_memory("update", fact="新", data_root=root, embedder=embedder)
    with pytest.raises(EchoesError):
        write_memory("merge", fact="合并", ids=["only-one"], data_root=root, embedder=embedder)
    with pytest.raises(EchoesError):
        write_memory("delete", fact="x", data_root=root, embedder=embedder)

    # 所有失败都在开库/写库前拦下（或整笔回滚），库里没有残留
    assert _active(root) == []


def test_update_missing_fact_fails(tmp_path: Path) -> None:
    root = _root(tmp_path)
    with pytest.raises(EchoesError):
        write_memory(
            "update",
            fact="新内容",
            fact_id="ghost",
            category="other",
            data_root=root,
            embedder=FakeEmbedder(),
        )
    assert _active(root) == []


def test_bulk_import_parses_category_and_skips_duplicates(tmp_path: Path) -> None:
    root = _root(tmp_path)
    embedder = FakeEmbedder()
    text = "\n".join(
        [
            "用户喜欢在雨天听爵士|preference",
            "- 用户会弹吉他",
            "",
            "用户住在杭州 | identity",
            "用户喜欢在雨天听爵士|preference",  # 批内重复
        ]
    )
    result = import_memories(text, data_root=root, embedder=embedder)
    assert result["added"] == 3
    assert result["skipped"] == 1

    facts = {item.fact: item.category for item in _active(root)}
    assert facts["用户喜欢在雨天听爵士"] == "preference"
    assert facts["用户会弹吉他"] == "other"
    assert facts["用户住在杭州"] == "identity"

    again = import_memories(
        "用户会弹吉他\n用户最近在学混音|event",
        data_root=root,
        embedder=embedder,
    )
    assert again["added"] == 1
    assert again["skipped"] == 1
    assert {item.fact for item in _active(root)} >= {"用户最近在学混音"}


def test_bulk_import_rejects_empty_and_oversized(tmp_path: Path) -> None:
    root = _root(tmp_path)
    with pytest.raises(EchoesError):
        import_memories("\n  \n", data_root=root, embedder=FakeEmbedder())
    with pytest.raises(EchoesError):
        import_memories("x" * 501, data_root=root, embedder=FakeEmbedder())
    with pytest.raises(EchoesError):
        import_memories("x", default_category="mood", data_root=root, embedder=FakeEmbedder())
    many = "\n".join(f"事实 {index}" for index in range(201))
    with pytest.raises(EchoesError):
        import_memories(many, data_root=root, embedder=FakeEmbedder())
    assert _active(root) == []
