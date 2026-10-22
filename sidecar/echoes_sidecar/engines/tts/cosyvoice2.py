"""CosyVoice2TtsEngine（4.5 契约实现；ADR-014 vendored 搬运，阶段 0 第二周尾部）。

形态决策（ADR-014 / tier_matrix 冒烟实测）：
- vendored cosyvoice（main 074ca6d）依赖子集进 pyproject（== 锚），vendor 目录
  禁手改；0.5B 权重无内置 sft 音色（spk2info.pt 缺失）→ zero-shot 是唯一合成面。
- 权重（7.3 运行时下载边界）：~/.cache/echoes/models/CosyVoice2-0.5B；缺失 =
  EchoesError(MODEL_NOT_LOADED) 报错不降级——先查目录再实例化，vendored 的
  snapshot_download 联网回退绝不触发（离线红线①，下载归部署 bootstrap）。
  同红线延伸：wetext 快照（vendor frontend 正则化依赖）载入时钉成
  local_files_only 零网 + 缓存预校验（vendored 的裸 except 会把 Normalizer
  构造失败吞成 silent no-frontend 文本面，R20 探针实证联网态可载入期假死）。
- boot 硬序（ADR-014 修订 7）：sys.path 注入 vendor → import torch →
  os.add_dll_directory(torch/lib)（cudnn/cublas 供 onnxruntime-gpu 的 CUDA EP；
  ort 静默回 CPU 必须显式 get_providers() 验证，DLL 缺失 GPUs 上直接掉速）→
  才能 import cosyvoice。_ensure_vendor_boot() 幂等。
- 内置音色 builtin:default：scripts/make_builtin_prompt.py 生成的一次性
  prompt wav 资产（Windows SAPI Huihui，16k mono PCM16）+ 配对文本，wav 与
  文本严格配对入库；zero-shot 声音克隆的前提是两者一致。
- 分级就绪（同 whisper，3.4 v1.4）：ready=False 首发 → warmup() 后台加载 →
  组合根置 ready 重发 hello；未 warmup 即 synthesize = MODEL_NOT_LOADED 报错。
- RTF 1.33（T-4060 fp16 实测）> 1：连续流式跟播不可行 → 「整句产出按句播」
  消费语义在壳侧；本层保证逐段产出与段尾 is_final 边界。
"""

from __future__ import annotations

import asyncio
import os
import queue
import sys
import threading
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.engines.tts.base import TTSEngine

__all__ = [
    "BUILTIN_DEFAULT_PROMPT_TEXT",
    "BUILTIN_DEFAULT_PROMPT_WAV",
    "BUILTIN_DEFAULT_VOICE",
    "CosyVoice2TtsEngine",
    "np_to_pcm16",
]

BUILTIN_DEFAULT_VOICE = "builtin:default"  # 2.5 保留 ID（none 态解析目标）

# 与 builtin_default_prompt.wav 严格配对（scripts/make_builtin_prompt.py 唯一来源）
BUILTIN_DEFAULT_PROMPT_TEXT = (
    "你好，我是 Echoes。我住在这台电脑里，全程离线运行，不用联网。今天想聊点什么？我在听。"
)
BUILTIN_DEFAULT_PROMPT_WAV = (
    Path(__file__).resolve().parent / "assets" / "builtin_default_prompt.wav"
)
_DEFAULT_MODEL_DIR = Path.home() / ".cache" / "echoes" / "models" / "CosyVoice2-0.5B"

# wetext（vendored frontend 文本正则化依赖）在 modelscope 的快照仓：
# 运行时一律 local_files_only 零网（R20 实证：联网补拉在匿名限频 403 +
# stdin=PIPE 进程形态下级联成载入期假死）；补齐归部署 bootstrap（7.3）。
_WETEXT_REPO = "pengzhendong/wetext"
_WETEXT_SNAPSHOT_FILES = (
    "en/tn/tagger.fst",
    "en/tn/verbalizer.fst",
    "zh/tn/tagger.fst",  # frontend.py zh_tn_model 实际加载面
    "zh/tn/verbalizer.fst",
)

_VENDOR_BOOTED = False


def np_to_pcm16(arr: Any) -> bytes:
    """float32 [-1,1] → PCM16 LE 单声道 bytes（3.4 输出口径：24kHz mono）。

    幅度溢出钳制；int16 量化朝零截断（壳侧同款实现对拍基准）；纯函数供单测锁。
    """
    import numpy as np

    a = np.asarray(arr, dtype=np.float32).reshape(-1)
    a = np.clip(a, -1.0, 1.0)
    return (a * 32767.0).astype("<i2").tobytes()


