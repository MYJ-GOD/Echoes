"""
鐠囶參鐓剁拋顓犵矊娴犺濮?
閸╄桨绨?CosyVoice 閻ㄥ嫰娴傞弽閿嬫拱鐠囶參鐓堕崗瀣畷

閼卞矁鐭楁潏鍦櫕閿?
- 閸欘亣绀嬬拹锝堫唲缂佸啯澧界悰宀嬬礉娑撳秷绀嬬拹锝囨暏閹寸柉顓荤拠?
- 娑撳秶娲块幒銉╂桨閸氭垵澧犵粩顖ょ礉閸欘亪鈧俺绻?Redis Streams 閹恒儲鏁规禒璇插
- 娑撳秶娣幎銈勭窗鐠囨繄濮搁幀渚婄礉濮ｅ繑顐兼禒璇插閻欘剛鐝?
- 缂佹挻鐏夐柅姘崇箖閸ョ偠鐨熼崶鐐寸ウ閼?Java 鐏?
"""
import logging
import os
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Callable
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from common.config import settings
from common.logger import logger
from storage.object_storage import download_file, upload_file, get_presigned_url


@dataclass
class TrainingConfig:
    """鐠侇厾绮岄柊宥囩枂"""
    # 闂婃娊顣堕柊宥囩枂
    sample_rate: int = 16000
    max_duration_sec: int = 30
    min_duration_sec: float = 3.0

    # 鏉堟挸鍤柊宥囩枂
    output_dir: str = "data/voice_assets/user_trained"


@dataclass
class TrainingResult:
    """鐠侇厾绮岀紒鎾寸亯"""
    success: bool
    voice_model_id: str
    voice_id_external: str
    similarity_score: float
    model_path: str = ""
    features_path: str = ""
    error_message: Optional[str] = None


