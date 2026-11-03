"""R5 数据导出 / 导入：往返完整、FTS/向量可召回、坏包整包回滚。"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from echoes_sidecar.core.errors import EchoesError
from echoes_sidecar.data_transfer import (
    FORMAT,
    export_bundle,
    import_bundle,
)
from echoes_sidecar.db import Storage

DIM = 512
VECTOR = [0.1] * DIM


def _seed(root: Path) -> Storage:
    store = Storage.open(root / "db" / "echoes.db")
    now = time.time()
    persona = store.personas.sync(
        persona_id="default", name="默认人设", system_prompt="s", now=now
    )
    store.sessions.create(session_id="s1", persona_id=persona.id, now=now)
    turn = store.turns.insert(session_id="s1", user_text="我喜欢弹吉他", now=now)
    store.turns.finish(
        turn.turn_id,
        assistant_text="记住了。",
        status="complete",
        now=now + 1,
        emotion="happy",
    )
    fact = store.memories.insert(
        fact_id="f1",
        fact="用户会弹吉他",
        category="preference",
        embedding=VECTOR,
        now=now,
        source_session_id="s1",
        source_turn=1,
    )
    store.turns.link_memory(turn.turn_id, [fact.id])
    store.sessions.save_summary("s1", summary="聊了吉他", up_to_turn=1, now=now)
    store.chunks.upsert(
        turn.turn_id,
        [("我喜欢弹吉他 记住了。", VECTOR)],
        model="bge-small-zh-v1.5",
        now=now,
    )
    return store


def test_round_trip_preserves_text_memory_and_vectors(tmp_path: Path) -> None:
    source = _seed(tmp_path / "src")
    dest = tmp_path / "bundle.json"
    stats = export_bundle(dest, storage=source)
    source.close()

    assert stats["sessions"] == 1
    assert stats["turns"] == 1
    assert stats["memories"] == 1
    assert stats["chunks"] == 1
    assert stats["bytes"] > 0

    target = Storage.open(tmp_path / "dst" / "db" / "echoes.db")
    try:
        counts = import_bundle(dest, storage=target)
        assert counts == {"sessions": 1, "turns": 1, "memories": 1, "chunks": 1}

        turn = target.turns.last_finished("s1")
        assert turn is not None
        assert turn.user_text == "我喜欢弹吉他"
        assert turn.emotion == "happy"

        # FTS：原文层重建（触发器随 INSERT 维护）
        assert [item.turn_id for item in target.turns.search("吉他")] == [turn.turn_id]
        # 向量：原文 chunk 与记忆都能被近邻召回
        chunks = target.chunks.search(VECTOR, k=3)
        assert [hit.turn_id for hit in chunks] == [turn.turn_id]
        facts = target.memories.search(VECTOR, k=3)
        assert [fact.id for fact in facts] == ["f1"]
        # 摘要与 turn↔记忆 引用同样回来了
        assert target.sessions.get_summary("s1") is not None
        assert target.turns.memory_refs(turn.turn_id) == ["f1"]
    finally:
        target.close()


def test_import_twice_is_idempotent(tmp_path: Path) -> None:
    source = _seed(tmp_path / "src")
    dest = tmp_path / "bundle.json"
    export_bundle(dest, storage=source)
    source.close()

    target = Storage.open(tmp_path / "dst" / "db" / "echoes.db")
    try:
        import_bundle(dest, storage=target)
        import_bundle(dest, storage=target)
        count = target.conn.execute("SELECT COUNT(*) FROM turn").fetchone()[0]
        assert count == 1
        assert len(target.turns.search("吉他")) == 1
    finally:
        target.close()


def test_rejects_foreign_or_corrupt_bundle(tmp_path: Path) -> None:
    target = Storage.open(tmp_path / "dst" / "db" / "echoes.db")
    try:
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"format": "something-else"}), encoding="utf-8")
        with pytest.raises(EchoesError) as err:
            import_bundle(bad, storage=target)
        assert FORMAT in err.value.message

        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(EchoesError):
            import_bundle(bad, storage=target)
    finally:
        target.close()


def test_dimension_mismatch_rolls_back_whole_bundle(tmp_path: Path) -> None:
    source = _seed(tmp_path / "src")
    dest = tmp_path / "bundle.json"
    export_bundle(dest, storage=source)
    source.close()

    payload = json.loads(dest.read_text(encoding="utf-8"))
    payload["memories"][0]["embedding"] = [0.1, 0.2, 0.3]
    dest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    target = Storage.open(tmp_path / "dst" / "db" / "echoes.db")
    try:
        with pytest.raises(EchoesError) as err:
            import_bundle(dest, storage=target)
        assert "维度" in err.value.message
        # 整包回滚：会话/轮次都不该留下半截
        assert target.sessions.get("s1") is None
        assert target.conn.execute("SELECT COUNT(*) FROM turn").fetchone()[0] == 0
    finally:
        target.close()


def test_import_rejects_unknown_turn_status(tmp_path: Path) -> None:
    source = _seed(tmp_path / "src")
    dest = tmp_path / "bundle.json"
    export_bundle(dest, storage=source)
    source.close()

    payload = json.loads(dest.read_text(encoding="utf-8"))
    payload["turns"][0]["status"] = "bogus"
    dest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    target = Storage.open(tmp_path / "dst" / "db" / "echoes.db")
    try:
        with pytest.raises(EchoesError) as err:
            import_bundle(dest, storage=target)
        assert "状态非法" in err.value.message
    finally:
        target.close()


def test_export_does_not_include_settings_or_keys(tmp_path: Path) -> None:
    source = _seed(tmp_path / "src")
    source.settings.set("llm_base_url", "https://secret.example/v1")
    dest = tmp_path / "bundle.json"
    export_bundle(dest, storage=source)
    source.close()

    text = dest.read_text(encoding="utf-8")
    assert "secret.example" not in text
    payload = json.loads(text)
    assert "settings" not in payload
    assert "apiKey" not in text
