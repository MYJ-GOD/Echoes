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
  组合根置 ready 重发 hello。**未开始 warmup 就合成 = MODEL_NOT_LOADED 报错**；
  已在进行中则**等它装完**（冷启动首轮慢是诚实的，报错让用户「点了却说没就绪」
  才是降级）。真机上窗口在 ~3s 就 ready，权重物化要十几秒，这段窗口正是用户
  最容易点第一句话的时候。
- **音色一律走 spk2info 缓存**（`add_zero_shot_spk`）：vendored 的
  `frontend_zero_shot` 在 `zero_shot_spk_id == ''` 时会**每次调用**重跑一遍
  campplus 嵌入 + speech tokenizer（百毫秒级）。逐句合成要调 N 次，不缓存就是
  N 倍开销，所以内置音色在 warmup 注册一次、克隆音色在 clone 后立刻注册。
  注册只写内存（不调 `save_spkinfo`），理由见 `_register_voices`。
- 4.5 分句接线：`synthesize` 先用 `audio.chunker.split_sentences` 切句再逐句推理
  （长句按次级停顿/硬切拆到 60 字内），首句更早出声；段内 chunk 序号跨句连续。
- 克隆真路（ADR-009 zero-shot）：样本 16k PCM16 → 落 `voices/clone_<hex>.wav`
  （temp+rename，14.2）→ `add_zero_shot_spk` 算嵌入 → 返回 `clone:<hex>`；
  合成走 `inference_cross_lingual`（无人转写文本，正是 cross-lingual 的适用面）。
- RTF 1.33（T-4060 fp16 实测）> 1：连续流式跟播不可行 → 「整句产出按句播」
  消费语义在壳侧；本层保证逐段产出与段尾 is_final 边界。
