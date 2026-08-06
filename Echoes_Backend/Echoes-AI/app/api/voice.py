import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import whisper
from opencc import OpenCC

from common.config import settings

router = APIRouter(prefix="/voice", tags=["voice"])
VOICE_INTERNAL_BASE_URL = os.environ.get("JAVA_API_URL", "http://localhost:18083").rstrip("/")

# Global Whisper model instance (lazy loaded)
_whisper_model = None
_t2s_converter = OpenCC("t2s")


def to_simplified_chinese(text: str) -> str:
    """Convert Traditional Chinese text to Simplified Chinese."""
    if not text:
        return text
    return _t2s_converter.convert(text)

def get_whisper_model():
    """Get or initialize Whisper model for transcription."""
    global _whisper_model
    if _whisper_model is None:
        print("Loading Whisper model for voice reference transcription...")
        _whisper_model = whisper.load_model("base")  # Use base model for speed/accuracy balance
        print("Whisper model loaded successfully")
    return _whisper_model

@router.post("/ref/upload")
async def upload_voice_reference(
    audio_file: UploadFile = File(...),
    ref_text: Optional[str] = Form(None),
    ref_id: Optional[str] = Form(None)
):
    """
    Upload voice reference audio for zero-shot voice cloning.

    - **audio_file**: Reference audio file (wav, mp3, etc.)
    - **ref_text**: Optional reference text (will auto-transcribe if not provided)

    Returns:
    - **ref_id**: Unique reference ID for this voice sample
    - **ref_text**: Transcribed text from the audio (if auto-transcribed)
    """
    try:
        # Create storage directory if it doesn't exist
        ref_dir = Path(settings.ECHOES_MODELS_DIR) / "voice_refs"
        ref_dir.mkdir(parents=True, exist_ok=True)

        # Use provided ref_id when present so Java/AI keep the same ID across upload -> training.
        ref_id = (ref_id or "").strip() or str(uuid.uuid4())

        # Save uploaded audio file
        file_extension = Path(audio_file.filename).suffix or ".wav"
        audio_path = ref_dir / f"{ref_id}{file_extension}"

        # Read and save the uploaded file
        audio_data = await audio_file.read()
        with open(audio_path, "wb") as f:
            f.write(audio_data)

        print(f"Saved voice reference audio: {audio_path}")

        # Auto-transcribe if ref_text not provided
        if not ref_text:
            try:
                model = get_whisper_model()
                # 指定语言为中文，Whisper 会输出简体中文
                result = model.transcribe(str(audio_path), language="zh")
                ref_text = to_simplified_chinese(result["text"].strip())
                print(f"Auto-transcribed ref_text: {ref_text}")
            except Exception as e:
                print(f"Whisper transcription failed: {e}")
                # Don't fail the whole request, just warn
                ref_text = f"[Transcription failed: {str(e)}]"
        else:
            ref_text = to_simplified_chinese(ref_text)
            print(f"Using provided ref_text: {ref_text}")

        # Save ref_text to a local file for training to reuse
        ref_text_file = ref_dir / f"{ref_id}.txt"
        with open(ref_text_file, "w", encoding="utf-8") as f:
            f.write(ref_text)
        print(f"Saved ref_text to: {ref_text_file}")

        # Extract and save speaker embedding for SFT training
        embedding_generated = False
        embedding_error = None
        try:
            import torch
            import torchaudio
            
            # 先检查 CosyVoice 路径是否正确设置
            if not settings.COSYVOICE_REPO_DIR:
                raise ValueError("COSYVOICE_REPO_DIR not set in environment")
            if not settings.ECHOES_MODELS_DIR:
                raise ValueError("ECHOES_MODELS_DIR not set in environment")
            
            # 添加 CosyVoice 到 sys.path
            import sys
            cosyvoice_path = Path(settings.COSYVOICE_REPO_DIR)
            if str(cosyvoice_path) not in sys.path:
                sys.path.insert(0, str(cosyvoice_path))
            
            from cosyvoice.cli.cosyvoice import AutoModel

            print(f"Loading CosyVoice model from: {settings.ECHOES_MODELS_DIR}")
            
            # Load CosyVoice model
            model_dir = os.path.join(settings.ECHOES_MODELS_DIR, settings.COSYVOICE_MODEL_SUBDIR)
            cosyvoice = AutoModel(model_dir=model_dir)
            print("CosyVoice model loaded successfully")

            # Load and preprocess audio (resample to 16k mono)
            waveform, sample_rate = torchaudio.load(str(audio_path))
            print(f"Audio loaded: sample_rate={sample_rate}, shape={waveform.shape}")
            
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
                waveform = resampler(waveform)
                print(f"Resampled to 16kHz")
                
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
                print(f"Converted to mono")
                
            waveform = waveform / waveform.abs().max()
            print(f"Normalized waveform")

            # Extract speaker embedding
            print(f"Extracting speaker embedding...")
            embedding = cosyvoice.frontend._extract_spk_embedding(str(audio_path))
            print(f"Speaker embedding extracted: shape={embedding.shape}")

            # Save embedding as .pt file
            embedding_file = ref_dir / f"{ref_id}.pt"
            torch.save({
                "audio_ref": waveform,
                "text_ref": ref_text,
                "embedding": embedding.detach().cpu()
            }, str(embedding_file))
            print(f"Saved speaker embedding to: {embedding_file}")

            # Also copy to CosyVoice voices directory for SFT mode inference
            try:
                voices_dir = Path(settings.COSYVOICE_REPO_DIR) / "voices"
                voices_dir.mkdir(parents=True, exist_ok=True)
                target_voice_file = voices_dir / f"{ref_id}.pt"
                shutil.copy2(embedding_file, target_voice_file)
                print(f"Copied voice to CosyVoice voices dir: {target_voice_file}")
            except Exception as e:
                print(f"[WARN] Failed to copy voice to CosyVoice voices dir: {e}")
                # Non-critical, continue
            
            # Upload .pt file to OSS for backup/restore
            try:
                import requests
                # Read .pt file
                with open(embedding_file, "rb") as f:
                    pt_data = f.read()
                
                # Upload to OSS via Java API
                oss_object_name = f"voice_embeddings/{ref_id}.pt"
                files = {"audio_file": (oss_object_name, pt_data, "application/octet-stream")}
                data = {"object_name": oss_object_name}
                
                # Call Java upload-object endpoint
                upload_url = f"{VOICE_INTERNAL_BASE_URL}/internal/voice/assets/ref/upload-object"
                print(f"Using upload-object endpoint: {upload_url}")
                response = requests.post(upload_url, files=files, data=data, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    print(f"Uploaded .pt to OSS: {result.get('storage_key')}")
                else:
                    print(f"[WARN] Failed to upload .pt to OSS: {response.status_code}")
            except Exception as e:
                print(f"[WARN] Failed to upload .pt to OSS: {e}")
                # Non-critical, continue
            
            embedding_generated = True
            
        except ImportError as e:
            embedding_error = f"Import error: {e}"
            print(f"[ERROR] Failed to extract speaker embedding - Import error: {e}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            embedding_error = str(e)
            print(f"[ERROR] Failed to extract speaker embedding: {e}")
            import traceback
            traceback.print_exc()
            # Non-critical, continue without embedding file

        if not embedding_generated:
            raise RuntimeError(f"Embedding extraction failed for ref_id={ref_id}: {embedding_error}")

        return JSONResponse(content={
            "ref_id": ref_id,
            "ref_text": ref_text,
            "audio_path": str(audio_path),
            "embedding_generated": embedding_generated,
            "embedding_error": embedding_error
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"Voice reference upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/ref/{ref_id}")
async def get_voice_reference(ref_id: str):
    """
    Get voice reference information by ref_id.
    """
    try:
        ref_dir = Path(settings.ECHOES_MODELS_DIR) / "voice_refs"

        # Find the audio file for this ref_id
        audio_files = list(ref_dir.glob(f"{ref_id}.*"))
        if not audio_files:
            raise HTTPException(status_code=404, detail="Voice reference not found")

        audio_path = audio_files[0]

        # Get audio duration
        duration_ms = None
        try:
            import torchaudio
            info = torchaudio.info(str(audio_path))
            duration_ms = int((info.num_frames / info.sample_rate) * 1000)
        except Exception as e:
            print(f"Failed to get audio duration: {e}")

        return JSONResponse(content={
            "ref_id": ref_id,
            "audio_path": str(audio_path),
            "duration_ms": duration_ms,
            "exists": True
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"Get voice reference failed: {e}")
        raise HTTPException(status_code=500, detail=f"Get reference failed: {str(e)}")

