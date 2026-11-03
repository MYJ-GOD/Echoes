"""ASR 引擎路由（R2a 2.5）：PTT 每次转写前按设置切换 provider。

**为什么在转写前 apply**：ASR 不经过 TurnGraph（PTT 先转写、再起 turn），
所以设置拉取点放在 `_asr_loop` 的 PTT 边界；turn 串行 + PTT 串行，没有在途
转写被换掉。

**失败保留**（3.4.1 不降级）：未知 provider / 云端构造失败 → 保持当前引擎；
隐私模式下选中公网云端 → 转写直接报错（不静默回退本地）。原始录音出境比
文本更难收回，这里是隐私矩阵里最严的一条。
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Callable
from typing import Any

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.engines.asr.base import ASREngine
from echoes_sidecar.engines.asr.mock import MockASREngine
from echoes_sidecar.engines.asr.openai_audio import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    OpenAIAudioASREngine,
)
from echoes_sidecar.engines.llm.openai_compat import is_loopback
from echoes_sidecar.secrets import engine_api_key

AsrFactory = Callable[[str, str, "str | None"], ASREngine]

_VALID = frozenset({"mock", "whisper", "openai"})


class AsrRouter(ASREngine):
    """当前 ASR 引擎的稳定门面。"""

    def __init__(
        self,
        local: ASREngine,
        *,
        local_provider: str = "whisper",
        factory: AsrFactory | None = None,
        provider: str = "whisper",
        model: str = "",
        base_url: str | None = None,
    ) -> None:
        self._local = local
        self._local_provider = local_provider
        self._factory = factory or _default_factory
        self._provider = provider if provider in _VALID else "whisper"
        self._model = model
        self._base_url = base_url
        self._cache: dict[tuple[str, str, str | None], ASREngine] = {}
        self._blocked = False
        try:
            self._engine = self._engine_for(self._provider, self._model, self._base_url)
        except Exception as exc:  # noqa: BLE001  云端构造失败 → 保留本地引擎
            print(f"[sidecar] ASR 初始引擎构造失败（回退本地装配）: {exc}", file=sys.stderr)
            self._provider = local_provider
            self._engine = local

    # ------------------------------ 观测 ------------------------------

    @property
    def current(self) -> tuple[str, str]:
        """(provider, model)：hello 里回报 active_*（2.5 / 2.12）。"""
        if self._provider == "openai":
            return self._provider, self._model or DEFAULT_MODEL
        if self._provider == "whisper":
            local = getattr(self._local, "current", None)
            return "whisper", (local[1] if local else "")
        return "mock", ""

    @property
    def warms_up(self) -> bool:
        return (
            self._provider == "whisper"
            and self._local_provider == "whisper"
            and hasattr(self._local, "warmup")
        )

    def preload(self) -> None:
        if not self.warms_up:
            return
        preload = getattr(self._local, "preload", None)
        if preload is not None:
            preload()

    async def warmup(self) -> None:
        if not self.warms_up:
            return
        warmup = getattr(self._local, "warmup", None)
        if warmup is not None:
            await warmup()

    # ------------------------------ 切换 ------------------------------

    async def apply(
        self,
        *,
        provider: str | None,
        model: str | None,
        base_url: str | None = None,
        allow_cloud: bool = True,
    ) -> None:
        target_provider = provider or self._provider
        target_model = model if model is not None else self._model
        target_base = base_url if base_url is not None else self._base_url
        if target_provider not in _VALID:
            print(
                f"[sidecar] 忽略未知 ASR provider {target_provider!r}（2.5 不降级）",
                file=sys.stderr,
            )
            return

        # 隐私判定每轮重算（设置可能在轮间被改）
        self._blocked = (
            target_provider == "openai"
            and not allow_cloud
            and not is_loopback(target_base)
        )
        if self._blocked:
            print(
                "[sidecar] 隐私模式开启：云端 ASR 已在设置页被选中，"
                "本轮转写将报错（本机环回端点不受此限）",
                file=sys.stderr,
            )

        if (target_provider, target_model, target_base) == (
            self._provider,
            self._model,
            self._base_url,
        ):
            return

        try:
            engine = self._engine_for(target_provider, target_model, target_base)
        except Exception as exc:  # noqa: BLE001  构造失败保持旧实例
            print(f"[sidecar] ASR 引擎切换失败（沿用旧引擎）: {exc}", file=sys.stderr)
            return

        self._engine = engine
        self._provider = target_provider
        self._model = target_model
        self._base_url = target_base
        print(
            f"[sidecar] ASR 引擎已切换：{target_provider} / {target_model or '-'}"
            "（2.5 拉取）",
            file=sys.stderr,
        )

    # ------------------------------ 契约 ------------------------------

    async def transcribe(self, audio: AudioInputStream) -> AsyncIterator[dict[str, Any]]:
        if self._blocked:
            raise EchoesError(
                ErrorCode.ASR_ENGINE_ERROR,
                "隐私模式已开启：云端 ASR 不允许出网（原始录音不出本机）。"
                "请在设置里改用本地 whisper，或关闭隐私模式",
            )
        async for segment in self._engine.transcribe(audio):
            yield segment

    async def aclose(self) -> None:
        for engine in self._cache.values():
            closer = getattr(engine, "aclose", None)
            if closer is None:
                continue
            try:
                await closer()
            except Exception as exc:  # noqa: BLE001
                print(f"[sidecar] 旧 ASR 客户端关闭失败: {exc}", file=sys.stderr)
        self._cache.clear()

    # ------------------------------ 内部 ------------------------------

    def _engine_for(
        self, provider: str, model: str, base_url: str | None
    ) -> ASREngine:
        if provider == self._local_provider:
            return self._local
        if provider == "whisper":
            raise ValueError(
                "本次启动未装配本地 whisper（--asr mock）；重启 sidecar 后生效"
            )
        key = (provider, model, base_url)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        engine = self._factory(provider, model, base_url)
        self._cache[key] = engine
        return engine


def _default_factory(provider: str, model: str, base_url: str | None) -> ASREngine:
    if provider == "mock":
        return MockASREngine()
    if provider == "openai":
        return OpenAIAudioASREngine(
            model=model or DEFAULT_MODEL,
            base_url=base_url or DEFAULT_BASE_URL,
            key_provider=lambda: engine_api_key("asr", "openai"),
        )
    raise ValueError(f"不支持的 ASR provider：{provider}")


__all__ = ["AsrFactory", "AsrRouter"]
