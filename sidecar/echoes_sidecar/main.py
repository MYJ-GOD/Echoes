"""组合根（文档 3.2「组装归组合根」/3.3）：具体引擎只在这里实例化，其余代码只接收 ABC。

运行形态（stdio）：hello（分级就绪）→ state(booting) → 必需引擎 gate（3.5）→
state(ready)；user_text → turn（generating→assistant_text 逐片→speaking→TTS
chunk 逐帧 WS send_audio→turn_complete→ready；ws=off 时 chunk 丢弃只走消息面）。

运行（cwd=sidecar）：`..\\.venv\\Scripts\\python -m echoes_sidecar.main`
（🔴-1 修复：脚本直跑无包路径；stdin 用线程阻塞读，EOF→recv None 正常退出）。
真实引擎接线在阶段 0（文档 §12 步骤 3/4）；本模块在 mypy strict 边界内（15.3 修复轮扩展）。
"""
from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
import time
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path
from typing import Any, Protocol

from echoes_sidecar import __version__, runtime
from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.cancel import CancelToken
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.state_machine import AppState, StateMachine, required_engines_ready
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.db import DataPaths, Storage, ensure_writable, path_risk_note, resolve
from echoes_sidecar.engines.asr.base import ASREngine
from echoes_sidecar.engines.asr.mock import MockASREngine
from echoes_sidecar.engines.asr.whisper import WhisperASREngine
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.engines.llm.mock import MockLLMProvider
from echoes_sidecar.engines.llm.ollama import OllamaLLMProvider
from echoes_sidecar.engines.llm.openai_compat import OpenAICompatibleLLM
from echoes_sidecar.engines.llm.persona import PERSONA_SYSTEM_PROMPT
from echoes_sidecar.engines.llm.router import ProviderRouter
from echoes_sidecar.engines.tts.base import TTSEngine
from echoes_sidecar.engines.tts.cosyvoice2 import CosyVoice2TtsEngine
from echoes_sidecar.engines.tts.mock import MockTTSEngine
from echoes_sidecar.ipc import (
    AsrFinalMsg,
    CloneCancelMsg,
    CloneStartMsg,
    ControlMsg,
    EngineState,
    ErrorMsg,
    HelloMsg,
    StateMsg,
    UserTextMsg,
    parse_obj,
)
from echoes_sidecar.memory.embedding import DEFAULT_MODEL_DIR, TransformersEmbedder
from echoes_sidecar.memory.extractor import MemoryExtractor
from echoes_sidecar.memory.store import MemoryStore
from echoes_sidecar.orchestration.clone import CloneService
from echoes_sidecar.orchestration.graph import TriggerSource, TurnDeps, TurnGraph
from echoes_sidecar.orchestration.turn import TurnFactory, TurnRunner
from echoes_sidecar.secrets import llm_api_key
from echoes_sidecar.session.manager import SessionManager
from echoes_sidecar.session.runtime import load_runtime_settings
from echoes_sidecar.session.session import Session
from echoes_sidecar.session.summary import SessionSummarizer
from echoes_sidecar.transport.base import Transport
from echoes_sidecar.transport.lan_ws import LanWebSocketTransport
from echoes_sidecar.transport.local_ws import LocalWebSocketTransport
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


DEFAULT_PERSONA_ID = "default"
DEFAULT_PERSONA_NAME = "默认人设"
DEFAULT_SESSION_ID = "default"
# OpenAI 兼容端点的兜底地址（设置页未填 base_url 时）
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
# 克隆样本等待上限（3.4）：壳侧录音上限 6s，留足余量；超时即报错而非挂死
SAMPLE_WAIT_SECONDS = 15.0


def _open_storage() -> tuple[DataPaths, Storage]:
    """数据目录 + 迁移 + 启动自检（5.3 / 14.1 / 14.2）。

    目录解析只发生在组合根（3.2）；不可写即 STORAGE_ERROR 报错引导，
    不退到内存库——静默降级会把「数据没存住」藏到用户发现为止（3.4.1）。
    返回 paths 是因为音色资产要相对 assets 目录解析（5.1/3.2）。
    """
    paths = resolve()
    ensure_writable(paths)
    note = path_risk_note(paths.root)
    if note is not None:
        print(
            f"[sidecar] 数据目录{note}（5.3 历史多发故障区，仅提示）：{paths.root}",
            file=sys.stderr,
        )
    storage = Storage.open(paths.db_file)
    orphans = storage.voices.fail_orphans()
    if orphans:
        print(
            f"[sidecar] 启动自检：{orphans} 条 training 孤儿音色置 failed（14.1）",
            file=sys.stderr,
        )
    return paths, storage