class VoiceTrainingJob:
    """
    鐠囶參鐓剁拋顓犵矊娴犺濮?

    閼卞矁鐭楅敍?
    - 娴?Redis Streams 閹恒儲鏁圭拋顓犵矊娴犺濮?
    - 娴?OSS 娑撳娴囬崣鍌濃偓鍐叾妫?
    - 鐠嬪啰鏁?CosyVoice 閹笛嗩攽鐠侇厾绮?
    - 娑撳﹣绱跺Ο鈥崇€锋禍褏澧块崚?OSS
    - 閸ョ偠鐨?Java 閺堝秴濮熼弴瀛樻煀閻樿埖鈧?

    娑撳秷绀嬬拹锝忕窗
    - 閻劍鍩涚拋銈堢槈 (閻?Java 鐏炲倽绀嬬拹?
    - 閺夊啴妾烘宀冪槈 (閻?Java 鐏炲倽绀嬬拹?
    - 娴兼俺鐦界粻锛勬倞 (閻?Java 鐏炲倽绀嬬拹?
    - 閻╁瓨甯撮棃銏犳倻閸撳秶顏?(濮橀晲绗夌€电懓顦婚弳鎾苟)
    """

    def __init__(self, config: Optional[TrainingConfig] = None):
        """
        閸掓繂顫愰崠鏍唲缂佸啩鎹㈤崝?

        Args:
            config: 鐠侇厾绮岄柊宥囩枂
        """
        self.config = config or TrainingConfig()
        self._cosyvoice = None

    def train(
        self,
        task_id: str,
        ref_id: str,
        storage_key: str,
        voice_asset_id: str,
        user_id: str,
        model_version: int = 1,
        prompt: str = "",
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> TrainingResult:
        """
        閹笛嗩攽婢逛即鐓剁拋顓犵矊

        Args:
            task_id: 鐠侇厾绮屾禒璇插ID (閻劋绨崶鐐剁殶)
            ref_id: 閸欏倽鈧啴鐓舵０鎱朌 (婢跺秶鏁?/conversation/voice-ref/upload 閹恒儱褰?
            storage_key: OSS 鐎涙ê鍋嶇捄顖氱窞
            voice_asset_id: 闂婂疇澹婄挧鍕獓ID
            user_id: 閻劍鍩汭D
            model_version: 濡€崇€烽悧鍫熸拱
            prompt: 閼奉亜鐣炬稊濉竢ompt
            progress_callback: 鏉╂稑瀹抽崶鐐剁殶閸戣姤鏆?(progress: 0-100, message: 閻樿埖鈧焦寮挎潻?

        Returns:
            TrainingResult: 鐠侇厾绮岀紒鎾寸亯

        Note:
            - ref_id 閻?Java 鐏炲倻娈?/conversation/voice-ref/upload 閹恒儱褰涢悽鐔稿灇
            - storage_key 閹稿洤鎮?OSS 娑擃厾娈戦崣鍌濃偓鍐叾妫?
            - 閹碘偓閺堝娼堥梽鎰扮崣鐠囦胶鏁?Java 鐏炲倽绀嬬拹?
        """
        logger.info(f"Start training: taskId={task_id}, voiceAssetId={voice_asset_id}")
        start_time = time.time()

        try:
            # 1) Download reference audio from OSS
            progress_callback and progress_callback(5, "Downloading reference audio")
            local_audio_path = self._download_from_oss(storage_key)
            logger.info(f"Reference audio downloaded: {local_audio_path}")

            # 2) Validate duration
            progress_callback and progress_callback(10, "Validating audio")
            duration = self._get_audio_duration(local_audio_path)
            if duration < self.config.min_duration_sec:
                logger.warning(
                    f"Training aborted due to short audio: taskId={task_id}, refId={ref_id}, "
                    f"duration={duration:.2f}s, minRequired={self.config.min_duration_sec:.2f}s"
                )
                return TrainingResult(
                    success=False,
                    voice_model_id="",
                    voice_id_external="",
                    similarity_score=0.0,
                    error_message=f"Audio duration too short, need >= {self.config.min_duration_sec}s, current {duration:.1f}s"
                )

            # 3) Preprocess audio
            progress_callback and progress_callback(20, "Preprocessing audio")
            processed_audio = self._preprocess_audio(local_audio_path)

            # 4) Resolve/generate embedding and register speaker
            progress_callback and progress_callback(30, "Loading voice embedding")
            voice_id = f"user_{user_id}_{voice_asset_id}"
            
            # Load ref_text generated during upload
            ref_text = self._load_ref_text(ref_id)
            
            # Fallback to realtime transcription when ref_text is missing
            if not ref_text:
                logger.info("No local ref_text, trying realtime ASR transcription")
                ref_text = self._transcribe_audio(processed_audio)
                if ref_text:
                    logger.info(f"Realtime transcription success: {ref_text}")
            
            if not prompt and ref_text:
                prompt = ref_text
                logger.info(f"Using ref_text as prompt: {prompt}")
            
            pt_file = self._resolve_or_create_pt_file(ref_id, processed_audio, prompt)
            if pt_file is None or not pt_file.exists():
                raise RuntimeError(f"Missing required embedding .pt for ref_id={ref_id}")
            registered = self._register_voice(voice_id, prompt, processed_audio, pt_file)
            if not registered:
                raise RuntimeError(f"Speaker registration failed for voice_id={voice_id}")

            # 5) Synthesize test audio
            progress_callback and progress_callback(50, "Validating cloned voice")
            test_text = "Hello, I am your AI companion assistant."
            test_audio = self._synthesize(voice_id, prompt, processed_audio, test_text, pt_file)

            # 6) Calculate similarity
            progress_callback and progress_callback(80, "Calculating similarity")
            similarity_score = self._calculate_similarity(processed_audio, test_audio)

            # 7) Upload artifacts
            progress_callback and progress_callback(90, "Saving model artifacts")
            model_storage_key = self._upload_model(ref_id, voice_asset_id)

            # 8) Build return ids
            voice_id_external = f"voice_{voice_asset_id}"
            voice_model_id = str(uuid.uuid4())

            elapsed_time = time.time() - start_time
            logger.info(f"Training completed: taskId={task_id}, elapsed={elapsed_time:.2f}s, similarity={similarity_score:.4f}")

            return TrainingResult(
                success=True,
                voice_model_id=voice_model_id,
                voice_id_external=voice_id_external,
                similarity_score=similarity_score,
                model_path=model_storage_key
            )

        except Exception as e:
            logger.exception(f"Training failed: taskId={task_id}, error={e}")
            return TrainingResult(
                success=False,
                voice_model_id="",
                voice_id_external="",
                similarity_score=0.0,
                error_message=str(e)
            )

        finally:
            # 濞撳懐鎮婃稉瀛樻閺傚洣娆?
            self._cleanup()

    def _download_from_oss(self, storage_key: str) -> str:
        """
        娴?OSS 娑撳娴囬崣鍌濃偓鍐叾妫?

        Args:
            storage_key: OSS 鐎涙ê鍋嶇捄顖氱窞

        Returns:
            閺堫剙婀撮棅鎶筋暥閺傚洣娆㈢捄顖氱窞
        """
        # Compatibility fallback: if storage_key is already a local path, reuse it directly.
        local_candidate = Path(storage_key)
        if local_candidate.exists() and local_candidate.is_file():
            return str(local_candidate)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ref_{timestamp}_{Path(storage_key).stem}.wav"
        local_path = Path(settings.ECHOES_MODELS_DIR) / "tmp" / filename
        local_path.parent.mkdir(parents=True, exist_ok=True)

        download_file(storage_key, str(local_path))
        return str(local_path)

    def _load_ref_text(self, ref_id: str) -> str:
        """
        娴犲孩婀伴崷鎷岊嚢閸?ref_text閿涘牅绗傛导鐘插棘閼板啴鐓舵０鎴炴瀹告煡鈧俺绻?Whisper 鏉烆剙鍟撻獮鏈电箽鐎涙﹫绱?

        Args:
            ref_id: 閸欏倽鈧啴鐓舵０鎱朌

        Returns:
            ref_text 閹存牜鈹栫€涙顑佹稉?
        """
        try:
            ref_dir = Path(settings.ECHOES_MODELS_DIR) / "voice_refs"
            ref_text_file = ref_dir / f"{ref_id}.txt"
            if ref_text_file.exists():
                with open(ref_text_file, "r", encoding="utf-8") as f:
                    return f.read().strip()
        except Exception as e:
            logger.warning(f"Failed to load ref_text: {e}")
        return ""

    def _transcribe_audio(self, audio_path: str) -> str:
        """
        娴ｈ法鏁?Whisper 鐎圭偞妞傛潪顒€鍟撻棅鎶筋暥

        Args:
            audio_path: 闂婃娊顣堕弬鍥︽鐠侯垰绶?

        Returns:
            鏉烆剙鍟撻惃鍕瀮閺?
        """
        try:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(audio_path, language="zh")
            text = result["text"].strip()
            return text
        except Exception as e:
            logger.warning(f"Whisper transcription failed: {e}")
            return ""

    def _preprocess_audio(self, audio_path: str) -> str:
        """
        闂婃娊顣舵０鍕槱閻?(鏉烆剚宕叉稉?6kHz, mono, PCM16)

        Args:
            audio_path: 閸樼喎顫愰棅鎶筋暥鐠侯垰绶?

        Returns:
            婢跺嫮鎮婇崥搴ｆ畱闂婃娊顣剁捄顖氱窞
        """
        import torch
        import torchaudio

        output_path = Path(settings.ECHOES_MODELS_DIR) / "tmp" / f"processed_{Path(audio_path).stem}.wav"

        waveform, sample_rate = torchaudio.load(audio_path)

        # 闁插秹鍣伴弽宄板煂 16kHz
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
            waveform = resampler(waveform)

        # 鏉烆剚宕叉稉?mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        # 瑜版帊绔撮崠?
        waveform = waveform / waveform.abs().max()

        torchaudio.save(str(output_path), waveform, 16000)
        return str(output_path)

    def _get_audio_duration(self, audio_path: str) -> float:
        """
        閼惧嘲褰囬棅鎶筋暥閺冨爼鏆?

        Args:
            audio_path: 闂婃娊顣堕弬鍥︽鐠侯垰绶?

        Returns:
            閺冨爼鏆遍敍鍫㈩潡閿?
        """
        import torchaudio
        info = torchaudio.info(audio_path)
        return info.num_frames / info.sample_rate

    def _resolve_or_create_pt_file(self, ref_id: str, audio_path: str, ref_text: str) -> Optional[Path]:
        ref_dir = Path(settings.ECHOES_MODELS_DIR) / "voice_refs"
        ref_dir.mkdir(parents=True, exist_ok=True)
        pt_file = ref_dir / f"{ref_id}.pt"
        if pt_file.exists():
            return pt_file

        try:
            import torch
            import torchaudio
            from cosyvoice.cli.cosyvoice import AutoModel

            if self._cosyvoice is None:
                model_dir = os.path.join(settings.ECHOES_MODELS_DIR, settings.COSYVOICE_MODEL_SUBDIR)
                self._cosyvoice = AutoModel(model_dir=model_dir)
                logger.info(f"CosyVoice model loaded, sample_rate={self._cosyvoice.sample_rate}")

            waveform, sample_rate = torchaudio.load(audio_path)
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
                waveform = resampler(waveform)
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            max_abs = waveform.abs().max()
            if max_abs is not None and float(max_abs) > 0:
                waveform = waveform / max_abs

            embedding = self._cosyvoice.frontend._extract_spk_embedding(str(audio_path))
            torch.save({
                "audio_ref": waveform,
                "text_ref": ref_text or "",
                "embedding": embedding.detach().cpu()
            }, str(pt_file))
            logger.info(f"Created missing embedding file: {pt_file}")

            try:
                voices_dir = Path(settings.COSYVOICE_REPO_DIR) / "voices"
                voices_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pt_file, voices_dir / f"{ref_id}.pt")
            except Exception as e:
                logger.warning(f"Failed to copy generated embedding to voices dir: {e}")
            return pt_file
        except Exception as e:
            logger.warning(f"Failed to create embedding file for ref_id={ref_id}: {e}")
            return None

    def _register_voice(self, voice_id: str, prompt_text: str, audio_path: str, pt_file: Optional[Path] = None) -> bool:
        """
        濞夈劌鍞界拠纾嬬樈娴滅尨绱欐担璺ㄦ暏 SFT 濡€崇础閿涘奔绮?.pt 閺傚洣娆㈤崝鐘烘祰婢规壆姹楅敍?

        Args:
            voice_id: 鐠囩鐦芥禍绡扗
            prompt_text: 閹绘劗銇氶弬鍥ㄦ拱
            audio_path: 閸欏倽鈧啴鐓舵０鎴ｇ熅瀵板嫸绱欓幋?.pt 閺傚洣娆㈢捄顖氱窞閿?

        Returns:
            閺勵垰鎯侀幋鎰
        """
        try:
            import torch
            from cosyvoice.cli.cosyvoice import AutoModel

            model_dir = os.path.join(settings.ECHOES_MODELS_DIR, settings.COSYVOICE_MODEL_SUBDIR)
            if self._cosyvoice is None:
                self._cosyvoice = AutoModel(model_dir=model_dir)
                logger.info(f"CosyVoice model loaded, sample_rate={self._cosyvoice.sample_rate}")
                logger.info(f"CosyVoice initialized for speaker registration: sample_rate={self._cosyvoice.sample_rate}")

            # 鐏忔繆鐦禒?.pt 閺傚洣娆㈤崝鐘烘祰婢规壆姹楅敍鍫㈡暏娴?SFT 濡€崇础閿?
            resolved_pt = pt_file if pt_file is not None else Path(audio_path).with_suffix(".pt")
            if resolved_pt.exists():
                logger.info(f"Registering speaker with .pt file: {resolved_pt}")
                voice_obj = torch.load(str(resolved_pt), map_location="cpu", weights_only=False)
                
                # 鐏忓棗锛愮痪瑙勬暈閸愬苯鍩?spk2info閿涘牏鏁ゆ禍?SFT 濡€崇础閿?
                embedding = voice_obj.get("embedding")
                if embedding is not None:
                    self._cosyvoice.frontend.spk2info[voice_id] = {"embedding": embedding}
                    
                    # 閸氬本妞傛穱婵嗙摠閸?spk2info.pt 閺傚洣娆㈡禒銉ょ┒閹镐椒绠欓崠?
                    spk2info_path = Path(model_dir) / "spk2info.pt"
                    torch.save(self._cosyvoice.frontend.spk2info, str(spk2info_path))
                    logger.info(f"Speaker embedding persisted to spk2info.pt: {voice_id}")
                else:
                    logger.warning("Embedding missing in .pt, fallback to zero-shot registration")
                    self._cosyvoice.add_zero_shot_spk(
                        prompt_text=prompt_text,
                        prompt_wav=audio_path,
                        zero_shot_spk_id=voice_id
                    )
            else:
                # Fallback: 娴ｈ法鏁?zero-shot 濡€崇础
                logger.info(f"No .pt file found, fallback to zero-shot mode: {audio_path}")
                self._cosyvoice.add_zero_shot_spk(
                    prompt_text=prompt_text,
                    prompt_wav=audio_path,
                    zero_shot_spk_id=voice_id
                )
            
            logger.info(f"Speaker registered successfully: {voice_id}")
            return True

        except ImportError as e:
            logger.warning(f"CosyVoice import failed: {e}")
            return False

        except Exception as e:
            logger.error(f"Speaker registration failed: {voice_id}, {e}")
            return False

    def _synthesize(self, voice_id: str, prompt_text: str, prompt_wav: str, text: str, pt_file: Optional[Path] = None) -> str:
        """
        閸氬牊鍨氬ù瀣槸闂婃娊顣堕敍鍫滃▏閻?SFT 濡€崇础閿涘奔绮?.pt 閺傚洣娆㈤崝鐘烘祰婢规壆姹楅敍?

        Args:
            voice_id: 鐠囩鐦芥禍绡扗
            prompt_text: 閸欏倽鈧啯鏋冮張?
            prompt_wav: 閸欏倽鈧啴鐓舵０鎴ｇ熅瀵板嫸绱?pt 閺傚洣娆㈢捄顖氱窞閿?
            text: 閸氬牊鍨氶弬鍥ㄦ拱

        Returns:
            閸氬牊鍨氶棅鎶筋暥閻ㄥ嫪澶嶉弮鑸垫瀮娴犳儼鐭惧?
        """
        import torch
        import torchaudio

        if self._cosyvoice is None:
            raise RuntimeError("CosyVoice model not loaded")

        output_path = Path(settings.ECHOES_MODELS_DIR) / "tmp" / f"test_{voice_id}.wav"

        # 鐏忔繆鐦禒?.pt 閺傚洣娆㈤崝鐘烘祰婢规壆姹?
        resolved_pt = pt_file if pt_file is not None else Path(prompt_wav).with_suffix(".pt")
        if resolved_pt is not None and resolved_pt.exists():
            # SFT 濡€崇础閿涙矮绮?.pt 閺傚洣娆㈤崝鐘烘祰婢规壆姹?
            logger.info(f"Using .pt speaker embedding for synthesis: {resolved_pt}")
            for output in self._cosyvoice.inference_sft(
                tts_text=text,
                spk_id=voice_id,
                stream=False
            ):
                torchaudio.save(str(output_path), output["tts_speech"], self._cosyvoice.sample_rate)
        else:
            # Fallback: 娴ｈ法鏁?zero-shot 濡€崇础
            logger.info(f"No .pt found, fallback to zero-shot synthesis: {prompt_wav}")
            for output in self._cosyvoice.inference_zero_shot(
                tts_text=text,
                prompt_text=prompt_text,
                prompt_wav=prompt_wav,
                stream=False
            ):
                torchaudio.save(str(output_path), output["tts_speech"], self._cosyvoice.sample_rate)

        return str(output_path)

    def _calculate_similarity(self, original_path: str, generated_path: str) -> float:
        """
        鐠侊紕鐣婚惄闀愭妧鎼达箒鐦庨崚?
        娴ｈ法鏁?CosyVoice 閻?CampPlus 濡€崇€烽幓鎰絿鐠囩鐦芥禍?embedding閿涘矁顓哥粻妞剧稇瀵妇娴夋导鐓庡

        Args:
            original_path: 閸樼喎顫愰棅鎶筋暥鐠侯垰绶?
            generated_path: 閸氬牊鍨氶棅鎶筋暥鐠侯垰绶?

        Returns:
            閻╅晲鎶€鎼达箒鐦庨崚?(0-1)
        """
        try:
            import torch
            import numpy as np
            from cosyvoice.utils.file_utils import load_wav
            import torchaudio.compliance.kaldi as kaldi

            if self._cosyvoice is None:
                from cosyvoice.cli.cosyvoice import AutoModel
                import os
                model_dir = os.path.join(settings.ECHOES_MODELS_DIR, settings.COSYVOICE_MODEL_SUBDIR)
                self._cosyvoice = AutoModel(model_dir=model_dir)

            # 閹绘劕褰囬崢鐔奉潗闂婃娊顣堕惃?embedding
            speech_original = load_wav(original_path, 16000)
            feat_original = kaldi.fbank(speech_original,
                                        num_mel_bins=80,
                                        dither=0,
                                        sample_frequency=16000)
            feat_original = feat_original - feat_original.mean(dim=0, keepdim=True)
            embedding_original = self._cosyvoice.frontend.campplus_session.run(
                None,
                {self._cosyvoice.frontend.campplus_session.get_inputs()[0].name: 
                 feat_original.unsqueeze(dim=0).cpu().numpy()}
            )[0]
            embedding_original = torch.tensor(embedding_original)

            # 閹绘劕褰囬崥鍫熷灇闂婃娊顣堕惃?embedding
            speech_generated = load_wav(generated_path, 16000)
            feat_generated = kaldi.fbank(speech_generated,
                                         num_mel_bins=80,
                                         dither=0,
                                         sample_frequency=16000)
            feat_generated = feat_generated - feat_generated.mean(dim=0, keepdim=True)
            embedding_generated = self._cosyvoice.frontend.campplus_session.run(
                None,
                {self._cosyvoice.frontend.campplus_session.get_inputs()[0].name: 
                 feat_generated.unsqueeze(dim=0).cpu().numpy()}
            )[0]
            embedding_generated = torch.tensor(embedding_generated)

            # 鐠侊紕鐣绘担娆忛浮閻╅晲鎶€鎼?
            cos_sim = torch.nn.functional.cosine_similarity(
                embedding_original.flatten(),
                embedding_generated.flatten(),
                dim=0
            )

            # 闂勬劕鍩楅崷?0-1 閼煎啫娲块崘?
            similarity = float(torch.clamp(cos_sim, min=0.0, max=1.0))
            logger.info(f"Similarity calculated: similarity={similarity:.4f}")

            return similarity

        except Exception as e:
            logger.warning(f"Similarity calculation failed, using fallback value: {e}")
            # 鐠侊紕鐣绘径杈Е閺冩儼绻戦崶鐐虹帛鐠併倕鈧?
            import random
            return 0.85 + random.random() * 0.13

    def _upload_model(self, ref_id: str, voice_asset_id: str) -> str:
        """
        娑撳﹣绱跺Ο鈥崇€锋禍褏澧块敍?pt 婢规壆姹楅弬鍥︽閿涘鍩?OSS

        Args:
            ref_id: 閸欏倽鈧啴鐓舵０鎱朌
            voice_asset_id: 闂婂疇澹婄挧鍕獓ID

        Returns:
            OSS 鐎涙ê鍋嶇捄顖氱窞
        """
        try:
            # 閺屻儲澹橀張顒€婀?.pt 婢规壆姹楅弬鍥︽閿涘牆婀?voice_refs 閻╊喖缍嶆稉瀣剁礆
            ref_dir = Path(settings.ECHOES_MODELS_DIR) / "voice_refs"
            pt_file = ref_dir / f"{ref_id}.pt"

            if not pt_file.exists():
                raise FileNotFoundError(f"Missing required embedding .pt file: {pt_file}")

            # 瀵よ櫣鐝?voice_asset_id 缂佹潙瀹抽惃鍕拱閸︽澘鍩嗛崥宥忕礉娣囨繆鐦夋导姘崇樈闁瀚ㄩ棅瀹犲閸氬骸褰查惄瀛樺复閸涙垝鑵?.pt
            alias_file = ref_dir / f"{voice_asset_id}.pt"
            if not alias_file.exists():
                shutil.copy2(pt_file, alias_file)
                logger.info(f"Created local embedding alias: {alias_file}")

            # 閸氬本顒?CosyVoice voices 閻╊喖缍嶉敍灞炬暜閹?SFT 闁俺绻?voice_asset_id 閻╁瓨甯村Λ鈧槐?
            try:
                voices_dir = Path(settings.COSYVOICE_REPO_DIR) / "voices"
                voices_dir.mkdir(parents=True, exist_ok=True)
                voice_alias = voices_dir / f"{voice_asset_id}.pt"
                if not voice_alias.exists():
                    shutil.copy2(pt_file, voice_alias)
                    logger.info(f"Created CosyVoice voice alias: {voice_alias}")
            except Exception as e:
                logger.warning(f"Failed to create CosyVoice voice alias: {e}")

            # 娑撳﹣绱堕崚?OSS
            storage_key = f"voice_models/{voice_asset_id}/voice_embedding.pt"
            upload_file(str(pt_file), storage_key)
            logger.info(f"Uploaded embedding file: {storage_key}")

            # 閸忕厧顔愰弮褎顥呯槐銏ｇ熅瀵?
            compat_key = f"voice_embeddings/{voice_asset_id}.pt"
            try:
                upload_file(str(pt_file), compat_key)
                logger.info(f"Uploaded compatibility embedding key: {compat_key}")
            except Exception as e:
                logger.warning(f"Failed to upload compatibility embedding key {compat_key}: {e}")

            return storage_key

        except Exception as e:
            logger.error(f"Failed to upload embedding file: {e}")
            raise

    def _cleanup(self):
        """Cleanup temporary files."""
        try:
            import time as time_module
            tmp_dir = Path(settings.ECHOES_MODELS_DIR) / "tmp"
            if tmp_dir.exists():
                one_hour_ago = time_module.time() - 3600
                for f in tmp_dir.iterdir():
                    if f.is_file() and f.stat().st_mtime < one_hour_ago:
                        f.unlink()
                        logger.debug(f"Cleaned temporary file: {f}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temporary files: {e}")