def _ensure_vendor_boot() -> None:
    """vendored 引导（ADR-014）：必须在首次 import cosyvoice 之前完成。

    - sys.path 注入 sidecar 根 + vendor 根（上游 example.py 同款惯例）；
    - torch/lib DLL 注入（torch wheel 自带 cudnn/cublas；缺它 onnxruntime-gpu
      静默回 CPU EP），仅 torch.cuda 可用时需要（CPU 机器无此依赖）。
    """
    global _VENDOR_BOOTED
    if _VENDOR_BOOTED:
        return
    sidecar_root = Path(__file__).resolve().parents[3]
    vendor_root = sidecar_root / "vendor" / "cosyvoice2"
    for p in (str(sidecar_root), str(vendor_root)):
        if p not in sys.path:
            sys.path.insert(0, p)

    import torch

    torch_lib = Path(torch.__file__).parent / "lib"
    if torch.cuda.is_available() and torch_lib.exists():
        os.add_dll_directory(str(torch_lib))
        os.environ["PATH"] = f"{torch_lib}{os.pathsep}{os.environ.get('PATH', '')}"
    _VENDOR_BOOTED = True


def _wetext_cache_dir() -> Path:
    """modelscope 缓存根（MODELSCOPE_CACHE 优先）→ wetext 快照目录。

    布局为 modelscope 1.20 的 {root}/hub/{repo_id}（snapshot_download 内部同式
    拼接）；与运行时间的事实缓存路径一致。
    """
    root = os.environ.get("MODELSCOPE_CACHE") or Path.home() / ".cache" / "modelscope"
    return Path(root) / "hub" / _WETEXT_REPO


def _require_wetext_cache() -> None:
    """wetext fst 本地缓存预校验（缺件 → boot 报错不降级）。

    vendored frontend 的裸 except 会把 Normalizer 构造失败静默吞成
    no-frontend 文本面（正则化无声消失）；报错不降级（3.4.1）必须在进入
    vendored 构造前把缺件截断为显式报错。
    """
    base = _wetext_cache_dir()
    missing = [
        rel for rel in _WETEXT_SNAPSHOT_FILES if not (base / rel).is_file()
    ]
    if missing:
        raise EchoesError(
            ErrorCode.MODEL_NOT_LOADED,
            f"wetext fst 缓存缺失（{base}）: {', '.join(missing)}"
            "（补齐归部署 bootstrap，运行时不联网补救，7.3/离线红线）",
        )


def _install_wetext_offline_snapshot() -> None:
    """把 wetext 的 modelscope 快照下载钉成 local_files_only=True（零网）。

    modelscope 1.20 语义：True ⇒ 零网络、缓存目录非空即返回根路径，不碰
    文件清单 API；联网路径会打印下载并逐文件补拉（今日实证可级联成载入期
    假死）。缓存完整性由 _require_wetext_cache() 前置保证。
    """
    _require_wetext_cache()
    import wetext  # wetext 包本体（构造 Normalizer 才触发下载面）

    snapshot = wetext.wetext.snapshot_download  # wetext 无类型 stub，Any 口

    def _offline(model_id: str, **kwargs: Any) -> Any:
        kwargs["local_files_only"] = True
        return snapshot(model_id, **kwargs)

    wetext.wetext.snapshot_download = _offline


