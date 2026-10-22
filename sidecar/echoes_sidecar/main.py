"""组合根（文档 3.2「组装归组合根」/3.3）：具体引擎只在这里实例化，其余代码只接收 ABC。

骨架运行形态（stdio）：hello（分级就绪）→ state(booting) → 必需引擎 gate（3.5，
required_engines_ready；不过则停 booting）→ state(ready)；user_text → mock turn
（generating→assistant_text 逐片→speaking→turn_complete→ready；v1.4.1）。

运行（cwd=sidecar）：`..\\.venv\\Scripts\\python -m echoes_sidecar.main`
（🔴-1 修复：脚本直跑无包路径；stdin 用线程阻塞读，EOF→recv None 正常退出）。
真实引擎接线在阶段 0（文档 §12 步骤 3/4）；本模块在 mypy strict 边界内（15.3 修复轮扩展）。
"""
from __future__ import annotations

import asyncio
import sys
import time
from typing import Any

from echoes_sidecar import __version__
from echoes_sidecar.core.state_machine import AppState, StateMachine, required_engines_ready
from echoes_sidecar.engines.asr.mock import MockASREngine
from echoes_sidecar.engines.llm.mock import MockLLMProvider
from echoes_sidecar.engines.tts.mock import MockTTSEngine
from echoes_sidecar.ipc import (
    AssistantTextMsg,
    CloneCancelMsg,
    CloneStartMsg,
    ControlMsg,
    EngineState,
    HelloMsg,
    StateMsg,
    Timings,
    TurnCompleteMsg,
    UserTextMsg,
    parse_obj,
)
from echoes_sidecar.session.manager import SessionManager
from echoes_sidecar.session.session import Persona, Session
from echoes_sidecar.transport.base import Transport
from echoes_sidecar.transport.stdio import StdioTransport


class _ThreadedReader:
    """stdin 的 asyncio 适配（🔴-1 修复）：阻塞读放进后台线程。

    避开 Windows Proactor 对管道句柄的读完即挂问题：`to_thread` 每行一读；
    EOF（打印/管道收尾）读出 b\"\"，由 StdioTransport 映射为 recv() → None（4.1）。
    """

    async def readline(self) -> bytes:
        return await asyncio.to_thread(sys.stdin.buffer.readline)


class _StdOutWriter:
    """stdout 的 StreamWriter 鸭子适配：骨架期直写进程 stdout（真实管道由壳装配，3.4）。"""

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


def _now_ms(t0: float) -> int:
    """3.4 观测字段 t：sidecar 单调时钟 ms（自进程启动起算）。"""
    return int((time.perf_counter() - t0) * 1000)


def _default_session() -> Session:
    """阶段 0 固定 default 人设/会话（4.6/5.1）。"""
    now = time.time()
    persona = Persona(
        id="default",
        name="默认人设",
        system_prompt="你是 Echoes，一个温柔的语音陪伴。简短回复、记得用户说过的事实。",
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
    """骨架 turn：→generating→(LLM 组装)→speaking→turn_complete→ready（3.5 全合法）。

    作战注释：真实打断/在途取消在三跳协议（3.4 阶段 0 第四周）；骨架期 turn 同步执行。
    """
    machine.transition(AppState.GENERATING)
    await transport.send(_state_payload(machine, session.session_id, _now_ms(t0)))

    messages: list[dict[str, str]] = [
        {"role": "system", "content": session.persona.system_prompt},
        {"role": "user", "content": text},
    ]
    pieces: list[str] = []
    async for piece in provider.generate(messages):
        pieces.append(piece)
        # v1.4.1：回复文本逐片回传（text=截至当前全量；收尾由 turn_complete 界定）
        await transport.send(
            AssistantTextMsg(
                session_id=session.session_id,
                text="".join(pieces),
                t=_now_ms(t0),
            ).model_dump(mode="json")
        )
    reply = "".join(pieces)

    machine.transition(AppState.SPEAKING)
    await transport.send(_state_payload(machine, session.session_id, _now_ms(t0)))

    voice_id = session.voice_id or "builtin:default"  # 2.5 未克隆绑定内置音色
    async for _chunk in tts.synthesize(reply, voice_id):
        pass  # 音频经 WS 出壳侧播放（3.4）——阶段 0 第二周接线；骨架只走通消息面

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

    # 组合根装配清单（3.2）：阶段 0 换真实引擎。asr 在骨架期不走语音路径（WS 未接），
    # 但必须装配且 hello 声明就绪（🔴-2 修复：3.5 必需引擎集合 = {asr, llm}）。
    engines_runtime: dict[str, Any] = {
        "asr": MockASREngine(),
        "tts": MockTTSEngine(),
        "llm": MockLLMProvider(),
    }
    engine_states: list[EngineState] = [
        EngineState(name=name, ready=True) for name in engines_runtime
    ]

    transport = StdioTransport(_ThreadedReader(), _StdOutWriter())
    machine = StateMachine()

    # 3.4 握手：第一行 hello；就绪_changes 时重发 hello（分级就绪载体，3.4 v1.4）
    await transport.send(
        HelloMsg(sidecar_version=__version__, t=_now_ms(t0), engines=engine_states)
        .model_dump(mode="json")
    )
    await transport.send(_state_payload(machine, None, _now_ms(t0)))  # booting
    if required_engines_ready((s.name, s.ready) for s in engine_states):
        machine.transition(AppState.READY)
    else:
        print("[sidecar] 必需引擎(asr/llm)未就绪：停在 booting（3.5）", file=sys.stderr)
    await transport.send(_state_payload(machine, None, _now_ms(t0)))

    try:
        while (raw := await transport.recv()) is not None:
            try:
                msg = parse_obj(raw)
            except Exception as exc:  # noqa: BLE001  3.4：未知/畸形消息必须忽略
                print(f"[sidecar] 忽略不认识的消息（3.4 兼容规则）: {exc}", file=sys.stderr)
                continue

            if isinstance(msg, UserTextMsg):
                await _mock_turn(
                    transport,
                    machine,
                    session,
                    engines_runtime["llm"],
                    engines_runtime["tts"],
                    msg.text,
                    t0,
                )
            elif isinstance(msg, ControlMsg):
                print(
                    f"[sidecar] control({msg.action})：骨架期 turn 同步执行、无在途；"
                    "三跳在阶段 0 第四周接线（3.4 口径）",
                    file=sys.stderr,
                )
            elif isinstance(msg, CloneStartMsg | CloneCancelMsg):
                print(
                    "[sidecar] clone_* 骨架占位：阶段 0 第三周接线（§12 步骤 5；4.5 契约）",
                    file=sys.stderr,
                )
            else:
                print(
                    f"[sidecar] 收到不该由壳上行的事件 {type(msg).__name__}（协议误用，已忽略）",
                    file=sys.stderr,
                )
    finally:
        await transport.close()


if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        print("[sidecar] 收到中断，退出", file=sys.stderr)
