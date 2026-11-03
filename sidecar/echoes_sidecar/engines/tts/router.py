"""TTS 引擎路由（R2a 2.5）：turn 边界按设置切换 provider，不重启进程。

**为什么需要这层**：判据 4「换 TTS 引擎不重启，下一句话就是新声音」。壳写
SQLite → sidecar 每轮 turn 前 `apply()`；turn 串行（TurnRunner），所以切换点
没有在途音频被换掉。

**失败保留**（3.4.1 不降级）：未知 provider / 云端构造失败 → 记 stderr 并保持
当前引擎；已选中的云端组合在隐私模式下 **报错**，而不是偷偷回退本地——那会把
用户的隐私选择变成假的。

**本地引擎只构造一次**：CosyVoice2 权重几十秒级，路由始终持有组合根给的实例；
`warmup`/`preload` 只在当前 provider 是本地时才执行（云端档不白占显存）。
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Callable

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.engines.llm.openai_compat import is_loopback
from echoes_sidecar.engines.tts.base import TTSEngine
from echoes_sidecar.engines.tts.mock import MockTTSEngine
from echoes_sidecar.engines.tts.openai_tts import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    OpenAITtsEngine,
)
from echoes_sidecar.secrets import engine_api_key

TtsFactory = Callable[[str, str, "str | None"], TTSEngine]

_VALID = frozenset({"mock", "cosyvoice2", "openai"})
_DEFAULT_TTS_MODEL = DEFAULT_MODEL
_DEFAULT_TTS_BASE = DEFAULT_BASE_URL


class TtsRouter(TTSEngine):
    """当前 TTS 引擎的稳定门面；`name`/`current` 随切换变化。"""

    def __init__(
        self,
        local: TTSEngine,
        *,
        local_provider: str = "cosyvoice2",
        factory: TtsFactory | None = None,
        provider: str = "cosyvoice2",
        model: str = "",
        base_url: str | None = None,
    ) -> None:
        self._local = local
        self._local_provider = local_provider
        self._factory = factory or _default_factory
        self._provider = provider if provider in _VALID else "cosyvoice2"
        self._model = model
        self._base_url = base_url
        self._cache: dict[tuple[str, str, str | None], TTSEngine] = {}
        self._blocked = False
        try:
            self._engine = self._engine_for(self._provider, self._model, self._base_url)
        except Exception as exc:  # noqa: BLE001  云端构造失败 → 保留本地引擎
            print(f"[sidecar] TTS 初始引擎构造失败（回退本地装配）: {exc}", file=sys.stderr)
            self._provider = local_provider
            self._engine = local

    # ------------------------------ 观测 ------------------------------

    @property
    def name(self) -> str:
        return self._engine.name if hasattr(self._engine, "name") else self._provider

    @property
    def current(self) -> tuple[str, str]:
        """(provider, model)：hello 里回报 active_* 用（2.5 / 2.12）。

        本地链没有"模型"概念（CosyVoice2 固定 0.5B），回空串而不是借用云端默认值。
        """
        if self._provider == "openai":
            return self._provider, self._model or _DEFAULT_TTS_MODEL
        return self._provider, ""

    @property
    def warms_up(self) -> bool:
        """当前 provider 是否走本地权重预热（决定 boot 期要不要建 gate）。"""
        return (
            self._provider == "cosyvoice2"
            and self._local_provider == "cosyvoice2"
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
                f"[sidecar] 忽略未知 TTS provider {target_provider!r}（2.5 不降级）",
                file=sys.stderr,
            )
            return

        # 隐私判定每轮重算（设置可能在轮间被改），即使 provider 没变
        self._blocked = (
            target_provider == "openai"
            and not allow_cloud
            and not is_loopback(target_base)
        )
        if self._blocked:
            print(
                "[sidecar] 隐私模式开启：云端 TTS 已在设置页被选中，"
                "本轮将报错（本机环回端点不受此限）",
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
        except Exception as exc:  # noqa: BLE001  构造失败保持旧实例（3.4.1）
            print(f"[sidecar] TTS 引擎切换失败（沿用旧引擎）: {exc}", file=sys.stderr)
            return

        self._engine = engine
        self._provider = target_provider
        self._model = target_model
        self._base_url = target_base
        print(
            f"[sidecar] TTS 引擎已切换：{target_provider} / {target_model or '-'}"
            "（2.5 拉取）",
            file=sys.stderr,
        )

    # ------------------------------ 契约 ------------------------------

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        if self._blocked:
            raise EchoesError(
                ErrorCode.TTS_ENGINE_ERROR,
                "隐私模式已开启：云端 TTS 不允许出网（设置 → 引擎 → 语音合成，"
                "或改用本地 CosyVoice2）",
            )
        async for chunk in self._engine.synthesize(text, voice_id):
            yield chunk

    async def clone(self, sample: AudioInputStream) -> str:
        return await self._engine.clone(sample)

    @property
    def supports_similarity_check(self) -> bool:
        return self._engine.supports_similarity_check

    async def speaker_similarity(self, sample_pcm: bytes, synth_pcm: bytes) -> float:
        return await self._engine.speaker_similarity(sample_pcm, synth_pcm)

    async def aclose(self) -> None:
        for engine in self._cache.values():
            closer = getattr(engine, "aclose", None)
            if closer is None:
                continue
            try:
                await closer()
            except Exception as exc:  # noqa: BLE001  关闭失败不影响退出
                print(f"[sidecar] 旧 TTS 客户端关闭失败: {exc}", file=sys.stderr)
        self._cache.clear()

    # ------------------------------ 内部 ------------------------------

    def _engine_for(
        self, provider: str, model: str, base_url: str | None
    ) -> TTSEngine:
        if provider == self._local_provider:
            return self._local
        if provider == "cosyvoice2":
            # mock 装配（ECHOES_SIDECAR_MOCK=1 / --tts mock）下没有本地权重：
            # 不偷偷构造一个重引擎，按「失败保留」处理，重启换装配后生效
            raise ValueError(
                "本次启动未装配本地 CosyVoice2（--tts mock）；重启 sidecar 后生效"
            )
        key = (provider, model, base_url)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        engine = self._factory(provider, model, base_url)
        self._cache[key] = engine
        return engine


def _default_factory(provider: str, model: str, base_url: str | None) -> TTSEngine:
    if provider == "mock":
        return MockTTSEngine()
    if provider == "openai":
        return OpenAITtsEngine(
            model=model or _DEFAULT_TTS_MODEL,
            base_url=base_url or _DEFAULT_TTS_BASE,
            key_provider=lambda: engine_api_key("tts", "openai"),
        )
    raise ValueError(f"不支持的 TTS provider：{provider}")


__all__ = ["TtsFactory", "TtsRouter"]
