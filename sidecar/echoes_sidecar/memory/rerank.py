"""R3b 3.4 精排：bge-reranker-base（CPU）的懒加载封装。

**为什么默认 Noop**：reranker 权重不在「必需模型」清单里（§4.2 的 θ 还要用
R3b 评测集重标），没装权重的机器上必须能正常对话。`BgeReranker.available`
为假时编排层跳过精排与阈值门禁，保留 RRF 顺序——宁可不重排，也不能让
「没下模型」变成「聊不了」。

**为什么是同步 score()**：一次 8 条 × 512 token 的前向在 CPU 上几十毫秒到
几百毫秒，调用方用 `asyncio.to_thread` 包起来，避免阻塞事件循环（3.2）。

**模型目录**：`<models_root>/bge-reranker-base`（与 `models/manager.default_root`
同根）；HF 仓库 `BAAI/bge-reranker-base`。
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

DEFAULT_MODEL_DIR_NAME = "bge-reranker-base"
MAX_LENGTH = 512
BATCH_SIZE = 8
# sigmoid 后的门禁线；θ 必须在 R3b 评测集上重标（§4.2 ④），先给一个保守值
DEFAULT_MIN_SCORE = 0.0


class Reranker(Protocol):
    """精排器：返回与 texts 同序的相关性分数（0–1）。"""

    @property
    def available(self) -> bool: ...

    def score(self, query: str, texts: Sequence[str]) -> list[float]: ...


class NoopReranker:
    """未装权重时的占位：永远不可用，调用方据此跳过精排。"""

    available = False

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        _ = query
        return [0.0 for _ in texts]


class BgeReranker:
    """bge-reranker-base 交叉编码器（懒加载，CPU）。"""

    def __init__(self, model_dir: Path | None) -> None:
        self._dir = model_dir
        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self._failed = False

    @property
    def available(self) -> bool:
        if self._failed or self._dir is None:
            return False
        return (self._dir / "config.json").is_file() and any(
            (self._dir / name).is_file()
            for name in ("model.safetensors", "pytorch_model.bin")
        )

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        if not texts or not self.available:
            return [0.0 for _ in texts]
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            if self._model is None:
                assert self._dir is not None
                self._tokenizer = AutoTokenizer.from_pretrained(
                    str(self._dir), local_files_only=True
                )
                self._model = AutoModelForSequenceClassification.from_pretrained(
                    str(self._dir), local_files_only=True
                )
                self._model.eval()

            tokenizer = self._tokenizer
            model = self._model
            if tokenizer is None or model is None:
                raise RuntimeError("reranker 未加载")

            scores: list[float] = []
            with torch.no_grad():
                for start in range(0, len(texts), BATCH_SIZE):
                    batch = list(texts[start : start + BATCH_SIZE])
                    encoded = tokenizer(
                        [query] * len(batch),
                        batch,
                        padding=True,
                        truncation=True,
                        max_length=MAX_LENGTH,
                        return_tensors="pt",
                    )
                    logits = model(**encoded).logits.view(-1)
                    scores.extend(float(v) for v in torch.sigmoid(logits))
            return scores
        except Exception as exc:  # noqa: BLE001  精排失败退回 RRF 顺序
            self._failed = True
            print(f"[sidecar] reranker 不可用（本轮跳过精排）: {exc}", file=sys.stderr)
            return [0.0 for _ in texts]


def make_reranker(model_dir: Path | None) -> Reranker:
    """按目录是否装好权重决定真实精排 / 占位。"""
    if model_dir is None:
        return NoopReranker()
    reranker = BgeReranker(model_dir)
    return reranker if reranker.available else NoopReranker()


__all__ = [
    "BATCH_SIZE",
    "BgeReranker",
    "DEFAULT_MIN_SCORE",
    "DEFAULT_MODEL_DIR_NAME",
    "MAX_LENGTH",
    "NoopReranker",
    "Reranker",
    "make_reranker",
]