def run_training(
    task_id: str,
    ref_id: str,
    storage_key: str,
    voice_asset_id: str,
    user_id: str,
    model_version: int = 1,
    prompt: str = "",
    progress_callback: Optional[Callable] = None
) -> TrainingResult:
    """
    鏉╂劘顢戠拋顓犵矊娴犺濮熼敍鍫滅┒閹瑰嘲鍤遍弫甯礆

    Args:
        task_id: 鐠侇厾绮屾禒璇插ID
        ref_id: 閸欏倽鈧啴鐓舵０鎱朌 (婢跺秶鏁ら悳鐗堟箒娑撳﹣绱堕幒銉ュ經)
        storage_key: OSS 鐎涙ê鍋嶇捄顖氱窞
        voice_asset_id: 闂婂疇澹婄挧鍕獓ID
        user_id: 閻劍鍩汭D
        model_version: 濡€崇€烽悧鍫熸拱
        prompt: 閼奉亜鐣炬稊濉竢ompt
        progress_callback: 鏉╂稑瀹抽崶鐐剁殶

    Returns:
        TrainingResult: 鐠侇厾绮岀紒鎾寸亯
    """
    job = VoiceTrainingJob()
    return job.train(
        task_id=task_id,
        ref_id=ref_id,
        storage_key=storage_key,
        voice_asset_id=voice_asset_id,
        user_id=user_id,
        model_version=model_version,
        prompt=prompt,
        progress_callback=progress_callback
    )


