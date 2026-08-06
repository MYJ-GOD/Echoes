import asyncio
import os
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import whisper
from opencc import OpenCC

router = APIRouter(prefix="/voice", tags=["asr"])

# Global Whisper model instance (lazy loaded)
_whisper_model = None
_whisper_lock = threading.Lock()
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
        with _whisper_lock:
            if _whisper_model is None:  # double-check
                print("Loading Whisper model for ASR transcription...")
                _whisper_model = whisper.load_model("base")  # Use base model for speed/accuracy balance
                print("Whisper model loaded successfully")
    return _whisper_model


@router.post("/asr")
async def transcribe_audio(
    audio_file: UploadFile = File(...),
):
    """
    Audio Speech Recognition - transcribe audio to text.
    Does NOT store the audio, only returns transcribed text.
    Used by Java service for voice reference upload workflow.

    - **audio_file**: Audio file to transcribe (wav, mp3, m4a, etc.)

    Returns:
    - **text**: Transcribed text in Simplified Chinese
    """
    try:
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(audio_file.filename).suffix or ".wav") as tmp:
            tmp_path = tmp.name
            audio_data = await audio_file.read()
            tmp.write(audio_data)

        try:
            # Transcribe using Whisper
            model = get_whisper_model()
            result = await asyncio.to_thread(
                model.transcribe,
                tmp_path,
                language="zh"
            )
            text = to_simplified_chinese(result["text"].strip())
            print(f"ASR transcription: {text}")

            return JSONResponse(content={
                "text": text
            })
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        print(f"ASR transcription failed: {e}")
        raise HTTPException(status_code=500, detail="ASR 转录失败")