"""

from __future__ import annotations

import asyncio
import os
import queue
import sys
import tempfile
import threading
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from echoes_sidecar.audio.chunker import split_sentences
from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.errors import CloneError, EchoesError, ErrorCode
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.engines.tts.base import TTSEngine

__all__ = [
    "BUILTIN_DEFAULT_PROMPT_TEXT",
    "BUILTIN_DEFAULT_PROMPT_WAV",
    "BUILTIN_DEFAULT_VOICE",
    "CLONE_VOICE_PREFIX",
    "CosyVoice2TtsEngine",
    "np_to_pcm16",
]

BUILTIN_DEFAULT_VOICE = "builtin:default"  # 2.5 保留 ID（none 态解析目标）
# 克隆音色 ID 前缀：`clone:<hex>`；落盘文件名 = ID 里的 ':' 换成 '_'（5.1/14.2）
CLONE_VOICE_PREFIX = "clone:"

# 与 builtin_default_prompt.wav 严格配对（scripts/make_builtin_prompt.py 唯一来源）
BUILTIN_DEFAULT_PROMPT_TEXT = (
    "你好，我是 Echoes。我住在这台电脑里，全程离线运行，不用联网。今天想聊点什么？我在听。"
)
BUILTIN_DEFAULT_PROMPT_WAV = (
    Path(__file__).resolve().parent / "assets" / "builtin_default_prompt.wav"
)
_DEFAULT_MODEL_DIR = Path.home() / ".cache" / "echoes" / "models" / "CosyVoice2-0.5B"
# 引擎侧面：克隆 prompt 落盘目录（组合根传 assets/voices；与 5.1 相对路径同根）
_DEFAULT_VOICES_DIR = Path.home() / ".cache" / "echoes" / "assets" / "voices"
# 克隆样本口径（与 4.2/3.4 的 PTT/WS 帧一致：16k mono PCM16）
_CLONE_SAMPLE_RATE = 16_000
_SAMPLE_WIDTH = 2
# 首句短切上限（字）：本地 RTF≈1（ADR-012 §4.1 实测：21 字 ≈ 4.2s 音频 ≈ 4.2s 合成），
# 首音频块要等首句合成完，所以「首句多长」直接决定 TTFA。20 字 ≈ 4s 音频，
# 是「常见口语首从句」的长度（实测 16 字会错过 18 字处的逗号，等于没切）；
# 再短就得在没有停顿的地方硬切，韵律会崩——宁可慢，不要机器味。
_FIRST_SEGMENT_MAX_CHARS = 20

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

    def __init__(
        self,
        *,
        fp16: bool = True,
        model_dir: Path | str | None = None,
        voices_dir: Path | str | None = None,
    ) -> None:
        self._fp16 = fp16
        self._model_dir = Path(model_dir) if model_dir is not None else _DEFAULT_MODEL_DIR
        self._voices_dir = (
            Path(voices_dir) if voices_dir is not None else _DEFAULT_VOICES_DIR
        )
        self._engine: Any | None = None  # vendored CosyVoice2（无 stub，Any 口）
        # 已注册进 vendored spk2info 的音色（= 其特征提取已缓存，合成时无需再算）
        self._spk_ids: set[str] = set()
        # R2b 2b.6：本轮风格/情感指令（由编排层每轮设置，合成结束复位）
        self._instruction: str | None = None
        # 分级就绪的闸门：warmup 装完（成功或失败）都置位，_warmup_error 区分结果。
        self._loaded = asyncio.Event()
        self._warmup_started = False
        self._warmup_error: EchoesError | None = None

    async def warmup(self) -> None:
        """组合根装配期预热（vendored 引导 + 权重加载在线程内，不阻塞 booting 其余装配）。"""
        self._warmup_started = True
        try:
            if self._engine is None:
                await asyncio.to_thread(self._load_engine)
        except EchoesError as exc:
            # 让在途等待者立刻醒来拿到真因（权重缺失/引导失败），而不是无限等
            self._warmup_error = exc
            raise
        finally:
            self._loaded.set()

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
        self._register_voices()

    def preload(self) -> None:
        """主线程预载重型 C 依赖（3.2 执行约束细则；Windows loader-lock 死锁规避）。

        R20 实证：非主线程首次初始化 OpenBLAS 家族扩展（numpy/scipy）可在
        LoadLibrary 的 loader lock 下死锁（spawn+PIPE 形态 100% 复现，
        直跑形态不复现）。组合根在首发 hello 后、gate 任务启动前于主线程
        调本方法：完成全部首次 import + CUDA context 建立；warmup 的 worker
        线程只做权重物化（torch.load），不再触发 C 扩展初始化。
        只热 import 面，不加载权重（权重仍归 warmup 分级就绪，3.4 v1.4）；幂等。
        """
        _ensure_vendor_boot()  # torch import + DLL 注入（主线程，幂等）
        import numpy  # noqa: F401  主线程完成 OpenBLAS 初始化
        import scipy  # noqa: F401  scipy 自带 OpenBLAS 副本，同风险面
        import torch
        import wetext  # noqa: F401  vendored frontend 文本面（kaldifst）
        from cosyvoice.cli.cosyvoice import CosyVoice2  # noqa: F401  vendored 全链

        if torch.cuda.is_available():
            torch.zeros(1, device="cuda")  # 建 CUDA context（worker 只复用不初始化）

    async def _ensure_engine(self, action: str) -> Any:
        """分级就绪闸门：等 warmup 装完再交给调用方（3.4 v1.4）。

        - 从未 warmup（单测直连 / 装配被跳过）→ MODEL_NOT_LOADED，不替调用方偷偷加载；
        - warmup 在途 → `await` 到底：冷启动首轮把「权重物化」算进 TTFA，比回一个
          「引擎未就绪」错误诚实（用户已看到 ready）；
        - warmup 失败 → 抛当时那次失败的真因（权重缺失优于笼统的「未就绪」）。
        """
        if self._engine is not None:
            return self._engine
        if not self._warmup_started:
            raise EchoesError(
                ErrorCode.MODEL_NOT_LOADED,
                f"CosyVoice2 未 warmup 即 {action}（3.4.1 报错不降级）",
            )
        await self._loaded.wait()
        if self._warmup_error is not None:
            raise self._warmup_error
        if self._engine is None:  # 防御：warmup 正常返回却没引擎
            raise EchoesError(
                ErrorCode.MODEL_NOT_LOADED,
                f"CosyVoice2 warmup 结束但引擎缺失（{action}，3.4.1 报错不降级）",
            )
        return self._engine

    # ------------------------------ 音色注册 ------------------------------

    def _register_voices(self) -> None:
        """把内置音色与既有克隆音色注册成 spk2info 条目（特征提取只做一次）。

        为什么不 `save_spkinfo()`：它写的是 `{model_dir}/spk2info.pt`——权重目录属
        7.3 的「下载边界」，运行时往里写会让「权重完好」与「嵌embedding 完好」两件事
        混在一起。本引擎的权威来源是 `voices/*.wav`：启动时按文件重建嵌入（
        每音色十几~几十毫秒，音色数是个位数），权重目录被重下也不会让音色静默失效。

        内置音色注册失败 → 直接抛（TTS 本就不可用）；单个克隆失败 → 记 stderr 并
        跳过，只有点它的会话会拿到 VOICE_NOT_AVAILABLE（不牵连其它音色）。
        """
        if BUILTIN_DEFAULT_PROMPT_WAV.is_file():
            self._add_spk(
                BUILTIN_DEFAULT_VOICE, BUILTIN_DEFAULT_PROMPT_TEXT, BUILTIN_DEFAULT_PROMPT_WAV
            )
        for wav in sorted(self._voices_dir.glob("clone_*.wav")):
            voice_id = f"{CLONE_VOICE_PREFIX}{wav.stem.removeprefix('clone_')}"
            try:
                self._add_spk(voice_id, "", wav)
            except EchoesError as exc:
                print(
                    f"[sidecar] 克隆音色 {voice_id} 嵌入重建失败，跳过（{exc.code}）: "
                    f"{exc.message}",
                    file=sys.stderr,
                )

    def _add_spk(self, voice_id: str, prompt_text: str, prompt_wav: Path) -> None:
        """算一次音色嵌入并缓存（vendored 同步重活，调用方负责离事件循环）。"""
        engine = self._engine
        if engine is None:  # 防御：注册只在 _load_engine 末尾或 warmup 之后发生
            raise EchoesError(ErrorCode.MODEL_NOT_LOADED, "引擎未加载即注册音色")
        try:
            engine.add_zero_shot_spk(prompt_text, str(prompt_wav), voice_id)
        except Exception as exc:  # noqa: BLE001  vendored 无类型，异常统一转引擎错误
            raise EchoesError(
                ErrorCode.TTS_ENGINE_ERROR, f"音色 {voice_id} 嵌入提取失败: {exc}"
            ) from exc
        self._spk_ids.add(voice_id)

    def _resolve_voice(self, voice_id: str) -> _Voice:
        """voice_id → 合成参数；未知/缺失报错不降级（2.5/3.4.1）。

        - `builtin:default`：prompt 文本与 wav 严格配对（同一脚本生成），零-shot 路；
        - `clone:<hex>`：只有 prompt wav，没有对应转写文本 → cross-lingual 路
          （vendored `inference_cross_lingual`，无需 prompt_text）。
        """
        if voice_id == BUILTIN_DEFAULT_VOICE:
            prompt_wav: Path = BUILTIN_DEFAULT_PROMPT_WAV  # 模块级查（tests monkeypatch 面）
            if not prompt_wav.is_file():
                raise EchoesError(
                    ErrorCode.VOICE_NOT_AVAILABLE,
                    f"内置音色 prompt 资产缺失: {prompt_wav}"
                    "（scripts/make_builtin_prompt.py 重生成，wav/文本须严格配对）",
                )
            return _Voice(
                prompt_text=BUILTIN_DEFAULT_PROMPT_TEXT,
                prompt_wav=prompt_wav,
                spk_id=voice_id if voice_id in self._spk_ids else "",
            )

        if voice_id.startswith(CLONE_VOICE_PREFIX):
            wav = self._voices_dir / f"{_safe(voice_id)}.wav"
            if not wav.is_file():
                raise EchoesError(
                    ErrorCode.VOICE_NOT_AVAILABLE,
                    f"克隆音色样本缺失: {wav}（音色资产被删？请重新克隆）",
                )
            if voice_id not in self._spk_ids:
                raise EchoesError(
                    ErrorCode.VOICE_NOT_AVAILABLE,
                    f"克隆音色 {voice_id} 的嵌入未就绪（见启动日志的嵌入重建失败行）",
                )
            return _Voice(
                prompt_text="", prompt_wav=wav, spk_id=voice_id, cross_lingual=True
            )

        raise EchoesError(
            ErrorCode.VOICE_NOT_AVAILABLE,
            f"voice_id {voice_id} 不在本引擎可用音色面"
            f"（{BUILTIN_DEFAULT_VOICE} 或 {CLONE_VOICE_PREFIX}<hex>）",
        )

    # ------------------------------ 合成 ------------------------------

    @property
    def supports_instruction(self) -> bool:
        """R2b 2b.6：CosyVoice2 支持 instruct2（情感/风格）合成。"""
        return True

    def set_instruction(self, text: str | None) -> None:
        """编排层每轮设置情绪指令；None = 复位默认语气。"""
        self._instruction = (text or "").strip() or None

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        """流式合成（4.5）：分句 → 逐句推理 → vendored 同步生成器经线程/队列桥接。

        - 4.5 分句接线：`split_sentences` 切句后逐句推理，首句更早出音；chunk 序号
          跨句连续；
        - **流尾 = 零长度 is_final 帧**（协议既有形态：PTT 松手同样用它收束）。
          真 chunk 一律**产出即发**，不为了给末段盖 is_final 而扣住——扣一下等于
          把首音频推迟到下一个 chunk 到达（ADR-012 §4.1 实测：首段 3.2s 就好，
          TTFA 却被算成 7.7s）；
        - 3.2 执行约束：vendored 迭代是同步长任务，必须离事件循环（worker thread）；
          每段 tts_speech（24k float）→ np_to_pcm16 → AudioChunk；
        - 线程内异常经队列桥回主协程 → EchoesError(TTS_ENGINE_ERROR)，不静默
          （3.4.1）；打断/在途取消由编排层 `pull()` 收束（3.4 三跳）。
        """
        engine = await self._ensure_engine("synthesize")
        voice = self._resolve_voice(voice_id)
        segments = split_sentences(text, first_max_chars=_FIRST_SEGMENT_MAX_CHARS)
        if not segments:
            yield AudioChunk(data=b"", seq=0, is_final=True)  # 空文本：流尾兜底
            return

        chunks_q: queue.Queue[Any] = queue.Queue()
        instruction = self._instruction
        instruct_fn = getattr(engine, "inference_instruct2", None)
        if instruction and not callable(instruct_fn):
            print(
                "[sidecar] 当前 CosyVoice2 vendored 版本不支持 instruct2，本轮忽略风格指令",
                file=sys.stderr,
            )

        def _produce() -> None:
            try:
                for segment in segments:
                    if instruction and callable(instruct_fn):
                        # R2b 2b.6：instruct2 用 prompt wav + 自然语言指令控制语气
                        stream = instruct_fn(
                            segment,
                            instruction,
                            str(voice.prompt_wav),
                            voice.spk_id,
                            stream=True,
                        )
                    elif voice.cross_lingual:
                        stream = engine.inference_cross_lingual(
                            segment, str(voice.prompt_wav), voice.spk_id, stream=True
                        )
                    elif voice.spk_id:
                        stream = engine.inference_zero_shot(
                            segment, "", "", voice.spk_id, stream=True
                        )
                    else:  # 未注册：内联重算 prompt 特征（等价结果，只是慢）
                        stream = engine.inference_zero_shot(
                            segment, voice.prompt_text, str(voice.prompt_wav), stream=True
                        )
                    for model_output in stream:
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
        while True:
            item = await asyncio.to_thread(chunks_q.get)
            if item is None:
                # 流尾锚点：零长度 is_final 帧（协议既有形态，PTT 松手同款）。
                # 不能用「扣住最后一个真 chunk 再盖 is_final」的写法——那会把**首**
                # 音频块推迟到下个 chunk 到达（ADR-012 §4.1 实测 TTFA 7.7s→
                # 首段其实 3.2s 就好了）。壳侧 push_pcm16 对空样本直接 return。
                yield AudioChunk(data=b"", seq=seq, is_final=True)
                return
            if isinstance(item, Exception):
                raise EchoesError(
                    ErrorCode.TTS_ENGINE_ERROR, f"CosyVoice2 合成失败: {item}"
                ) from item
            yield AudioChunk(data=np_to_pcm16(item), seq=seq)
            seq += 1

    async def clone(self, sample: AudioInputStream) -> str:
        """克隆（4.5/ADR-009 zero-shot 真路）：样本 → prompt wav → 嵌入 → voice_id。

        三步（ADR-009 第二周 spike 清单 1 的工程化落地）：
        1. 收整段 16k PCM16 样本（4.2 输入流 → bytes；空样本报错不降级）；
        2. 落 `voices/clone_<hex>.wav`（temp+rename，14.2：半个样本绝不对外可见）；
        3. `add_zero_shot_spk` 算一次嵌入并缓存在 spk2info（合成时零重复提取）。

        为什么不 `save_spkinfo()`：见 `_register_voices`——嵌入的权威来源是
        `voices/*.wav`，启动时按文件重建；权重目录保持只读（7.3 下载边界）。

        走 cross-lingual 合成：用户样本没有对应转写文本，`inference_zero_shot`
        要求 prompt 文本与 prompt wav 严格配对，硬填会让韵律跑偏。
        """
        await self._ensure_engine("clone")
        pcm = await _drain_pcm(sample)
        if not pcm:
            raise CloneError(ErrorCode.CLONE_ENGINE_FAILED, "克隆样本为空（引擎侧收到 0 字节）")

        voice_id = f"{CLONE_VOICE_PREFIX}{uuid4().hex}"
        wav = await asyncio.to_thread(self._write_clone_wav, voice_id, pcm)
        try:
            await asyncio.to_thread(self._add_spk, voice_id, "", wav)
        except EchoesError as exc:
            # 嵌入失败则该音色无意义：把 prompt wav 一起清掉（14.1 不留孤儿资产）
            wav.unlink(missing_ok=True)
            raise CloneError(
                ErrorCode.CLONE_ENGINE_FAILED, f"克隆嵌入提取失败：{exc.message}"
            ) from exc
        return voice_id

    @property
    def supports_similarity_check(self) -> bool:
        """4.5 v1.4.4 可选能力：CosyVoice2 有 campplus，能做说话人相似度质检。"""
        return True

    async def speaker_similarity(self, sample_pcm: bytes, synth_pcm: bytes) -> float:
        """阶段 2 质检：原样本 vs 克隆音色合成音频的 campplus 余弦（0–1）。

        TTS 输出是 24k，campplus 要 16k；2/3 重采样后写临时 WAV 再提嵌入。
        能力位见 `supports_similarity_check`（4.5 v1.4.4：质检是显式可选能力，
        编排层按能力位调用，不再用 getattr 探测）。
        """
        engine = await self._ensure_engine("speaker_similarity")
        frontend = getattr(engine, "frontend", None)
        extract = getattr(frontend, "_extract_spk_embedding", None)
        if extract is None:
            raise EchoesError(ErrorCode.TTS_ENGINE_ERROR, "CosyVoice2 前端缺少说话人嵌入")
        if not sample_pcm or not synth_pcm:
            raise EchoesError(ErrorCode.TTS_ENGINE_ERROR, "质检音频为空")
        return await asyncio.to_thread(
            self._similarity_sync, extract, sample_pcm, synth_pcm
        )

    def _similarity_sync(self, extract: Any, sample_pcm: bytes, synth_pcm: bytes) -> float:
        import numpy as np
        import torch
        from scipy.signal import resample_poly

        def _write_wav(path: Path, pcm: bytes) -> None:
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(_SAMPLE_WIDTH)
                handle.setframerate(_CLONE_SAMPLE_RATE)
                handle.writeframes(pcm[: len(pcm) - (len(pcm) % _SAMPLE_WIDTH)])

        synth = np.frombuffer(synth_pcm, dtype="<i2").astype(np.float32)
        synth16 = resample_poly(synth, 2, 3)  # 24k -> 16k（2/3）
        synth16_pcm = np.clip(synth16, -32768, 32767).astype("<i2").tobytes()

        with tempfile.TemporaryDirectory() as tmp:
            sample_wav = Path(tmp) / "sample.wav"
            synth_wav = Path(tmp) / "synth.wav"
            _write_wav(sample_wav, sample_pcm)
            _write_wav(synth_wav, synth16_pcm)
            emb_sample = extract(str(sample_wav))
            emb_synth = extract(str(synth_wav))
            score = torch.nn.functional.cosine_similarity(
                emb_sample, emb_synth, dim=1
            ).item()
        return float(max(-1.0, min(1.0, score)))

    def _write_clone_wav(self, voice_id: str, pcm: bytes) -> Path:
        """样本落盘（temp+rename）：文件名 = voice_id 的 ':' → '_'（5.1 相对路径）。"""
        target = self._voices_dir / f"{_safe(voice_id)}.wav"
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.tmp")
        try:
            with wave.open(str(tmp), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(_SAMPLE_WIDTH)
                handle.setframerate(_CLONE_SAMPLE_RATE)
                handle.writeframes(pcm[: len(pcm) - (len(pcm) % _SAMPLE_WIDTH)])
            os.replace(tmp, target)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            raise CloneError(
                ErrorCode.CLONE_ENGINE_FAILED, f"克隆样本写盘失败：{target}（{exc}）"
            ) from exc
        return target


@dataclass(frozen=True)
class _Voice:
    """合成所需的音色解析结果（引擎内部用；`spk_id` 为空 = 内联重算 prompt 特征）。"""

    prompt_text: str
    prompt_wav: Path
    spk_id: str
    cross_lingual: bool = False


def _safe(voice_id: str) -> str:
    """voice_id → 文件名安全形态（`clone:<hex>` → `clone_<hex>`，5.1/14.2）。"""
    return voice_id.replace(":", "_")


async def _drain_pcm(sample: AudioInputStream) -> bytes:
    """整段 PCM16 收齐（4.2 输入流可能是任意分片；克隆只要一段完整样本）。"""
    parts: list[bytes] = []
    async for chunk in sample:
        if chunk.data:
            parts.append(chunk.data)
    return b"".join(parts)