def _open_session(storage: Storage, *, now: float) -> Session:
    """会话装配（4.6 + 14.1 v1.4）：沿用 DB 最近 session，无记录则建默认会话。

    persona 的 prompt 单一来源仍是 engines.llm.persona（v2）；DB 侧随代码同步，
    避免旧库里的陈旧 prompt 反过来覆盖代码（3.2 单一来源）。
    """
    default_persona = storage.personas.sync(
        persona_id=DEFAULT_PERSONA_ID,
        name=DEFAULT_PERSONA_NAME,
        system_prompt=PERSONA_SYSTEM_PROMPT,
        now=now,
    )
    row = storage.sessions.latest()
    if row is None:
        row = storage.sessions.create(
            session_id=DEFAULT_SESSION_ID,
            persona_id=default_persona.id,
            now=now,
        )
    persona = default_persona
    if row.persona_id != default_persona.id:
        persona = storage.personas.get(row.persona_id) or default_persona
    return Session(
        session_id=row.id,
        profile_id=row.profile_id,
        persona=persona,
        voice_id=row.voice_id,
        created_at=row.started_at,
    )


def _state_payload(machine: StateMachine, session_id: str | None, t: int) -> dict[str, Any]:
    return StateMsg(state=machine.state.value, session_id=session_id, t=t).model_dump(
        mode="json"
    )


def _turn_factory(graph: TurnGraph, session: Session, text: str) -> TurnFactory:
    """把「本轮输入文本」绑成一个 turn 工厂（3.5 单在途 / 3.4 三跳）。

    绑定必须发生在构造期：`runner.start()` 只是建任务，任务要到下一次 `await`
    才真正起跑——用闭包直接抓循环变量会把上一轮的文本串到下一轮。
    真正的 turn 流程在 `orchestration.graph`（4.3/10），组合根只做装配与适配。
    """

    async def _bound(token: CancelToken) -> None:
        await graph.run_turn(
            session, TriggerSource.USER_INPUT, {"text": text}, token=token
        )

    return _bound


class _PcmStream(AudioInputStream):
    """单段 PTT PCM16（16k mono）→ 4.2 输入流（整段转写形态）。"""

    def __init__(self, pcm: bytes) -> None:
        self._pcm = pcm

    def __aiter__(self) -> AsyncIterator[AudioChunk]:
        async def _gen() -> AsyncIterator[AudioChunk]:
            yield AudioChunk(data=self._pcm, seq=0, is_final=True)

        return _gen()


async def _transcribe_pcm(asr: ASREngine, pcm: bytes) -> str:
    """PTT 整段 PCM → 文本（4.5 transcribe 整段形态；final 段按序拼接）。"""
    texts: list[str] = []
    async for seg in asr.transcribe(_PcmStream(pcm)):
        if seg.get("is_final") and seg.get("text"):
            texts.append(str(seg["text"]))
    return "".join(texts)


async def _send_error(
    transport: Transport, session: Session, exc: EchoesError, t0: float
) -> None:
    """3.4 error 事件（引擎错误不静默；fatal 语义透传）。"""
    await transport.send(
        ErrorMsg(
            session_id=session.session_id,
            code=exc.code,
            message=exc.message,
            fatal=exc.fatal,
            t=_now_ms(t0),
        ).model_dump(mode="json")
    )


