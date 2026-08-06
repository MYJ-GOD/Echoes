import os
import io
import struct
import time
import asyncio
from pathlib import Path
import torch
import torchaudio
import tempfile
from typing import Generator, Optional, Union, AsyncGenerator
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import threading
import shutil

from common.config import settings, PROJECT_ROOT
# Verify path setup before importing cosyvoice
import sys
# Ensure we can import from the repo dir
if settings.COSYVOICE_REPO_DIR not in sys.path:
    sys.path.insert(0, settings.COSYVOICE_REPO_DIR)

try:
    from cosyvoice.cli.cosyvoice import CosyVoice2, CosyVoice
    from cosyvoice.utils.file_utils import logging
except ImportError as e:
    print(f"Error importing CosyVoice: {e}")
    print(f"Current sys.path: {sys.path}")
    raise

class CosyVoiceWorker:
    _instance = None
    _model = None
    _executor = None
    _lock = None
    _active_requests = 0
    _max_concurrent = 2  # Limit concurrent requests to prevent GPU memory issues
    _request_timeout = 300  # 5 minutes timeout

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CosyVoiceWorker, cls).__new__(cls)
            cls._instance._executor = ThreadPoolExecutor(max_workers=cls._max_concurrent, thread_name_prefix="cosyvoice")
            cls._instance._lock = threading.Lock()
        return cls._instance

    def initialize(self):
        """
        Initialize the CosyVoice model. This is heavy and should be done once.
        """
        if self._model is not None:
            return

        model_dir = os.path.join(settings.ECHOES_MODELS_DIR, settings.COSYVOICE_MODEL_SUBDIR)
        print(f"Loading CosyVoice2 model from: {model_dir}")
        
        if not os.path.exists(model_dir):
            raise FileNotFoundError(f"Model directory not found: {model_dir}")

        # Check for CUDA
        use_cuda = torch.cuda.is_available()
        print(f"Using CUDA: {use_cuda}")

        # Initialize CosyVoice2
        # Note: We use fp16=True if CUDA is available for performance
        try:
            self._model = CosyVoice2(
                model_dir=model_dir,
                load_jit=False, # Set to True if you have JIT models
                load_trt=False, 
                fp16=use_cuda
            )
            # Ensure local voice .pt files are registered for SFT
            self._register_sft_voices(model_dir)
            print("CosyVoice2 model loaded successfully.")
        except Exception as e:
            print(f"Failed to load CosyVoice2 model: {e}")
            raise

    def _register_sft_voices(self, model_dir: str) -> None:
        """
        Load voices/*.pt (audio_ref/text_ref/embedding) and register embeddings into spk2info.pt for SFT.
        Prioritizes pre-extracted embedding if available, otherwise extracts from audio_ref.
        """
        try:
            model = self._model
            if model is None:
                return
            voices_dir = Path(settings.COSYVOICE_REPO_DIR) / "voices"
            if not voices_dir.exists():
                return
            spk2info_path = Path(model_dir) / "spk2info.pt"
            spk2info = {}
            if spk2info_path.exists():
                try:
                    spk2info = torch.load(spk2info_path, map_location="cpu", weights_only=False)
                except Exception:
                    spk2info = {}

            updated = False
            for voice_file in voices_dir.glob("*.pt"):
                spk_id = voice_file.stem
                if spk_id in spk2info:
                    continue
                try:
                    voice_obj = torch.load(voice_file, map_location="cpu", weights_only=False)
                    
                    # First, try to use pre-extracted embedding
                    embedding = voice_obj.get("embedding")
                    if embedding is not None:
                        # Use the pre-extracted embedding directly
                        spk2info[spk_id] = {"embedding": embedding.detach().cpu()}
                        print(f"Registered speaker '{spk_id}' using pre-extracted embedding")
                        updated = True
                        continue
                    
                    # Fallback: extract embedding from audio_ref if available
                    audio_ref = voice_obj.get("audio_ref")
                    if audio_ref is None:
                        continue
                    if audio_ref.dim() == 1:
                        audio_ref = audio_ref.unsqueeze(0)
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        tmp_path = tmp.name
                    # Assume model sample rate for the stored reference
                    torchaudio.save(tmp_path, audio_ref, model.sample_rate)
                    embedding = model.frontend._extract_spk_embedding(tmp_path)
                    spk2info[spk_id] = {"embedding": embedding.detach().cpu()}
                    updated = True
                finally:
                    try:
                        if "tmp_path" in locals() and os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except Exception:
                        pass

            if updated:
                torch.save(spk2info, spk2info_path)
                # Refresh in-memory cache
                model.frontend.spk2info = torch.load(
                    spk2info_path, map_location=model.frontend.device, weights_only=False
                )
                print(f"Registered {len(spk2info)} SFT speakers into spk2info.pt")
        except Exception as e:
            print(f"Failed to register SFT voices: {e}")

    def get_model(self) -> CosyVoice2:
        if self._model is None:
            self.initialize()
        return self._model

    def pcm_to_wav_bytes(self, pcm_data: bytes, sample_rate: int = 24000) -> bytes:
        """
        Convert raw PCM bytes to WAV format bytes.

        Args:
            pcm_data: Raw PCM 16-bit audio data
            sample_rate: Sample rate (default 24000 for CosyVoice)

        Returns:
            WAV format bytes
        """
        # WAV header constants
        riff_chunk_id = b'RIFF'
        riff_chunk_size = 36 + len(pcm_data)  # 36 = header size - 8
        wave_format = b'WAVE'
        fmt_chunk_id = b'fmt '
        fmt_chunk_size = 16  # PCM format
        audio_format = 1  # PCM
        num_channels = 1  # Mono
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        data_chunk_id = b'data'
        data_chunk_size = len(pcm_data)

        # Pack WAV header
        wav_header = struct.pack('<4sI4s4sIHHIIHH4sI',
            riff_chunk_id,      # RIFF
            riff_chunk_size,    # Chunk size
            wave_format,        # WAVE
            fmt_chunk_id,       # fmt
            fmt_chunk_size,     # Subchunk1Size (16 for PCM)
            audio_format,       # AudioFormat (1 = PCM)
            num_channels,       # NumChannels
            sample_rate,        # SampleRate
            byte_rate,          # ByteRate
            block_align,        # BlockAlign
            bits_per_sample,    # BitsPerSample
            data_chunk_id,      # Subchunk2ID
            data_chunk_size     # Subchunk2Size
        )

        return wav_header + pcm_data

    def synthesize_wav(
        self,
        text: str,
        prompt_text: Optional[str] = None,
        prompt_wav: Optional[str] = None,
        speaker_id: Optional[str] = None,
        mode: str = "zero_shot"
    ) -> bytes:
        """
        Synthesize complete speech and return WAV bytes with concurrency control.
        Attempts zero_shot first, falls back to sft if it fails.
        """
        start_time = time.time()

        # Concurrency control
        with self._lock:
            while self._active_requests >= self._max_concurrent:
                print(f"Waiting for available TTS slot. Active: {self._active_requests}/{self._max_concurrent}")
                time.sleep(0.1)  # Small delay before retry
            self._active_requests += 1

        try:
            # Submit to thread pool with timeout
            future = self._executor.submit(self._synthesize_wav_impl, text, prompt_text, prompt_wav, speaker_id, mode)
            wav_bytes = future.result(timeout=self._request_timeout)

            elapsed = time.time() - start_time
            print(f"TTS synthesis completed in {elapsed:.2f}s")
            return wav_bytes

        finally:
            with self._lock:
                self._active_requests -= 1

    def _synthesize_wav_impl(
        self,
        text: str,
        prompt_text: Optional[str] = None,
        prompt_wav: Optional[str] = None,
        speaker_id: Optional[str] = None,
        mode: str = "zero_shot"
    ) -> bytes:
        """
        Internal implementation of WAV synthesis with fallback logic.
        """
        model = self.get_model()

        # Prepare resampler if needed
        src_sr = model.sample_rate
        target_sr = settings.TTS_SAMPLE_RATE
        resampler = None

        if src_sr != target_sr:
            resampler = torchaudio.transforms.Resample(orig_freq=src_sr, new_freq=target_sr)
            # If using CUDA, move resampler to GPU
            if torch.cuda.is_available():
                resampler = resampler.cuda()

        # Try requested mode first, fallback to sft if it fails
        modes_to_try = [mode]
        if mode != "sft":
            modes_to_try.append("sft")  # Always try sft as fallback

        for attempt_mode in modes_to_try:
            try:
                print(f"Attempting TTS synthesis with mode: {attempt_mode}")

                iterator = self._get_inference_iterator(model, text, prompt_text, prompt_wav, speaker_id, attempt_mode)

                # Accumulate all PCM chunks
                pcm_chunks = []
                for output in iterator:
                    # output is a dict: {'tts_speech': torch.Tensor}
                    audio_tensor = output['tts_speech']

                    # Resample if necessary
                    if resampler is not None:
                        audio_tensor = resampler(audio_tensor)

                    # Convert to PCM 16-bit bytes
                    audio_int16 = (audio_tensor * 32767).clamp(-32768, 32767).to(torch.int16)
                    pcm_bytes = audio_int16.cpu().numpy().tobytes()
                    pcm_chunks.append(pcm_bytes)

                # Combine all PCM chunks
                if pcm_chunks:
                    combined_pcm = b''.join(pcm_chunks)
                    # Wrap in WAV container
                    wav_bytes = self.pcm_to_wav_bytes(combined_pcm, target_sr)
                    if attempt_mode != mode:
                        print(f"Successfully fell back from {mode} to {attempt_mode}")
                    return wav_bytes
                else:
                    raise RuntimeError("No audio data generated")

            except Exception as e:
                print(f"TTS synthesis failed with mode {attempt_mode}: {e}")
                if attempt_mode == modes_to_try[-1]:  # Last attempt failed
                    raise RuntimeError(f"All TTS modes failed. Last error: {e}")
                # Continue to next mode

        # This should never be reached
        raise RuntimeError("Unexpected error in TTS synthesis")

    def _get_inference_iterator(self, model, text: str, prompt_text: Optional[str],
                               prompt_wav: Optional[str], speaker_id: Optional[str], mode: str):
        """Get the appropriate inference iterator based on mode."""
        if mode == "sft":
            # Pre-trained speaker: try provided speaker_id first;
            # then check configured default (DEFAULT_SFT_SPEAKER_PT);
            # finally fallback to any voice in CosyVoice repo voices dir.
            chosen_speaker = speaker_id

            # 1) If no speaker_id provided, try DEFAULT_SFT_SPEAKER_PT env var
            if not chosen_speaker:
                try:
                    default_pt = None
                    # A. Check env var / settings
                    if settings.DEFAULT_SFT_SPEAKER_PT:
                        candidate = Path(settings.DEFAULT_SFT_SPEAKER_PT)
                        # If relative path, resolve against project root
                        if not candidate.is_absolute():
                            candidate = PROJECT_ROOT / candidate
                        if candidate.exists():
                            default_pt = candidate

                    # B. Check hardcoded project default asset location (fallback)
                    if default_pt is None:
                        default_features_dir = PROJECT_ROOT / "data" / "voice_assets" / "shared" / "narrator_female" / "features"
                        if default_features_dir.exists():
                            default_pt = next(default_features_dir.glob("*.pt"), None)

                    if default_pt:
                        voices_dir = Path(settings.COSYVOICE_REPO_DIR) / "voices"
                        voices_dir.mkdir(parents=True, exist_ok=True)
                        dest = voices_dir / default_pt.name
                        # Copy default .pt into CosyVoice voices dir if not already present
                        if not dest.exists():
                            shutil.copy2(default_pt, dest)
                        chosen_speaker = dest.stem
                except Exception as e:
                    print(f"Error loading default speaker: {e}")
                    pass

            # 2) If still not chosen, fallback to any available voice in repo
            if not chosen_speaker:
                try:
                    voices_dir = Path(settings.COSYVOICE_REPO_DIR) / "voices"
                    if voices_dir.exists():
                        first_voice = next(voices_dir.glob("*.pt"), None)
                        if first_voice:
                            chosen_speaker = first_voice.stem
                except Exception:
                    chosen_speaker = None

            if not chosen_speaker:
                raise ValueError("No speaker found for sft mode; provide speaker_id or add a voice in CosyVoice 'voices' directory")

            # Compat: callers may pass assetId, while training may have registered
            # speaker key as "user_<userId>_<assetId>". Resolve and/or register lazily.
            chosen_speaker = self._resolve_sft_speaker(model, chosen_speaker)

            iterator = model.inference_sft(text, chosen_speaker, stream=True)

        elif mode == "zero_shot":
            # Voice cloning
            if not prompt_wav:
                raise ValueError("prompt_wav is required for zero_shot mode")

            # Use prompt_text if provided
            if not prompt_text:
                print("Warning: prompt_text not provided for zero_shot. Using placeholder.")
                prompt_text = "Hello, this is a voice sample."

            iterator = model.inference_zero_shot(text, prompt_text, prompt_wav, stream=True)

        elif mode == "cross_lingual":
             if not prompt_wav:
                raise ValueError("prompt_wav is required for cross_lingual mode")
             iterator = model.inference_cross_lingual(text, prompt_wav, stream=True)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        return iterator

    def _resolve_sft_speaker(self, model, requested_speaker: str) -> str:
        """
        Resolve an SFT speaker key that exists in frontend.spk2info.
        Supports:
        1) exact key match,
        2) lazy registration from voices/<speaker>.pt,
        3) suffix match for keys like user_<uid>_<assetId>.
        """
        spk2info = getattr(model.frontend, "spk2info", {}) or {}
        if requested_speaker in spk2info:
            return requested_speaker

        # Try lazy register from voices/<speaker>.pt so freshly produced alias files work
        if self._register_single_voice_from_file(model, requested_speaker):
            return requested_speaker

        suffix = f"_{requested_speaker}"
        suffix_matches = sorted([k for k in spk2info.keys() if k.endswith(suffix)])
        if suffix_matches:
            resolved = suffix_matches[0]
            print(f"Resolved SFT speaker '{requested_speaker}' -> '{resolved}' by suffix match")
            return resolved

        raise KeyError(requested_speaker)

    def _register_single_voice_from_file(self, model, speaker_id: str) -> bool:
        """
        Register one speaker from voices/<speaker_id>.pt into frontend.spk2info.
        Returns True if registration succeeded.
        """
        try:
            voices_dir = Path(settings.COSYVOICE_REPO_DIR) / "voices"
            voice_file = voices_dir / f"{speaker_id}.pt"
            if not voice_file.exists():
                return False

            voice_obj = torch.load(voice_file, map_location="cpu", weights_only=False)
            embedding = voice_obj.get("embedding")
            if embedding is None:
                return False

            spk2info = getattr(model.frontend, "spk2info", {}) or {}
            spk2info[speaker_id] = {"embedding": embedding.detach().cpu()}
            model.frontend.spk2info = spk2info
            print(f"Lazily registered SFT speaker from file: {speaker_id}")
            return True
        except Exception as e:
            print(f"Failed lazy register speaker '{speaker_id}': {e}")
            return False

    def synthesize_stream(
        self,
        text: str,
        prompt_text: Optional[str] = None,
        prompt_wav: Optional[str] = None,
        speaker_id: Optional[str] = None,
        mode: str = "zero_shot", # zero_shot, sft, cross_lingual
        stream: bool = True
    ) -> Generator[bytes, None, None]:
        """
        Legacy method: Synthesize speech and yield PCM bytes.
        Kept for backward compatibility.
        """
        # For now, just yield the complete WAV as a single chunk
        # This maintains the streaming interface but returns complete audio
        yield self.synthesize_wav(text, prompt_text, prompt_wav, speaker_id, mode)

# Global instance
cosyvoice_worker = CosyVoiceWorker()
