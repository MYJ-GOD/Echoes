"""13.2-1：IPC 消息模型 → `src/lib/ipc_types.ts` 生成器（漂移守护的单一来源）。

**为什么要生成**：3.4 的 12 条消息是冻结契约，前端手抄一遍必然漂移（审计已记
「协议改动无守护」）。这里把 pydantic 模型当唯一事实，`--check` 模式与入库生成物
对拍，`git diff` 干净才算过——CI 与本地一条命令同一口径。

**为什么不引 datamodel-code-generator**：它按 JSON Schema 生成全量嵌套类型，输出
大且难 diff；本协议是扁平消息 + 少量字面量联合，40 行渲染就够，且能精确控制
「可选字段 → `name?: T | null`」这类前端友好的细节。

方向的分类（3.4 原文）不在模型里，也不该塞进冻结的 `schema.py`：本文件维护
`_SHELL_TO_SIDECAR`，出现未分类的新消息**直接报错**（逼一次显式决策，而不是
默默当事件发出去）。

用法（cwd = 仓库根）：
    node scripts/gen-ipc-types.mjs            # 写回 src/lib/ipc_types.ts
    node scripts/gen-ipc-types.mjs --check    # 只比对，漂移即非零退出
"""

from __future__ import annotations

import argparse
import sys
import types
import typing
from pathlib import Path
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

from echoes_sidecar.core.errors import ErrorCode
from echoes_sidecar.ipc import schema as ipc_schema

# 3.4「控制四类 = 壳→sidecar」；其余全部是 sidecar→壳的事件/状态。
_SHELL_TO_SIDECAR = frozenset({"control", "user_text", "clone_start", "clone_cancel"})
_SIDECAR_TO_SHELL = frozenset(
    {
        "hello",
        "asr_partial",
        "asr_final",
        "assistant_text",
        "turn_complete",
        "clone_progress",
        "error",
        "state",
    }
)

# 仓库根 → src/lib/ipc_types.ts（脚本按仓库根跑，生成物路径固定）
DEFAULT_OUT = Path("src/lib/ipc_types.ts")

_SCALARS: dict[Any, str] = {str: "string", int: "number", float: "number", bool: "boolean"}


def message_models() -> list[type[BaseModel]]:
    """从 `Message` 联合里取全部消息模型（新增消息自动进生成物，无需手改）。"""
    union = get_args(ipc_schema.Message)[0]
    return [model for model in get_args(union) if isinstance(model, type)]


def _nested_models(models: list[type[BaseModel]]) -> list[type[BaseModel]]:
    """消息里引用的内嵌模型（如 `Timings` / `EngineState`）：接口必须一并生成。"""
    found: dict[str, type[BaseModel]] = {}
    queue = list(models)
    while queue:
        model = queue.pop()
        for field in model.model_fields.values():
            for candidate in _walk_models(field.annotation):
                if candidate.__name__ not in found:
                    found[candidate.__name__] = candidate
                    queue.append(candidate)
    return [found[name] for name in sorted(found)]