async def _asr_turn_from_pcm(
    pcm: bytes,
    transport: Transport,
    graph: TurnGraph,
    session: Session,
    asr: ASREngine,
    t0: float,
    *,
    runner: TurnRunner | None = None,
) -> bool:
    """一段 PTT 音频 → ASR → asr_final → turn（3.4：asr_final 与 user_text 等价）。

    返回是否形成 turn。booting/error 期、空转写、ASR 失败不形成 turn；ASR 失败经
    error 事件上报（ASR_ENGINE_ERROR，非致命不进 3.5 error 态——3.4.1 报错不降级）。
    `generating`/`speaking` 期收到新输入 = 先打断在途 turn 再起新 turn（3.5 动作矩阵）；
    `runner` 为空时无取消通道，只能按旧口径忽略（单测直调走这条）。
    """
    machine = graph.machine
    if not pcm:
        print("[sidecar] 收到空 PTT 段，忽略", file=sys.stderr)
        return False
    if machine.state is AppState.BOOTING or machine.state is AppState.ERROR:
        print(
            f"[sidecar] 状态 {machine.state.value} 收到 PTT 音频，忽略（3.5）",
            file=sys.stderr,
        )
        return False
    if machine.state is not AppState.READY:
        if runner is None:
            print(
                f"[sidecar] 状态 {machine.state.value} 收到 PTT 音频，无取消通道，忽略（3.5）",
                file=sys.stderr,
            )
            return False
        # 3.5：generating/speaking + 新输入 = 打断在途 turn（generating→generating 重入）
        print(
            f"[sidecar] 状态 {machine.state.value} 收到 PTT 音频，先打断在途 turn（3.5）",
            file=sys.stderr,
        )
        await runner.interrupt()
    try:
        text = await _transcribe_pcm(asr, pcm)
    except EchoesError as exc:
        print(f"[sidecar] ASR 失败: {exc}", file=sys.stderr)
        await _send_error(transport, session, exc, t0)
        return False
    except Exception as exc:  # noqa: BLE001  引擎实现异常统一落 ASR_ENGINE_ERROR
        print(f"[sidecar] ASR 异常: {exc}", file=sys.stderr)
        await _send_error(
            transport, session, EchoesError(ErrorCode.ASR_ENGINE_ERROR, str(exc)), t0
        )
        return False
    if not text:
        print("[sidecar] ASR 空转写，忽略本段", file=sys.stderr)
        return False
    await transport.send(
        AsrFinalMsg(
            session_id=session.session_id, text=text, is_final=True, t=_now_ms(t0)
        ).model_dump(mode="json")
    )
    runner = runner if runner is not None else TurnRunner()
    task = await runner.start(_turn_factory(graph, session, text))
    await runner.wait(task)
    return True


async def _asr_loop(
    ws_transport: LocalWebSocketTransport,
    transport: Transport,
    graph: TurnGraph,
    session: Session,
    asr: ASREngine,
    t0: float,
    runner: TurnRunner,
    *,
    is_cloning: Callable[[], bool] | None = None,
) -> None:
    """PTT 语音入口（3.4/§12 步骤 4）：WS 整段音频 → ASR → turn。

    收整段音频在 turn 之外等待（不阻塞文本面 user_text）；打断通道不在这里——
    PTT 按下时壳侧发 `control(interrupt)`，由 stdio 主循环处理（turn 是后台任务，
    主循环才是打断的唯一入口）。
    """
    while True:
        try:
            pcm = await ws_transport.next_utterance()
        except Exception as exc:  # noqa: BLE001  连接级异常不杀 PTT 循环
            print(f"[sidecar] WS 音频段收集失败: {exc}", file=sys.stderr)
            await asyncio.sleep(0.2)
            continue
        if pcm is None:
            continue  # 壳断开/重连：半段丢弃（不构成有效输入）
        if is_cloning is not None and is_cloning():
            # 克隆期间不开新 turn（同上：TTS 引擎被占用，且样本音不该进 ASR 轮次）
            print("[sidecar] 克隆进行中，忽略本段 PTT 音频", file=sys.stderr)
            continue
        await _asr_turn_from_pcm(
            pcm, transport, graph, session, asr, t0, runner=runner
        )


