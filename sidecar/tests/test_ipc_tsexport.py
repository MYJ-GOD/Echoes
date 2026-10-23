"""13.2-1：IPC 类型生成器的口径（`ipc_types.ts` 由 pydantic 模型生成）。

本地四闸也守漂移：`test_generated_file_matches_models` 等价于 CI 的
`node scripts/gen-ipc-types.mjs --check`，改协议忘了重生成会在这里红。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from echoes_sidecar.core.errors import ErrorCode
from echoes_sidecar.ipc import schema as ipc_schema
from echoes_sidecar.ipc import tsexport

# sidecar/tests/ → 仓库根 → src/lib/ipc_types.ts
_GENERATED = Path(__file__).resolve().parents[2] / "src" / "lib" / "ipc_types.ts"


def test_all_messages_are_classified_by_direction() -> None:
    """新增消息必须显式登记方向（3.4）：未分类即报错，不允许默认当事件发出去。"""
    models = tsexport.message_models()
    assert len(models) == 12
    for model in models:
        assert tsexport._direction(model) in {"shell", "sidecar"}


def test_unclassified_message_raises() -> None:
    from pydantic import BaseModel

    class FutureMsg(BaseModel):
        type: Literal["future"] = "future"

    with pytest.raises(ValueError, match="未分类方向"):
        tsexport._direction(FutureMsg)


def test_optional_field_becomes_optional_property() -> None:
    """`int | None` → `name?: number`（前端免判空，与 pydantic 的 null 语义对齐）。"""
    assert tsexport._ts_type(int | None) == ("number", True)
    assert tsexport._ts_type(str) == ("string", False)
    assert tsexport._ts_type(list[str]) == ("string[]", False)
    assert tsexport._ts_type(Literal["a", "b"]) == ('"a" | "b"', False)


def test_unmappable_annotation_raises() -> None:
    """映射不了的注解要炸（报错而非降级：悄悄输出 `any` 会让守护形同虚设）。"""
    with pytest.raises(ValueError, match="无法映射"):
        tsexport._ts_type(dict[str, str])


def test_nested_models_are_emitted() -> None:
    """嵌套结构体（Timings/EngineState）没有 type 字段，不会被当成信封。"""
    names = {model.__name__ for model in tsexport._nested_models(tsexport.message_models())}
    assert names == {"EngineState", "Timings"}


def test_render_is_deterministic() -> None:
    assert tsexport.render() == tsexport.render()


def test_render_covers_every_message_and_error_code() -> None:
    rendered = tsexport.render()
    for model in tsexport.message_models():
        assert f"export interface {model.__name__} {{" in rendered
    for code in ErrorCode:
        assert f'"{code.value}"' in rendered
    assert f'PROTOCOL_VERSION = "{ipc_schema.PROTOCOL_VERSION}"' in rendered


def test_generated_file_matches_models() -> None:
    """入库生成物必须与当前模型一致（CI 同口径；漂移时给出重生成命令）。"""
    assert _GENERATED.is_file(), f"缺生成物 {_GENERATED}：node scripts/gen-ipc-types.mjs"
    assert _GENERATED.read_text(encoding="utf-8") == tsexport.render(), (
        "IPC 类型漂移：重跑 node scripts/gen-ipc-types.mjs（13.2-1）"
    )
