"""LLM provider 路由（3.4 拉取语义 / 4.4）：设置变化时在 turn 边界切换 provider。

**为什么需要这层**：壳写入 SQLite 后，sidecar 在下一个 turn 读取新 provider/model；
不能重启进程。路由持有当前 provider，`apply()` 在配置变化时构造新实例并关闭旧客户端。
turn 是串行的（TurnRunner），切换只发生在 turn 开始前，没有在途 generate 被换掉。

**边界**：mock 是测试/无模型链；ollama 是本地真路；openai 是 OpenAI 兼容端点
（云端或本地 LM Studio/vLLM）。未知 provider 忽略并保持当前，不静默换成 mock
（3.4.1 报错不降级）。
"""
from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Callable

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.engines.llm.openai_compat import is_loopback

# provider/model/base_url 三者任一变化都要重建（base_url 只对 openai 有意义）
ProviderFactory = Callable[[str, str, "str | None"], LLMProvider]

_VALID = frozenset({"mock", "ollama", "openai"})


class ProviderRouter(LLMProvider):
    """当前 provider 的稳定门面；`name` 随切换变化（记忆/摘要据此判断 mock/云端）。"""

    def __init__(
        self,
        initial: LLMProvider,
        factory: ProviderFactory,
        *,
        provider: str,
        model: str,
        base_url: str | None = None,
    ) -> None:
        self._provider = initial
        self._factory = factory
        self._provider_name = provider
        self._model = model
        self._base_url = base_url
        # 启动期还不知道隐私设置：每轮 apply() 重新判定（3.4 拉取语义）
        self._blocked = False

    @property
    def name(self) -> str:
        return self._provider.name

    @property
    def current(self) -> tuple[str, str]:
        """(provider, model)：hello 里回报 active_*（R2a 2.5）。"""
        return self._provider_name, self._model

    async def health(self) -> bool:
        return await self._provider.health()

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        if self._blocked:
            raise EchoesError(
                ErrorCode.LLM_PROVIDER_UNAVAILABLE,
                "隐私模式已开启：云端 LLM 不允许出网（设置 → 引擎，或改用本地 Ollama）",
            )
        async for piece in self._provider.generate(
            messages, stream=stream, max_tokens=max_tokens, temperature=temperature
        ):
            yield piece

    async def apply(
        self,
        *,
        provider: str | None,
        model: str | None,
        base_url: str | None = None,
        allow_cloud: bool = True,
    ) -> None:
        """配置变了才重建；未知 provider 保持当前并记 stderr。

        `allow_cloud=False`（隐私模式）时只拦「会出网」的组合：`openai` + 公网地址。
        `openai` + 环回地址不出网（LM Studio / vLLM / Ollama `/v1`），按 ADR-016 §3
        矩阵照常放行——把本机端点也拒掉，等于让隐私模式用户失去本地兼容端点。
        公网被拦时 `generate` 直接报错，**不静默退回本地**——那会把用户的隐私选择
        变成假的。
        """
        target_provider = provider or self._provider_name
        target_model = model or self._model
        target_base = base_url if base_url is not None else self._base_url
        if target_provider not in _VALID:
            print(
                f"[sidecar] 忽略未知 LLM provider {target_provider!r}（4.4 不降级）",
                file=sys.stderr,
            )
            return
        self._blocked = (
            target_provider == "openai"
            and not allow_cloud
            and not is_loopback(target_base)
        )
        if self._blocked:
            print(
                "[sidecar] 隐私模式开启：云端 LLM 已在设置页被选中，turn 将报错"
                "（本机环回端点不受此限）",
                file=sys.stderr,
            )
        if (target_provider, target_model, target_base) == (
            self._provider_name,
            self._model,
            self._base_url,
        ):
            return

        new_provider = self._factory(target_provider, target_model, target_base)
        old_provider = self._provider
        self._provider = new_provider
        self._provider_name = target_provider
        self._model = target_model
        self._base_url = target_base
        await _close(old_provider)
        print(
            f"[sidecar] LLM provider 已切换：{target_provider} / {target_model}（3.4 拉取）",
            file=sys.stderr,
        )

    async def aclose(self) -> None:
        await _close(self._provider)


async def _close(provider: LLMProvider) -> None:
    closer = getattr(provider, "aclose", None)
    if closer is None:
        return
    try:
        await closer()
    except Exception as exc:  # noqa: BLE001  关闭旧客户端失败不影响新 provider
        print(f"[sidecar] 旧 LLM 客户端关闭失败: {exc}", file=sys.stderr)


__all__ = ["ProviderFactory", "ProviderRouter"]