async def _assemble_llm(argv: Sequence[str] | None) -> tuple[LLMProvider, bool]:
    """组合根 LLM 装配（3.2）：mock 默认（无模型依赖的契约链）、ollama 本地、openai 兼容。

    openai 一档同时覆盖云端（OpenAI/DeepSeek/…）与本地兼容端点（Ollama `/v1`、
    LM Studio、vLLM）——差异只在 base_url 与 API key（ADR-016）。
    Ollama 不可达 / 缺 key 时 ready=False → hello 声明不就绪 → 3.5 gate 停 booting
    （报错而非降级：不静默换 mock）。
    """
    parser = argparse.ArgumentParser(prog="echoes_sidecar.main")
    parser.add_argument("--llm", choices=["mock", "ollama", "openai"], default="mock")
    # ADR-001 二轮判定：T-8G 本地默认首候选 qwen3:8b(no-think, 0.80)
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument(
        "--base-url",
        default=None,
        help="OpenAI 兼容端点（填到 /v1 为止；设置页可覆盖）",
    )
    parser.add_argument(
        "--ollama-url", default="http://127.0.0.1:11434", help="本地 Ollama 地址"
    )
    parser.add_argument(
        "--no-think", action="store_true", help="qwen3 系关 thinking（ADR-001 硬前提）"
    )
    # 组合根可独立组装：各装配器只认领自己的 flag（parse_known_args // 阶段 0 简易拼装）
    args, _ = parser.parse_known_args(list(argv) if argv is not None else None)

    think = False if args.no_think else None
    base_url: str | None = args.base_url

    def _build(provider: str, model: str, url: str | None) -> LLMProvider:
        if provider == "mock":
            return MockLLMProvider()
        if provider == "ollama":
            return OllamaLLMProvider(model=model, think=think, base_url=args.ollama_url)
        # 云端与本地兼容端点共用一套客户端；key 在请求时从凭据管理器读
        return OpenAICompatibleLLM(
            model=model,
            base_url=url or DEFAULT_OPENAI_BASE_URL,
            key_provider=llm_api_key,
        )

    initial = _build(args.llm, args.model, base_url)
    ready = await initial.health()
    if not ready:
        print(
            f"[sidecar] LLM 不可用（provider={args.llm}, model={args.model}）："
            "llm ready=False（3.5 gate）",
            file=sys.stderr,
        )

    # 3.4 拉取语义：设置表可在 turn 边界切 provider，无需重启 sidecar。
    router = ProviderRouter(
        initial,
        _build,
        provider=args.llm,
        model=args.model,
        base_url=base_url,
    )
    return router, ready


def _assemble_asr(argv: Sequence[str] | None) -> tuple[ASREngine, bool]:
    """组合根 ASR 装配（3.2）：mock 默认；whisper 真路（CPU int8，第二周-4）。

    whisper ready 语义（分级就绪，3.4 v1.4）：首发 ready=False，warmup 完成的
    后台任务置 True 并重发 hello——重模型加载不阻塞 booting 其余装配；
    权重缺失时开始下载（7.3 运行时下载边界；镜像 fallback 见 engines.asr.whisper）。
    """
    parser = argparse.ArgumentParser(prog="echoes_sidecar.main")
    parser.add_argument("--asr", choices=["mock", "whisper"], default="mock")
    parser.add_argument("--asr-model", default="small")
    args, _ = parser.parse_known_args(list(argv) if argv is not None else None)

    if args.asr == "mock":
        return MockASREngine(), True

    from echoes_sidecar.models.manager import default_root

    local_model = default_root() / "faster-whisper-small"
    model_path = str(local_model) if (local_model / "model.bin").is_file() else None
    if model_path is not None:
        print(f"[sidecar] Whisper 使用本地权重: {model_path}", file=sys.stderr)
    engine: WhisperASREngine = WhisperASREngine(
        model_size=args.asr_model,
        model_path=model_path,
        device="cpu",
        compute_type="int8",
    )
    print(
        f"[sidecar] WhisperASREngine(model={args.asr_model}, CPU int8): 后台 warmup 中",
        file=sys.stderr,
    )
    return engine, False


def _assemble_tts(
    argv: Sequence[str] | None, *, assets_dir: Path | None = None
) -> tuple[TTSEngine, bool]:
    """组合根 TTS 装配（3.2）：mock 默认（契约链）；cosyvoice2 真路（第二周尾部）。

    分级就绪同 whisper：ready=False 首发，vendored 权重 warmup 完成后才置 True
    并重发 hello（3.4 v1.4）；权重缺失时 warmup 任务报 MODEL_NOT_LOADED
    （7.3：下载归部署 bootstrap，运行时不联网补救——ADR-014）。
    `assets_dir` 是克隆 prompt 的落盘根（5.1：引擎与 session 库认同一个资产目录）。
    """
    parser = argparse.ArgumentParser(prog="echoes_sidecar.main")
    parser.add_argument("--tts", choices=["mock", "cosyvoice2"], default="mock")
    args, _ = parser.parse_known_args(list(argv) if argv is not None else None)

    if args.tts == "mock":
        return MockTTSEngine(), True

    voices_dir = (assets_dir / "voices") if assets_dir is not None else None
    # fp16 默认（tier_matrix 定档）；voices_dir 缺省时引擎退到 ~/.cache/echoes/assets
    engine: CosyVoice2TtsEngine = CosyVoice2TtsEngine(voices_dir=voices_dir)
    print("[sidecar] CosyVoice2TtsEngine(fp16): 后台 warmup 中", file=sys.stderr)
    return engine, False


