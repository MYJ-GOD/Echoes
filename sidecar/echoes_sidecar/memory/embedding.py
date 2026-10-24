"""嵌入 provider（ADR-006 默认档 bge-small-zh，512 维）。

**为什么不装 `sentence-transformers`**：它会把 torch/transformers 的版本自由度拉回来
（15.1 的「== 精确锁」是我们的锚），而 bge 系列就是普通 BERT + CLS 池化 + L2 归一化。
直接用已锁的 `transformers` 加载，少一层依赖、少一处版本漂移面。

**权重边界（7.3）**：模型目录在 `~/.cache/echoes/models/bge-small-zh-v1.5`，由部署
bootstrap 预取；运行时目录缺失 → `MODEL_NOT_LOADED` 报错，**绝不联网回退**
（离线红线，同 CosyVoice2 与 wetext 的处理）。

**执行约束（3.2）**：一次前向是同步重活，一律 `asyncio.to_thread`，不占事件循环。
"""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.db.memory_repo import EMBEDDING_DIM

_DEFAULT_MODEL_DIR = Path.home() / ".cache" / "echoes" / "models" / "bge-small-zh-v1.5"
DEFAULT_MODEL_DIR = _DEFAULT_MODEL_DIR


@runtime_checkable
class Embedder(Protocol):
    """嵌入契约：文本 → 定长向量（维度必须等于存储列宽）。"""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def normalize(vector: Sequence[float]) -> list[float]:
    """L2 归一化（bge 的检索口径：归一化后 L2 距离等价 cosine 排序）。"""
    total = sum(value * value for value in vector) ** 0.5
    if total == 0.0:
        raise EchoesError(ErrorCode.INTERNAL_ERROR, "嵌入向量全零，无法归一化")
    return [value / total for value in vector]


class TransformersEmbedder:
    """`transformers` 直载 bge-small-zh：CLS 池化 + L2 归一化（ADR-006 默认档）。"""

    def __init__(self, *, model_dir: Path | str | None = None, max_length: int = 512) -> None:
        self._model_dir = Path(model_dir) if model_dir is not None else _DEFAULT_MODEL_DIR
        self._max_length = max_length
        self._model: Any | None = None  # transformers 无 stub，Any 口
        self._tokenizer: Any | None = None

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        await self._ensure_loaded()
        return await asyncio.to_thread(self._embed_sync, list(texts))

    async def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        await asyncio.to_thread(self._load)

    def _load(self) -> None:
        # 先查目录再 import：目录缺失时绝不 import（防止 transformers 内部走 hub 回退）
        if not self._model_dir.is_dir():
            raise EchoesError(
                ErrorCode.MODEL_NOT_LOADED,
                f"嵌入权重不存在: {self._model_dir}"
                "（7.3 下载边界外，部署 bootstrap 预取，运行时不联网补救）",
            )
        import torch  # noqa: F401  显式：确保与 transformers 用同一个 torch
        from transformers import AutoModel, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(str(self._model_dir))
        model = AutoModel.from_pretrained(str(self._model_dir))
        model.eval()
        self._model = model
        dim = int(model.config.hidden_size)
        if dim != EMBEDDING_DIM:
            raise EchoesError(
                ErrorCode.MODEL_NOT_LOADED,
                f"嵌入维度 {dim} 与存储列宽 {EMBEDDING_DIM} 不符"
                "（切档要新建迁移重建 memory_vec，见 0002 头注释）",
            )

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        import torch

        assert self._tokenizer is not None and self._model is not None
        batch = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self._max_length,
            return_tensors="pt",
        )
        with torch.no_grad():
            output = self._model(**batch)
        cls = output.last_hidden_state[:, 0]  # bge：CLS 位即句向量
        return [normalize(row.tolist()) for row in cls]


__all__ = ["DEFAULT_MODEL_DIR", "EMBEDDING_DIM", "Embedder", "TransformersEmbedder", "normalize"]
