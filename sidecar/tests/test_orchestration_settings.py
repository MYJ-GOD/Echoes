"""3.4 拉取语义：每轮应用设置、provider 切换与人设覆盖。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from echoes_sidecar.db.repo import Storage
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.engines.llm.router import ProviderRouter
from echoes_sidecar.orchestration.graph import TriggerSource
from echoes_sidecar.session.runtime import RuntimeSettings
from tests.conftest import RecordingTransport, make_graph, make_session


class NamedLLM(LLMProvider):
    def __init__(self, name: str) -> None:
        self._name = name
        self.messages: list[list[dict[str, str]]] = []
        self.closed = False

    @property
    def name(self) -> str:
        return self._name

    async def health(self) -> bool:
        return True

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        _ = (stream, max_tokens, temperature)
        self.messages.append(messages)
        yield f"{self._name}回复"

    async def aclose(self) -> None:
        self.closed = True


class Factory:
    def __init__(self) -> None:
        self.created: list[tuple[str, str, NamedLLM]] = []

    def __call__(
        self, provider: str, model: str, base_url: str | None = None
    ) -> LLMProvider:
        _ = base_url
        instance = NamedLLM(provider)
        self.created.append((provider, model, instance))
        return instance


class SettingsBox:
    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings

    def __call__(self) -> RuntimeSettings:
        return self.settings


class BoomLoader:
    def __call__(self) -> RuntimeSettings:
        raise RuntimeError("db gone")


def _settings(**overrides: object) -> RuntimeSettings:
    base: dict[str, object] = {
        "provider": None,
        "model": None,
        "privacy_mode": True,
        "persona_name": None,
        "persona_system_prompt": None,
    }
    base.update(overrides)
    return RuntimeSettings(**base)  # type: ignore[arg-type]


async def test_persona_override_is_applied_per_turn() -> None:
    llm = NamedLLM("capture")
    box = SettingsBox(_settings(persona_name="小林", persona_system_prompt="你是小林，说话简洁。"))
    graph = make_graph(llm=llm, settings_loader=box)
    session = make_session()

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "你好"})

    assert llm.messages[0][0]["content"].startswith("你是小林")
    assert session.persona.name == "小林"
    assert session.persona.system_prompt == "你是小林，说话简洁。"


async def test_provider_switch_between_turns() -> None:
    initial = NamedLLM("initial")
    factory = Factory()
    router = ProviderRouter(initial, factory, provider="initial", model="m")
    box = SettingsBox(_settings())
    graph = make_graph(llm=router, settings_loader=box)
    session = make_session()

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "第一轮"})
    assert len(initial.messages) == 1

    box.settings = _settings(provider="mock", model="mock-model")
    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "第二轮"})

    assert router.name == "mock"
    assert len(initial.messages) == 1
    assert initial.closed is True
    assert [(p, m) for p, m, _ in factory.created] == [("mock", "mock-model")]
    assert len(factory.created[0][2].messages) == 1


async def test_settings_loader_failure_does_not_break_turn() -> None:
    transport = RecordingTransport()
    graph = make_graph(transport, settings_loader=BoomLoader())
    session = make_session()

    outcome = await graph.run_turn(
        session, TriggerSource.USER_INPUT, {"text": "你好"}
    )

    assert outcome.status == "SUCCESS"
    assert transport.only_turn_complete()["status"] == "SUCCESS"
    assert transport.of_type("error") == []
    assert session.persona.name == "默认人设"


async def test_persona_override_requires_both_fields() -> None:
    llm = NamedLLM("capture")
    box = SettingsBox(_settings(persona_name="只有名字"))
    graph = make_graph(llm=llm, settings_loader=box)
    session = make_session()

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "你好"})

    assert session.persona.name == "默认人设"
    assert llm.messages[0][0]["content"] == "s"


async def test_voice_selection_is_pulled_from_db_each_turn(tmp_path: Path) -> None:
    storage = Storage.open(tmp_path / "db" / "echoes.db")
    try:
        storage.personas.sync(
            persona_id="default", name="默认人设", system_prompt="s", now=1.0
        )
        storage.sessions.create(session_id="default", persona_id="default", now=1.0)
        storage.voices.insert_training(
            voice_id="clone:v1", display_name="音色 1", sample_path="a.wav", now=1.0
        )
        storage.voices.mark_ready("clone:v1")
        storage.sessions.bind_voice("default", "clone:v1")

        graph = make_graph(storage=storage, settings_loader=SettingsBox(_settings()))
        session = make_session()

        await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "第一轮"})
        assert session.voice_id == "clone:v1"

        storage.sessions.bind_voice("default", None)
        await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "第二轮"})
        assert session.voice_id is None
    finally:
        storage.close()