async def _assemble_transports(
    argv: Sequence[str] | None,
) -> tuple[Transport, LocalWebSocketTransport | None]:
    """3.4/8.2：stdio（默认，壳）或 LAN WS（单活动端点，token 配对）。"""
    parser = argparse.ArgumentParser(prog="echoes_sidecar.main")
    parser.add_argument("--transport", choices=["stdio", "lan"], default="stdio")
    parser.add_argument("--lan-token", default=None)
    args, _ = parser.parse_known_args(list(argv) if argv is not None else None)

    if args.transport == "stdio":
        return StdioTransport(_ThreadedReader(), _StdOutWriter()), await _assemble_ws(argv)

    token = (args.lan_token or os.environ.get("ECHOES_LAN_TOKEN", "") or "").strip()
    if not token:
        token = secrets.token_urlsafe(18)
    if len(token) < 16:
        raise SystemExit("--lan-token 至少 16 字符（8.2 配对令牌）")
    lan = LanWebSocketTransport(token)
    await lan.start()
    print(
        f"[sidecar] LAN 终端接入 {lan.url()}",
        file=sys.stderr,
    )
    print("[sidecar] LAN 模式：单活动端点；token 配对（8.2）", file=sys.stderr)
    return lan, lan


async def _assemble_ws(argv: Sequence[str] | None) -> LocalWebSocketTransport | None:
    """组合根 WS 音频面装配：off 默认（阶段 0 壳侧接线在第三周拨）；auto 起 server。"""
    parser = argparse.ArgumentParser(prog="echoes_sidecar.main")
    parser.add_argument("--ws", choices=["off", "auto"], default="off")
    args, _ = parser.parse_known_args(list(argv) if argv is not None else None)
    if args.ws == "off":
        return None

    transport = LocalWebSocketTransport()
    port = await transport.start()
    print(f"[sidecar] WS 音频面监听 ws://127.0.0.1:{port}（壳侧连接即收帧）", file=sys.stderr)
    return transport


def _assemble_memory(
    argv: Sequence[str] | None,
    storage: Storage,
    llm: LLMProvider,
    *,
    model_dir: Path | None = None,
) -> tuple[MemoryStore | None, MemoryExtractor | None]:
    """组合根记忆装配（5.2）：auto 默认；mock 或权重缺失时关闭（不产假记忆）。

    `--memory on` 强制启用（权重缺失会在首次检索/写入报 MODEL_NOT_LOADED，
    用于验证错误路径）；`off` 完全关闭。bge 权重归 7.3 部署 bootstrap。
    """
    parser = argparse.ArgumentParser(prog="echoes_sidecar.main")
    parser.add_argument("--memory", choices=["auto", "on", "off"], default="auto")
    args, _ = parser.parse_known_args(list(argv) if argv is not None else None)

    if args.memory == "off":
        print("[sidecar] 记忆功能关闭（--memory off）", file=sys.stderr)
        return None, None

    weights = Path(model_dir) if model_dir is not None else DEFAULT_MODEL_DIR
    available = (weights / "config.json").is_file()
    if args.memory == "auto" and (llm.name == "mock" or not available):
        reason = "mock LLM" if llm.name == "mock" else f"bge 权重缺失: {weights}"
        print(f"[sidecar] 记忆功能未启用（auto：{reason}）", file=sys.stderr)
        return None, None

    if not available:
        print(
            f"[sidecar] 记忆权重缺失（{weights}）：首次检索/写入将报 MODEL_NOT_LOADED"
            "（7.3 bootstrap 预取；运行时不联网补救）",
            file=sys.stderr,
        )
    embedder = TransformersEmbedder(model_dir=weights)
    store = MemoryStore(storage.memories, embedder)
    # 隐私边界在上游落地（ADR-016）：设置层拒绝「云端 + 隐私模式」，Router 直接
    # 阻断云端 generate。这里若传静态 True，云端用户会永久静默失去记忆/摘要——
    # 那个开关是 ADR-001「只许本地」时代的产物，已不再成立。
    extractor = MemoryExtractor(llm, store, privacy_mode=False)
    print(f"[sidecar] 记忆功能启用（bge={weights}）", file=sys.stderr)
    return store, extractor


class _Warmable(Protocol):
    """分级就绪引擎的最小面（whisper / CosyVoice2 的 warmup 载荷，3.4 v1.4）。

    组合根 _gate_engine_ready 只认 warmup() 能力，不耦合具体引擎类型。
    """

    async def warmup(self) -> None: ...


