"""组合根主线程预热（3.2 执行约束细则；Windows loader-lock 死锁规避，R20）。

口径：
- 分派只对真路引擎（CosyVoice2/whisper）生效，mock 零成本；
- 预热失败不中断服务（stderr 记录；warmup 的报错不降级链保底，3.4.1）；
- serve 顺序：首发 hello/booting/ready 写出之后、gate 任务创建之前——
  worker 线程不得触发首次重型 C import（R20 实证死锁面）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import echoes_sidecar.main as main_module
from echoes_sidecar.engines.asr.mock import MockASREngine
from echoes_sidecar.engines.asr.whisper import WhisperASREngine
from echoes_sidecar.engines.tts.cosyvoice2 import CosyVoice2TtsEngine
from echoes_sidecar.engines.tts.mock import MockTTSEngine
from echoes_sidecar.main import _preload_runtime, serve


def test_preload_runtime_calls_tts_preload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(CosyVoice2TtsEngine, "preload", lambda self: calls.append("tts"))
    tts = CosyVoice2TtsEngine(model_dir=tmp_path / "weights")
    _preload_runtime(tts, MockASREngine())
    assert calls == ["tts"]


def test_preload_runtime_calls_asr_preload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(WhisperASREngine, "preload", lambda self: calls.append("asr"))
    _preload_runtime(MockTTSEngine(), WhisperASREngine())
    assert calls == ["asr"]


def test_preload_runtime_mock_zero_cost() -> None:
    """mock 引擎无 preload 面：直接返回不炸（阶段 0 mock 链零成本）。"""
    _preload_runtime(MockTTSEngine(), MockASREngine())


def test_preload_runtime_failure_is_non_fatal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """预热失败不中断服务（stderr 记录；warmup 路径将复现并走既有报错链）。"""

    def _boom(self: CosyVoice2TtsEngine) -> None:
        raise RuntimeError("loader boom")

    monkeypatch.setattr(CosyVoice2TtsEngine, "preload", _boom)
    tts = CosyVoice2TtsEngine(model_dir=tmp_path / "weights")
    _preload_runtime(tts, MockASREngine())  # 不传播
    assert "预热失败" in capsys.readouterr().err


async def test_serve_preloads_after_handshake_before_main_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """serve 顺序锁：hello/booting/ready 先写出 → preload → 才进 recv 主循环。"""
    # 数据目录隔离（5.3）：serve 会真开 SQLite 并跑迁移，不许落到用户 %LOCALAPPDATA%
    monkeypatch.setenv("ECHOES_DATA_DIR", str(tmp_path / "data"))
    order: list[Any] = []
    monkeypatch.setattr(
        main_module, "_preload_runtime", lambda tts, asr: order.append("preload")
    )

    class _FakeStdioTransport:
        def __init__(self, reader: Any, writer: Any) -> None:
            order.append("transport")

        async def send(self, msg: dict[str, Any]) -> None:
            order.append(("send", msg.get("type")))

        async def recv(self) -> bytes | None:
            order.append("recv")
            return None  # 直接 EOF：主循环退出

        async def close(self) -> None:
            order.append("close")

    monkeypatch.setattr(main_module, "StdioTransport", _FakeStdioTransport)
    await serve([])  # 默认全 mock / ws=off：无网络无模型

    assert order.index("preload") < order.index("recv")
    sent_types = [
        item[1] for item in order[: order.index("preload")] if isinstance(item, tuple)
    ]
    assert sent_types[0] == "hello"
    assert "state" in sent_types  # booting/ready 握手已写出
