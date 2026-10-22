"""组合根（文档 3.2「组装归组合根」/3.3）：具体引擎只在这里实例化，其余代码只接收 ABC。

骨架运行形态（stdio）：hello → state(booting) → state(ready)；
user_text → mock turn（LLM 组装 → state(generating/speaking) → turn_complete）→ state(ready)。
真实引擎接线在阶段 0（文档 §12 步骤 3/4）；本模块不在 mypy strict 边界（15.3）。

运行：`.venv\\Scripts\\python echoes_sidecar\\main.py`（stdin 交互）。
"""
from __future__ import annotations

import asyncio
import sys
import time
from typing import Any

from echoes_sidecar import __version__
from echoes_sidecar.core.state_machine import AppState, StateMachine
from echoes_sidecar.engines.llm.mock import MockLLMProvider
from echoes_sidecar.engines.tts.mock import MockTTSEngine
from echoes_sidecar.ipc import (
    EngineState,
    HelloMsg,
    StateMsg,
    Timings,
    TurnCompleteMsg,
    parse_obj,
)
from echoes_sidecar.session.manager import SessionManager
from echoes_sidecar.session.session import Persona, Session
from echoes_sidecar.transport.base import Transport
from echoes_sidecar.transport.stdio import StdioTransport

# ASR 装配点同样在此：阶段 0 第二周 WS 音频接通后加入（4.5；骨架期语音路径未接线）。


class _StdOutWriter:
    """stdout StreamWriter 鸭子适配：骨架期直接写进程 stdout（真实管道在壳侧装配，3.4）。"""

    def __init__(self) -> None:
        self._buf = sys.stdout.buffer

    def write(self, data: bytes) -> None:
        self._buf.write(data)

    async def drain(self) -> None:
        self._buf.flush()

    def close(self) -> None:
        self._buf.flush()

    async def wait_closed(self) -> None:
        return None


async def _stdio_reader() -> asyncio.StreamReader:
    """把进程 stdin 接进 asyncio（Windows Proactor 支持 pipe reader）。"""
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
    return reader


def _now_ms(t0: float) -> int:
    """3.4 观测字段 t：sidecar 单调时钟 ms（自进程启动起算）。"""
    return int((time.perf_counter() - t0) * 1000)


def _default_session() -> Session:
    """阶段 0 固定 default 人设/会话（4.6/5.1）。"""
    now = time.time()
    persona = Persona(
        id="default",
        name="默认人设",
        system_prompt="你是 Echoes，一个温柔的语音陪伴。简称回复、记得用户说过的事实。",
        created_at=now,
        updated_at=now,
    )
    return Session(session_id="default", profile_id="default", persona=persona, created_at=now)


def _state_payload(machine: StateMachine, session_id: str | None, t: int) -> dict[str, Any]:
    return StateMsg(state=machine.state.value, session_id=session_id, t=t).model_dump(
        mode="json"
    )


async def _mock_turn(
    transport: Transport,
    machine: StateMachine,
    session: Session,
    provider: MockLLMProvider,
    tts: MockTTSEngine,
    text: str,
    t0: float,
) -> None:
    """骨架 turn：ready→generating→(LLM 组装)→speaking→turn_complete→ready（3.5 全合法）。"""
    machine.transition(AppState.GENERATING)
    await transport.send(_state_payload(machine, session.session_id, _now_ms(t0)))

    messages: list[dict[str, str]] = [
        {"role": "system", "content": session.persona.system_prompt},
        {"role": "user", "content": text},
    ]
    pieces: list[str] = []
    async for piece in provider.generate(messages):
        pieces.append(piece)
    reply = "".join(pieces)

    machine.transition(AppState.SPEAKING)
    await transport.send(_state_payload(machine, session.session_id, _now_ms(t0)))

    voice_id = session.voice_id or "builtin:default"  # 2.5 未克隆绑定内置音色
    async for _chunk in tts.synthesize(reply, voice_id):
        pass  # 音频经 WS 出到壳侧播放（3.4）——阶段 0 第二周接线；骨架只走通消息面

    session.turn_seq += 1
    await transport.send(
        TurnCompleteMsg(
            session_id=session.session_id,
            turn_seq=session.turn_seq,
            status="SUCCESS",
            timings=Timings(total_ms=_now_ms(t0)),
        ).model_dump(mode="json")
    )
    machine.transition(AppState.READY)
    await transport.send(_state_payload(machine, session.session_id, _now_ms(t0)))


async def serve() -> None:
    t0 = time.perf_counter()
    session = _default_session()
    SessionManager().create(session)  # 4.6：阶段 0 单会话，按 session_id 查找写
    tts = MockTTSEngine()
    provider = MockLLMProvider()

    transport = StdioTransport(await _stdio_reader(), _StdOutWriter())
    machine = StateMachine()

    # 3.4 握手：第一行 hello；随后 state 变更才发（booting→ready，3.5）
    await transport.send(
        HelloMsg(
            sidecar_version=__version__,
            t=_now_ms(t0),
            engines=[
                EngineState(name="asr", ready=False),
                EngineState(name="tts", ready=True),
                EngineState(name="llm", ready=True),
            ],
        ).model_dump(mode="json")
    )
    await transport.send(_state_payload(machine, None, _now_ms(t0)))  # booting
    machine.transition(AppState.READY)  # 必需引擎 = {ASR, LLM}：骨架期 llm mock 就绪
    await transport.send(_state_payload(machine, None, _now_ms(t0)))

    try:
        while (raw := await transport.recv()) is not None:
            try:
                msg = parse_obj(raw)
            except Exception as exc:  # noqa: BLE001 - 3.4：未知/畸形消息必须忽略
                print(f"[sidecar] 忽略不认识的消息（3.4 兼容规则）: {exc}", file=sys.stderr)
                continue

            kind = type(msg).__name__
            if kind == "UserTextMsg":
                await _mock_turn(
                    transport, machine, session, provider, tts, msg.text, t0  # type: ignore[union-attr]
                )
            elif kind == "ControlMsg":
                action = str(msg.action)
                print(
                    f"[sidecar] control({action})：骨架期 turn 同步执行，无在途可打断；"
                    "三跳接线见阶段 0 第四周（3.4 口径）",
                    file=sys.stderr,
                )
            elif kind in {"CloneStartMsg", "CloneCancelMsg"}:
                print(
                    "[sidecar] clone_* 骨架占位：阶段 0 第三周接线（§12 步骤 5；4.5 契约）",
                    file=sys.stderr,
                )
            else:
                print(
                    f"[sidecar] 收到不该由壳上行的事件 {kind}（协议误用，已忽略）",
                    file=sys.stderr,
                )
    finally:
        await transport.close()


if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except NotImplementedError as exc:
        print(f"[sidecar] 本环境不支持 stdin 管道：{exc}", file=sys.stderr)
        sys.exit(1)
