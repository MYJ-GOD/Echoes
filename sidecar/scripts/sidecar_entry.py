"""PyInstaller 入口：`python -m` 等价物（main.py 只有 serve 协程，无 main()）。

源码直跑与冻结形态共用：`python scripts/sidecar_entry.py --llm mock ...`；
首启向导走同一入口：`echoes-sidecar.exe --setup detect`（一次性 JSON 行进程）。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(_SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(_SIDECAR_ROOT))

from echoes_sidecar.main import serve  # noqa: E402


def main() -> None:
    if "--setup" in sys.argv[1:]:
        from echoes_sidecar.setup_cli import main as setup_main

        raise SystemExit(setup_main(sys.argv[1:]))
    asyncio.run(serve())


if __name__ == "__main__":
    main()