def _try_preload(name: str, preload: Callable[[], None]) -> None:
    """预热失败只记 stderr 不中断服务（预热是优化面；warmup 的报错不降级链保底）。"""
    try:
        preload()
    except Exception as exc:  # noqa: BLE001  warmup 路径将复现同一缺件/死锁类问题
        print(
            f"[sidecar] {name} 主线程预热失败（warmup 路径将复现）: {exc}",
            file=sys.stderr,
        )


def _preload_runtime(tts_engine: TTSEngine, asr_engine: ASREngine) -> None:
    """主线程预热真路引擎的重型 C 依赖（3.2 执行约束细则；Windows 死锁规避，R20）。

    R20 实证：非主线程首次初始化 OpenBLAS 家族扩展（numpy/scipy）可在
    LoadLibrary 的 loader lock 下死锁（spawn+PIPE 形态 100% 复现）。预热必须
    发生在 gate 任务创建之前（见 serve），使 warmup 的 worker 只做权重物化。
    mock 引擎无此面，零成本。
    """
    if isinstance(tts_engine, CosyVoice2TtsEngine):
        print("[sidecar] 主线程预热 CosyVoice2 依赖链（R20）", file=sys.stderr)
        _try_preload("tts", tts_engine.preload)
    if isinstance(asr_engine, WhisperASREngine):
        print("[sidecar] 主线程预热 whisper 依赖链（R20）", file=sys.stderr)
        _try_preload("asr", asr_engine.preload)



async def _gate_engine_ready(
    transport: Transport,
    machine: StateMachine,
    engine_name: str,
    engine: _Warmable,
    engine_states: list[EngineState],
    t0: float,
) -> None:
    """分级就绪（3.4 v1.4）：warmup 完成 → 该引擎 ready=True → gate → 重发 hello/state。

    必需引擎（asr/llm，3.5 v1.4）gate 决定 booting→ready；tts 属分级就绪，
    就绪与否对状态机透明（就绪变化由 hello 重发承载）。
    """
    try:
        await engine.warmup()
    except Exception as exc:  # noqa: BLE001  权重下载失败等：报错不降级（保持现状）
        print(f"[sidecar] {engine_name} warmup 失败: {exc}", file=sys.stderr)
        return
    for state in engine_states:
        if state.name == engine_name:
            state.ready = True
    if (
        required_engines_ready((s.name, s.ready) for s in engine_states)
        and machine.state is not AppState.READY
    ):
        machine.transition(AppState.READY)
    await transport.send(_hello_payload(engine_states, _now_ms(t0)))
    await transport.send(_state_payload(machine, None, _now_ms(t0)))


def _hello_payload(engine_states: list[EngineState], t: int) -> dict[str, Any]:
    """3.4 hello（v1.4 schema）：首发与分级就绪重发共用同一组装点。"""
    return HelloMsg(sidecar_version=__version__, t=t, engines=engine_states).model_dump(
        mode="json"
    )


async def _clone_job(
    ws_transport: LocalWebSocketTransport,
    service: CloneService,
    sample_keys: Sequence[str],
    transport: Transport,
    session: Session,
    t0: float,
) -> bool:
    """克隆任务（后台，4.6/4.5）：先收 WS 样本，再交付 CloneService。

    必须后台跑：clone 是秒级以上的活，占住 stdio 主循环就再也收不到
    `clone_cancel`，取消形同虚设。

    等待样本要设上限：壳侧 bit2 帧与 clone_start 走两条通道（WS / stdio），到达顺序
    不保证——所以这里必须等；但等不到就该报错收场，不能让任务挂死把后续 turn 一起堵住。
    """
    try:
        pcm = await asyncio.wait_for(
            ws_transport.collect_clone_sample(), timeout=SAMPLE_WAIT_SECONDS
        )
    except TimeoutError:
        await _send_error(
            transport,
            session,
            EchoesError(
                ErrorCode.SAMPLE_TOO_SHORT,
                f"克隆样本未在 {SAMPLE_WAIT_SECONDS:.0f}s 内上送完成（WS 连接异常）",
            ),
            t0,
        )
        return False
    if not pcm:
        await _send_error(
            transport,
            session,
            EchoesError(
                ErrorCode.SAMPLE_TOO_SHORT,
                "未收到克隆样本（WS bit2 帧为空或连接已断开）",
            ),
            t0,
        )
        return False
    return await service.run(pcm, sample_keys)


