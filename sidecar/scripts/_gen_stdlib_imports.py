"""生成 stdlib hidden-import 清单：warmup 后 sys.modules ∩ stdlib（完整点分名）。"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from echoes_sidecar.engines.tts.cosyvoice2 import CosyVoice2TtsEngine  # noqa: E402

OUT = Path(r"C:\Users\BigGayGod\Desktop\Echoes\sidecar\scripts\stdlib_hidden_imports.txt")

HEADER = """# 仅被运行时（torch / transformers / cosyvoice）动态 import 的 stdlib 模块。
#
# 为什么需要这份清单：ONEDIR 不打包 torch，PyInstaller 静态分析看不到 torch 内部
# 的 import，于是这些模块在冻结版里会 ModuleNotFoundError（实测 timeit、pickletools、
# http.cookies）。清单由真实 warmup 后 `sys.modules ∩ stdlib_module_names` 生成，
# 含子模块（http.cookies 这类）。
#
# 重新生成：python scripts/_gen_stdlib_imports.py（构建机，需模型权重已就绪）。
# 新增依赖导致缺件时手加一行也行；已打进包的模块重复列出无副作用。
"""


async def main() -> None:
    tts = CosyVoice2TtsEngine()
    await tts.warmup()
    stdlib = sys.stdlib_module_names
    names = sorted(
        name
        for name in sys.modules
        if name.split(".")[0] in stdlib and not name.startswith("_")
    )
    OUT.write_text(HEADER + "\n".join(names) + "\n", encoding="utf-8")
    print(f"wrote {len(names)} modules → {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