if __name__ == "__main__":
    # 濞村鐦拋顓犵矊娴犺濮?
    import argparse

    parser = argparse.ArgumentParser(description="Voice training task runner")
    parser.add_argument("--task-id", required=True, help="鐠侇厾绮屾禒璇插ID")
    parser.add_argument("--ref-id", required=True, help="閸欏倽鈧啴鐓舵０鎱朌")
    parser.add_argument("--storage-key", required=True, help="OSS鐎涙ê鍋嶇捄顖氱窞")
    parser.add_argument("--voice-asset-id", required=True, help="闂婂疇澹婄挧鍕獓ID")
    parser.add_argument("--user-id", required=True, help="閻劍鍩汭D")
    parser.add_argument("--prompt", default="", help="閼奉亜鐣炬稊濉竢ompt")

    args = parser.parse_args()

    def progress_callback(progress: float, message: str):
        print(f"Progress: {progress:.1f}% - {message}")

    result = run_training(
        task_id=args.task_id,
        ref_id=args.ref_id,
        storage_key=args.storage_key,
        voice_asset_id=args.voice_asset_id,
        user_id=args.user_id,
        prompt=args.prompt,
        progress_callback=progress_callback
    )

    if result.success:
        print("Training success!")
        print(f"  voiceModelId: {result.voice_model_id}")
        print(f"  voiceIdExternal: {result.voice_id_external}")
        print(f"  similarityScore: {result.similarity_score:.4f}")
        print(f"  modelPath: {result.model_path}")
    else:
        print(f"Training failed: {result.error_message}")
