"""R3b 3.5：用标注对扫 reranker 阈值（θ），输出建议值与分数分布。

用法（在 sidecar 目录）::

    .venv\\Scripts\\python scripts\\calibrate_theta.py --pairs tests/fixtures/theta_pairs.jsonl
    .venv\\Scripts\\python scripts\\calibrate_theta.py --pairs ... --grid 0.1,0.2,0.3

前提：`bge-reranker-base` 权重已安装（`--setup install-models --ids bge-reranker-base`）。
没有权重时脚本返回非零并提示安装，不会伪造分数。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from echoes_sidecar.core.errors import EchoesError
from echoes_sidecar.memory.calibrate import DEFAULT_GRID, load_pairs, score_pairs, sweep
from echoes_sidecar.memory.rerank import DEFAULT_MODEL_DIR_NAME, make_reranker
from echoes_sidecar.models.manager import default_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="calibrate_theta")
    parser.add_argument("--pairs", required=True, help="JSONL：query/passage/relevant")
    parser.add_argument(
        "--models-root",
        default=None,
        help="模型根目录（默认 ~/.cache/echoes/models）",
    )
    parser.add_argument(
        "--grid",
        default=",".join(str(value) for value in DEFAULT_GRID),
        help="逗号分隔的候选阈值",
    )
    parser.add_argument("--out", default=None, help="把结果写成 JSON 文件")
    args = parser.parse_args(argv)

    try:
        grid = tuple(float(item) for item in args.grid.split(",") if item.strip())
        pairs = load_pairs(Path(args.pairs))
        models_root = Path(args.models_root) if args.models_root else default_root()
        reranker = make_reranker(models_root / DEFAULT_MODEL_DIR_NAME)
        samples = score_pairs(pairs, reranker)
        best = sweep(samples, grid)
    except (EchoesError, ValueError) as exc:
        print(f"[calibrate] {exc}", file=sys.stderr)
        return 1

    positives = [score for score, relevant in samples if relevant]
    negatives = [score for score, relevant in samples if not relevant]
    report = {
        "pairs": len(samples),
        "positives": len(positives),
        "negatives": len(negatives),
        "positiveMean": round(sum(positives) / len(positives), 4) if positives else None,
        "negativeMean": round(sum(negatives) / len(negatives), 4) if negatives else None,
        "suggestedThreshold": best.threshold,
        "precision": round(best.precision, 4),
        "recall": round(best.recall, 4),
        "f1": round(best.f1, 4),
        "grid": list(grid),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out:
        Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