class CosyVoice2TtsEngine(TTSEngine):
    """CosyVoice2 zero-shot 流式合成引擎（lazy 加载；输出 24kHz mono PCM16）。"""

    def __init__(self, *, fp16: bool = True, model_dir: Path | str | None = None) -> None:
        self._fp16 = fp16
        self._model_dir = Path(model_dir) if model_dir is not None else _DEFAULT_MODEL_DIR
        self._engine: Any | None = None  # vendored CosyVoice2（无 stub，Any 口）

    async def warmup(self) -> None:
        """组合根装配期预热（vendored 引导 + 权重加载在线程内，不阻塞 booting 其余装配）。"""
        if self._engine is None:
            await asyncio.to_thread(self._load_engine)

    def _load_engine(self) -> None:
        # 先查权重再引导 vendored：目录缺失时绝不 import（防 vendored 联网回退，
        # 离线红线①；7.3 下载归部署 bootstrap 预取，运行时报错不降级）。
        if not self._model_dir.is_dir():
            raise EchoesError(
                ErrorCode.MODEL_NOT_LOADED,
                f"CosyVoice2 权重不存在: {self._model_dir}"
                "（7.3 下载边界外，部署 bootstrap 预取，运行时不联网补救）",
            )
        _ensure_vendor_boot()
        _install_wetext_offline_snapshot()  # 离线红线②：wetext 快照零网 + 缓存预校验
        import logging
        import warnings

        prev_level = logging.getLogger().getEffectiveLevel()
        logging.getLogger().setLevel(logging.WARNING)
        warnings.filterwarnings("ignore")
        try:
            from cosyvoice.cli.cosyvoice import CosyVoice2  # vendored（无 stub）

            self._engine = CosyVoice2(
                str(self._model_dir),
                load_jit=False,
                load_trt=False,
                load_vllm=False,
                fp16=self._fp16,  # CUDA 缺席时 vendored 内部自动回落 fp32
                trt_concurrent=1,
            )
        finally:
            logging.getLogger().setLevel(prev_level)

    def _resolve_voice(self, voice_id: str) -> tuple[str, Path]:
        """voice_id → zero-shot prompt（prompt_text, prompt_wav）；未知/缺失报错不降级。"""
        if voice_id != BUILTIN_DEFAULT_VOICE:
            raise EchoesError(
                ErrorCode.VOICE_NOT_AVAILABLE,
                f"voice_id {voice_id} 不在本引擎可用音色面"
                "（阶段 0 仅 builtin:default；克隆接线=第三周 §12 步骤 5）",
            )
        prompt_wav: Path = BUILTIN_DEFAULT_PROMPT_WAV  # 模块级查（tests monkeypatch 面）
        if not prompt_wav.is_file():
            raise EchoesError(
                ErrorCode.VOICE_NOT_AVAILABLE,
                f"内置音色 prompt 资产缺失: {prompt_wav}"
                "（scripts/make_builtin_prompt.py 重生成，wav/文本须严格配对）",
            )
        return BUILTIN_DEFAULT_PROMPT_TEXT, prompt_wav

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        """流式合成（4.5）：vendored 同步生成器经线程 + 队列桥接为 async chunk 流。

        - 3.2 执行约束：vendored 迭代是同步长任务，必须离事件循环（worker thread）；
          每段 tts_speech（24k float）→ np_to_pcm16 → AudioChunk；
        - 末段带真实 payload 且 is_final=True；零段产出兜底单帧 b"" 流尾帧；
        - 线程内异常经队列桥回主协程 → EchoesError(TTS_ENGINE_ERROR)，不静默
          （3.4.1）；打断/在途取消归三跳协议（3.4 第四周，阶段 0 turn 同步执行）。
        """
        engine = self._engine
        if engine is None:
            raise EchoesError(
                ErrorCode.MODEL_NOT_LOADED,
                "CosyVoice2 未 warmup 即 synthesize（3.4.1 报错不降级）",
            )
        prompt_text, prompt_wav = self._resolve_voice(voice_id)
        chunks_q: queue.Queue[Any] = queue.Queue()

        def _produce() -> None:
            try:
                for model_output in engine.inference_zero_shot(
                    text, prompt_text, str(prompt_wav), stream=True
                ):
                    speech = model_output["tts_speech"]
                    if hasattr(speech, "detach"):  # torch.Tensor：断梯度 + 归 CPU
                        speech = speech.detach().cpu()
                    chunks_q.put(speech)
            except Exception as exc:  # noqa: BLE001  跨线程异常桥（消费端统一转错误码）
                chunks_q.put(exc)
            finally:
                chunks_q.put(None)  # 流尾哨兵：任何终止路径（含异常）都保证消费端不挂死

        threading.Thread(target=_produce, name="cosyvoice2-synth", daemon=True).start()

        seq = 0
        pending: AudioChunk | None = None  # 缓冲一段：判明流尾后给末段盖 is_final
        while True:
            item = await asyncio.to_thread(chunks_q.get)
            if item is None:
                if pending is None:
                    yield AudioChunk(data=b"", seq=seq, is_final=True)  # 空产出兜底
                    return
                pending.is_final = True
                yield pending
                return
            if isinstance(item, Exception):
                raise EchoesError(
                    ErrorCode.TTS_ENGINE_ERROR, f"CosyVoice2 合成失败: {item}"
                ) from item
            if pending is not None:
                yield pending
            pending = AudioChunk(data=np_to_pcm16(item), seq=seq)
            seq += 1

    async def clone(self, sample: AudioInputStream) -> str:
        """克隆（4.5/ADR-009）：阶段 0 第三周接线（§12 步骤 5）；失败抛 CloneError。"""
        raise NotImplementedError("阶段 0 第三周接线（§12 步骤 5；4.5 契约与 ADR-009）")