async def serve(argv: Sequence[str] | None = None) -> None:
    """进程入口：注入运行时 → 开存储 → 跑服务 → 关存储（存储失败即 STORAGE_ERROR 冒泡，14.1）。

    运行时注入必须发生在任何引擎 import 之前（ADR-011）：冻结版只带契约链，
    torch/transformers 在外部档位目录里；dev 形态（`.venv`）不注入。
    """
    layout = runtime.inject()
    if layout is not None:
        # ASCII 标记：壳/首启引导按 `injected profile=` 解析 stderr（中文在 Windows 管道会变码）
        print(
            f"[runtime] injected profile={layout.profile} site={layout.site_packages}",
            file=sys.stderr,
        )
    paths, storage = _open_storage()
    try:
        await _serve_with_storage(argv, storage, paths)
    finally:
        storage.close()


async def _serve_with_storage(
    argv: Sequence[str] | None, storage: Storage, paths: DataPaths
) -> None:
    t0 = time.perf_counter()
    session = _open_session(storage, now=time.time())  # 5.1 + 14.1 重启重建

    # 组合根装配清单（3.2）：whisper/cosyvoice2 均走真路分级就绪（warmup 后台任务
    # 完成后重发 hello，3.4 v1.4）；mock 保留为无模型契约链。
    llm_provider, llm_ready = await _assemble_llm(argv)
    asr_engine, asr_ready = _assemble_asr(argv)
    tts_engine, tts_ready = _assemble_tts(argv, assets_dir=paths.assets_dir)
    transport, ws_transport = await _assemble_transports(argv)
    memory_store, memory_extractor = _assemble_memory(argv, storage, llm_provider)
    # 摘要与记忆共用同一个功能门：memory off / mock / bge 权重缺失时一起关闭。
    # mock LLM 下即使强制 --memory on 也不做摘要（否则会把 mock 台词写成摘要）。
    summarizer = (
        SessionSummarizer(llm_provider, storage.sessions, privacy_mode=False)
        if memory_extractor is not None and llm_provider.name != "mock"
        else None
    )
    # hello.engines 的清单顺序即装配顺序（3.4：壳以最后一份 hello 为准）
    engine_states: list[EngineState] = [
        EngineState(name="asr", ready=asr_ready),
        EngineState(name="tts", ready=tts_ready),
        EngineState(name="llm", ready=llm_ready),
    ]

    machine = StateMachine()
    # 4.6：会话登记与串行化守卫（编排层的 turn 从这里进出）
    manager = SessionManager()
    manager.create(session)
    # 4.3/10 编排层：turn 三节点的唯一实现，组合根只喂依赖（3.2）
    graph = TurnGraph(
        TurnDeps(
            transport=transport,
            llm=llm_provider,
            tts=tts_engine,
            t0=t0,
            egress=ws_transport,
            storage=storage,
            memory=memory_store,
            extractor=memory_extractor,
            summarizer=summarizer,
            settings_loader=lambda: load_runtime_settings(storage),
        ),
        machine,
        manager=manager,
    )
    # 3.5 单会话单在途 turn：文本面/语音面共用一个 turn 槽（串行 + 可打断）
    runner = TurnRunner()
    clone_service = CloneService(
        transport=transport,
        storage=storage,
        tts=tts_engine,
        session=session,
        assets_root=paths.assets_dir,
        t0=t0,
    )
    clone_task: asyncio.Task[bool] | None = None

    # 3.4 握手：第一行 hello；就绪_changes 时重发 hello（分级就绪载体，3.4 v1.4）
    await transport.send(_hello_payload(engine_states, _now_ms(t0)))
    await transport.send(_state_payload(machine, None, _now_ms(t0)))  # booting
    if required_engines_ready((s.name, s.ready) for s in engine_states):
        machine.transition(AppState.READY)
    else:
        print("[sidecar] 必需引擎(asr/llm)未就绪：停在 booting（3.5）", file=sys.stderr)
    await transport.send(_state_payload(machine, None, _now_ms(t0)))
    # 3.2 执行约束细则（R20）：主线程预热重型 C 依赖——首发 hello/booting/ready
    # 已写出（UI 有反馈），且必须早于 gate 任务（worker 线程不得触发首 import）。
    _preload_runtime(tts_engine, asr_engine)
    if isinstance(asr_engine, WhisperASREngine):
        asyncio.create_task(
            _gate_engine_ready(
                transport, machine, "asr", asr_engine, engine_states, t0
            )
        )
    if isinstance(tts_engine, CosyVoice2TtsEngine):
        asyncio.create_task(
            _gate_engine_ready(
                transport, machine, "tts", tts_engine, engine_states, t0
            )
        )

    # PTT 语音入口（3.4/§12 步骤 4）：WS 整段音频 → ASR → asr_final → turn。
    # ws=off 时无音频面；mock ASR 下也接线（壳侧无模型验收用）。
    if ws_transport is not None:
        asyncio.create_task(
            _asr_loop(
                ws_transport,
                transport,
                graph,
                session,
                asr_engine,
                t0,
                runner,
                is_cloning=lambda: clone_task is not None and not clone_task.done(),
            )
        )

    try:
        while (raw := await transport.recv()) is not None:
            try:
                msg = parse_obj(raw)
            except Exception as exc:  # noqa: BLE001  3.4：未知/畸形消息必须忽略
                print(f"[sidecar] 忽略不认识的消息（3.4 兼容规则）: {exc}", file=sys.stderr)
                continue

            if isinstance(msg, UserTextMsg):
                if machine.state is AppState.BOOTING or machine.state is AppState.ERROR:
                    # 3.5：booting/生成期用户请求不可触发 turn（语音面同规则）
                    print(
                        f"[sidecar] 状态 {machine.state.value} 收到 user_text，忽略（3.5）",
                        file=sys.stderr,
                    )
                    continue
                if clone_task is not None and not clone_task.done():
                    # 克隆期间不开新 turn：TTS 引擎被克隆占用，抢跑只会两边都慢
                    print("[sidecar] 克隆进行中，忽略 user_text", file=sys.stderr)
                    continue
                # 不 await：stdio 主循环必须继续读 control——那是打断的唯一入口；
                # start() 内部会先打断在途 turn（3.5「文本输入=打断并发起新 turn」）
                await runner.start(_turn_factory(graph, session, msg.text))
            elif isinstance(msg, ControlMsg):
                action = msg.action
                # interrupt 与 cancel_turn 在 sidecar 侧同义（都收束为 CANCELLED）；
                # 差异在壳：interrupt 随后立即开采集，cancel_turn 不采集（3.4 控制动词定案）
                interrupted = await runner.interrupt()
                if interrupted:
                    print(
                        f"[sidecar] control({action}) → 在途 turn 按 CANCELLED 收尾（三跳）",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"[sidecar] control({action})：无在途 turn，忽略（可容忍的协议噪声）",
                        file=sys.stderr,
                    )
            elif isinstance(msg, CloneStartMsg):
                if clone_task is not None and not clone_task.done():
                    print("[sidecar] 克隆进行中，忽略重复 clone_start", file=sys.stderr)
                    continue
                if machine.state is not AppState.READY:
                    # 3.5 用户动作矩阵：克隆入口只在 ready 可用（壳侧禁按钮，sidecar 兜底）
                    print(
                        f"[sidecar] 状态 {machine.state.value} 收到 clone_start，忽略（3.5）",
                        file=sys.stderr,
                    )
                    continue
                if ws_transport is None:
                    await _send_error(
                        transport,
                        session,
                        EchoesError(
                            ErrorCode.CLONE_ENGINE_FAILED,
                            "克隆样本经 WS 音频面上送，当前 --ws off 无法接收",
                        ),
                        t0,
                    )
                    continue
                clone_task = asyncio.create_task(
                    _clone_job(
                        ws_transport,
                        clone_service,
                        msg.sample_keys,
                        transport,
                        session,
                        t0,
                    )
                )
            elif isinstance(msg, CloneCancelMsg):
                clone_service.cancel()
                print("[sidecar] 收到 clone_cancel，已在阶段边界请求取消", file=sys.stderr)
            else:
                print(
                    f"[sidecar] 收到不该由壳上行的事件 {type(msg).__name__}（协议误用，已忽略）",
                    file=sys.stderr,
                )
    finally:
        # 先打断在途 turn（它还要往 transport 写 turn_complete），再关传输面
        await runner.interrupt()
        if ws_transport is not None:
            await ws_transport.close()
        await transport.close()


if __name__ == "__main__":
    if "--setup" in sys.argv[1:]:
        # 首启向导是一次性进程（JSON 行协议），不进聊天状态机
        from echoes_sidecar.setup_cli import main as setup_main

        raise SystemExit(setup_main(sys.argv[1:]))
    try:
        asyncio.run(serve(sys.argv[1:]))
    except KeyboardInterrupt:
        print("[sidecar] 收到中断，退出", file=sys.stderr)