def _walk_models(annotation: Any) -> list[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    found: list[type[BaseModel]] = []
    for arg in get_args(annotation):
        found.extend(_walk_models(arg))
    return found


def _ts_type(annotation: Any) -> tuple[str, bool]:
    """注解 → (TS 类型文本, 是否含 null)。只覆盖协议里真实用到的形态，其它报错。"""
    if annotation in _SCALARS:
        return _SCALARS[annotation], False
    if annotation is ErrorCode:
        return "ErrorCode", False
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation.__name__, False
    if annotation is type(None):
        return "null", True

    origin = get_origin(annotation)
    if origin is typing.Literal:
        return " | ".join(_literal(arg) for arg in get_args(annotation)), False
    if origin is list:
        item, _ = _ts_type(get_args(annotation)[0])
        return f"{item}[]", False
    if origin in (Union, types.UnionType):
        parts: list[str] = []
        nullable = False
        for arg in get_args(annotation):
            text, arg_nullable = _ts_type(arg)
            nullable = nullable or arg_nullable
            if not arg_nullable:
                parts.append(text)
        if not parts:  # 纯 None
            return "null", True
        return " | ".join(parts), nullable
    raise ValueError(f"无法映射到 TS 的注解：{annotation!r}（补 tsexport._ts_type）")


def _literal(value: object) -> str:
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _direction(model: type[BaseModel]) -> str:
    type_name = str(model.model_fields["type"].default)
    if type_name in _SHELL_TO_SIDECAR:
        return "shell"
    if type_name in _SIDECAR_TO_SHELL:
        return "sidecar"
    raise ValueError(
        f"消息 {model.__name__}（type={type_name}）未分类方向："
        "请在 ipc/tsexport.py 的 _SHELL_TO_SIDECAR / _SIDECAR_TO_SHELL 里显式登记（3.4）"
    )


def render() -> str:
    """渲染整份 TS 文件（生成物头部标明来源与再生成命令）。"""
    models = message_models()
    lines: list[str] = [
        "/**",
        " * 本文件由 `node scripts/gen-ipc-types.mjs` 生成，**不要手改**。",
        " * 唯一来源：sidecar/echoes_sidecar/ipc/schema.py（3.4 冻结协议，13.2-1）。",
        " * 手改会在 `npm run ipc:check` 与 CI schema-drift 里判红并给出再生成命令。",
        " */",
        "",
        f'export const PROTOCOL_VERSION = "{ipc_schema.PROTOCOL_VERSION}" as const;',
        "",
        "/** 3.4.1 错误码表（前端按 code 渲染文案/重试策略） */",
        "export type ErrorCode =",
    ]
    codes = [f'  | "{code.value}"' for code in ErrorCode]
    lines.extend(codes[:-1])
    lines.append(f"{codes[-1]};")
    lines.append("")

    for model in models + _nested_models(models):
        if model in models:
            peer = "sidecar" if _direction(model) == "shell" else "壳"
            lines.append(f"/** {model.__name__}（{_direction(model)} → {peer}） */")
        else:
            lines.append(f"/** {model.__name__}（嵌套结构体） */")
        lines.append(f"export interface {model.__name__} {{")
        for name, field in model.model_fields.items():
            annotation = field.annotation if field.annotation is not None else Any
            text, nullable = _ts_type(annotation)
            optional = "?" if nullable else ""
            lines.append(f"  {name}{optional}: {text};")
        lines.append("}")
        lines.append("")

    sidecar = [m for m in models if _direction(m) == "sidecar"]
    shell = [m for m in models if _direction(m) == "shell"]
    lines.append("/** sidecar → 壳：事件与状态（3.4） */")
    lines.append("export type SidecarMessage =")
    lines.extend(f"  | {m.__name__}" for m in sidecar[:-1])
    lines.append(f"  | {sidecar[-1].__name__};")
    lines.append("")
    lines.append("/** 壳 → sidecar：控制面（3.4 v1.4 四类） */")
    lines.append("export type ShellMessage =")
    lines.extend(f"  | {m.__name__}" for m in shell[:-1])
    lines.append(f"  | {shell[-1].__name__};")
    lines.append("")
    lines.append('export type SidecarMessageType = SidecarMessage["type"];')
    lines.append('export type ShellMessageType = ShellMessage["type"];')
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="echoes_sidecar.ipc.tsexport")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true", help="只比对，不写盘")
    args = parser.parse_args(argv)

    rendered = render()
    target: Path = args.out
    if args.check:
        if not target.is_file():
            print(f"缺生成物：{target}（先跑 node scripts/gen-ipc-types.mjs）", file=sys.stderr)
            return 1
        current = target.read_text(encoding="utf-8")
        if current != rendered:
            print(
                f"IPC 类型漂移：{target} 与 sidecar 模型不一致。\n"
                "修复：node scripts/gen-ipc-types.mjs（13.2-1）",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {target} 与 sidecar 模型一致")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    # 统一 LF：生成物入库后不该因平台换行产生假 diff
    target.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"已生成 {target}（{len(message_models())} 条消息）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
