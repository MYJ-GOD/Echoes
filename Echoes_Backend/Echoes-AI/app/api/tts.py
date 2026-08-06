from __future__ import annotations

import logging
import os
import re
import shutil
import asyncio
from pathlib import Path
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from common.config import settings, PROJECT_ROOT
from workers.tts.cosyvoice_worker import cosyvoice_worker

router = APIRouter(prefix="/tts", tags=["tts"])
logger = logging.getLogger(__name__)
VOICE_INTERNAL_BASE_URL = os.environ.get("JAVA_API_URL", "http://localhost:18083").rstrip("/")
WS_EOS_MARKER = "__ECHOES_STREAM_EOS__"


def _is_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}

# Request models
class TTSRequest(BaseModel):
    text: str
    voice_name: str = "default"
    prompt_text: Optional[str] = None
    stream: bool = False

async def verify_internal_call(x_internal_key: str = Header(None, alias="x-internal-api-key")):
    """Dependency to verify internal calls."""
    if x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Direct calls are forbidden")
    return True

@router.post("/inference/synthesize-text")
async def synthesize_text(
    request: TTSRequest,
    x_internal_key: str = Header(None, alias="x-internal-api-key"),
    x_strict_voice: Optional[str] = Header(None)
):
    """
    Synchronous TTS: Text -> Audio Bytes (WAV)
    Internal API called by Java Conversation Service.
    """
    if x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        # Resolve voice reference
        ref_audio_path, ref_text, speaker_id = resolve_voice_reference(request.voice_name)
        strict_voice = _is_truthy(x_strict_voice)
        if strict_voice and request.voice_name != "default" and not ref_audio_path and not speaker_id:
            raise HTTPException(status_code=422, detail=f"voice_not_available:{request.voice_name}")
        
        # Determine mode: SFT if speaker_id provided, else zero_shot if audio provided, else sft fallback
        if speaker_id:
            mode = "sft"
        elif ref_audio_path:
            mode = "zero_shot"
        else:
            mode = "sft"  # Use default SFT fallback

        logger.info(f"TTS Sync Request: text='{request.text[:20]}...', voice='{request.voice_name}', mode={mode}, speaker_id={speaker_id}")

        wav_bytes = await asyncio.to_thread(
            cosyvoice_worker.synthesize_wav,
            text=request.text,
            prompt_text=ref_text,
            prompt_wav=ref_audio_path,
            mode=mode,
            speaker_id=speaker_id
        )
        return Response(content=wav_bytes, media_type="audio/wav")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS Sync Error: {e}")
        raise HTTPException(status_code=500, detail="TTS 合成失败")

@router.post("/inference/synthesize-stream")
async def synthesize_stream(
    request: Request,
    voiceName: str = "default",
    x_internal_key: str = Header(None, alias="x-internal-api-key"),
    x_strict_voice: Optional[str] = Header(None)
):
    """
    Streaming TTS: Text Stream (SSE) -> Audio Stream (SSE/Bytes)
    Receives text chunks via SSE or raw body, yields audio chunks.
    """
    if x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        # Resolve voice once for this streaming session
        ref_audio_path, ref_text, speaker_id = resolve_voice_reference(voiceName)
        strict_voice = _is_truthy(x_strict_voice)
        if strict_voice and voiceName != "default" and not ref_audio_path and not speaker_id:
            raise HTTPException(status_code=422, detail=f"voice_not_available:{voiceName}")

        # Determine mode: SFT if speaker_id provided, else zero_shot if audio provided, else sft fallback
        if speaker_id:
            mode = "sft"
        elif ref_audio_path:
            mode = "zero_shot"
        else:
            mode = "sft"

        logger.info(f"TTS Stream Request: voice='{voiceName}', mode={mode}, speaker_id={speaker_id}")

        async def iter_clean_text_segments() -> AsyncGenerator[str, None]:
            """
            Incrementally parse incoming text stream and emit speakable segments.
            Supports plain text chunks and SSE-like chunks prefixed with `data:`.
            """
            buffer = ""
            min_emit_len = 6
            max_buffer_len = 48
            # enforce proper CJK punctuation set even if file encoding is inconsistent
            sentence_marks = {"\u3002", "\uff01", "\uff1f", ".", "!", "?", "\n"}
            raw_chunk_count = 0

            async for raw_chunk in request.stream():
                if not raw_chunk:
                    continue
                raw_chunk_count += 1
                chunk = raw_chunk.decode("utf-8", errors="ignore")
                if not chunk:
                    continue
                logger.debug(f"TTS stream raw chunk #{raw_chunk_count}, bytes={len(raw_chunk)}, preview={chunk[:120]!r}")

                # Normalize possible SSE framing
                normalized_lines = []
                for line in chunk.splitlines():
                    l = line.strip()
                    if not l:
                        continue
                    if l.startswith("data:"):
                        l = l[5:].strip()
                    if l:
                        normalized_lines.append(l)
                if not normalized_lines:
                    continue

                incoming_text = "".join(normalized_lines)
                if not incoming_text:
                    continue

                buffer += incoming_text

                # Emit while we can cut a stable segment
                while True:
                    boundary_idx = -1
                    for idx, ch in enumerate(buffer):
                        if ch in sentence_marks:
                            boundary_idx = idx + 1

                    if boundary_idx >= min_emit_len:
                        segment = buffer[:boundary_idx].strip()
                        buffer = buffer[boundary_idx:]
                        if segment:
                            yield segment
                        continue

                    if len(buffer) >= max_buffer_len:
                        segment = buffer[:max_buffer_len].strip()
                        buffer = buffer[max_buffer_len:]
                        if segment:
                            yield segment
                        continue

                    break

            # Flush tail
            tail = buffer.strip()
            if tail:
                yield tail
            if raw_chunk_count == 0:
                logger.warning("TTS stream received 0 raw text chunks from upstream request body")

        async def audio_generator():
            try:
                seg_count = 0
                async for segment in iter_clean_text_segments():
                    seg_count += 1
                    logger.info(f"TTS stream segment #{seg_count}, len={len(segment)}, preview={segment[:80]}")
                    # Run heavy synthesis in worker thread to avoid blocking event loop.
                    wav_bytes = await asyncio.to_thread(
                        cosyvoice_worker.synthesize_wav,
                        segment,
                        ref_text,
                        ref_audio_path,
                        speaker_id,
                        mode,
                    )
                    chunk_size = 8192
                    for i in range(0, len(wav_bytes), chunk_size):
                        yield wav_bytes[i:i + chunk_size]
            except Exception as e:
                logger.exception(f"Stream generation error: {e}")
                return

        return StreamingResponse(audio_generator(), media_type="application/octet-stream")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS Stream Error: {e}")
        raise HTTPException(status_code=500, detail="TTS 流式合成失败")


@router.websocket("/inference/synthesize-stream-ws")
async def synthesize_stream_ws(websocket: WebSocket, voiceName: str = "default"):
    """
    True duplex stream over WebSocket:
    - client sends text chunks continuously
    - server returns audio bytes continuously
    """
    x_internal_key = websocket.headers.get("x-internal-api-key")
    x_strict_voice = websocket.headers.get("x-strict-voice")
    if x_internal_key != settings.INTERNAL_API_KEY:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        ref_audio_path, ref_text, speaker_id = resolve_voice_reference(voiceName)
        strict_voice = _is_truthy(x_strict_voice)
        if strict_voice and voiceName != "default" and not ref_audio_path and not speaker_id:
            await websocket.close(code=1008)
            return
        if speaker_id:
            mode = "sft"
        elif ref_audio_path:
            mode = "zero_shot"
        else:
            mode = "sft"
        logger.info(f"TTS Stream WS Request: voice='{voiceName}', mode={mode}, speaker_id={speaker_id}")

        buffer = ""
        min_emit_len = 6
        max_buffer_len = 48
        sentence_marks = {"\u3002", "\uff01", "\uff1f", ".", "!", "?", "\n"}
        raw_chunk_count = 0

        async def flush_segment(segment: str):
            if not segment:
                return
            logger.info(f"TTS stream ws segment, len={len(segment)}, preview={segment[:80]}")
            wav_bytes = await asyncio.to_thread(
                cosyvoice_worker.synthesize_wav,
                segment,
                ref_text,
                ref_audio_path,
                speaker_id,
                mode,
            )
            chunk_size = 8192
            for i in range(0, len(wav_bytes), chunk_size):
                await websocket.send_bytes(wav_bytes[i:i + chunk_size])

        while True:
            try:
                incoming = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            if incoming == WS_EOS_MARKER:
                break

            raw_chunk_count += 1
            logger.debug(f"TTS stream ws raw chunk #{raw_chunk_count}, len={len(incoming)}, preview={incoming[:120]!r}")

            normalized_lines = []
            for line in incoming.splitlines():
                l = line.strip()
                if not l:
                    continue
                if l.startswith("data:"):
                    l = l[5:].strip()
                if l:
                    normalized_lines.append(l)
            if not normalized_lines:
                continue

            buffer += "".join(normalized_lines)

            while True:
                boundary_idx = -1
                for idx, ch in enumerate(buffer):
                    if ch in sentence_marks:
                        boundary_idx = idx + 1

                if boundary_idx >= min_emit_len:
                    segment = buffer[:boundary_idx].strip()
                    buffer = buffer[boundary_idx:]
                    await flush_segment(segment)
                    continue

                if len(buffer) >= max_buffer_len:
                    segment = buffer[:max_buffer_len].strip()
                    buffer = buffer[max_buffer_len:]
                    await flush_segment(segment)
                    continue

                break

        tail = buffer.strip()
        if tail:
            await flush_segment(tail)
        if raw_chunk_count == 0:
            logger.warning("TTS stream ws received 0 raw text chunks from upstream request body")
    except Exception as e:
        logger.exception(f"TTS Stream WS Error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

def _is_probably_audio_file(path: Path) -> bool:
    try:
        if not path.exists() or path.stat().st_size < 44:
            return False
        with path.open('rb') as f:
            head = f.read(12)
            if head.startswith(b'RIFF') and head[8:12] == b'WAVE':
                return True
            if head[:3] == b'ID3':
                return True
            # MP3 frame sync (very loose)
            if head[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
                return True
        return False
    except Exception:
        return False


def _download_embedding_by_storage_key(storage_key: str, local_target: Path) -> bool:
    try:
        import requests

        signed_url = None
        try:
            url = f"{VOICE_INTERNAL_BASE_URL}/internal/voice/assets/ref/signed?storage_key={storage_key}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                result = response.json()
                signed_url = result.get("url")
        except Exception as e:
            logger.warning(f"Failed to get signed URL from Java for {storage_key}: {e}")

        if not signed_url:
            return False

        response = requests.get(signed_url, timeout=60)
        if response.status_code != 200:
            logger.warning(f"Failed to download embedding from OSS ({storage_key}): {response.status_code}")
            return False

        with open(local_target, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        logger.warning(f"Failed to download embedding from OSS ({storage_key}): {e}")
        return False


def download_embedding_from_oss(ref_id: str) -> Optional[Path]:
    """
    Download .pt embedding file from OSS to local cache.
    Returns local path if successful, None otherwise.
    """
    try:
        local_dir = Path(settings.ECHOES_MODELS_DIR) / "voice_refs"
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / f"{ref_id}.pt"

        # Compat strategy:
        # 1) legacy upload key: voice_embeddings/{id}.pt
        # 2) training model key: voice_models/{voice_asset_id}/voice_embedding.pt
        candidate_keys = [
            f"voice_embeddings/{ref_id}.pt",
            f"voice_models/{ref_id}/voice_embedding.pt",
        ]
        downloaded_key = None
        for storage_key in candidate_keys:
            if _download_embedding_by_storage_key(storage_key, local_path):
                downloaded_key = storage_key
                break

        if not downloaded_key:
            logger.warning(f"No downloadable embedding found in OSS for {ref_id}")
            return None

        logger.info(f"Downloaded .pt from OSS ({downloaded_key}) to: {local_path}")
        
        # Also copy to CosyVoice voices directory
        try:
            voices_dir = Path(settings.COSYVOICE_REPO_DIR) / "voices"
            voices_dir.mkdir(parents=True, exist_ok=True)
            target_path = voices_dir / f"{ref_id}.pt"
            shutil.copy2(local_path, target_path)
            logger.info(f"Copied .pt to CosyVoice voices dir: {target_path}")
        except Exception as e:
            logger.warning(f"Failed to copy .pt to CosyVoice voices dir: {e}")
        
        return local_path

    except Exception as e:
        logger.warning(f"Failed to download .pt from OSS: {e}")
        return None


def resolve_voice_reference(voice_name: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Helper to find reference audio path and text from voice name.
    Returns: (ref_audio_path, ref_text, speaker_id)
    - If speaker_id is not None, use SFT mode with that speaker
    - If ref_audio_path is not None, use zero_shot mode with audio file
    - If both are None, use default SFT fallback
    """
    # Validate voice_name: only allow safe characters to prevent path traversal
    if not re.match(r'^[a-zA-Z0-9_-]+$', voice_name):
        raise ValueError(f"Invalid voice_name: {voice_name}")

    # Map default voice name to shared narrator for now
    normalized_name = "narrator_female" if voice_name == "default" else voice_name

    def _default_prompt_text() -> str:
        return "hello"

    # Prefer SFT if a voice .pt exists for this speaker
    voices_dir = Path(settings.COSYVOICE_REPO_DIR) / "voices"
    if voices_dir.exists():
        voice_pt = voices_dir / f"{normalized_name}.pt"
        if voice_pt.exists():
            # Use SFT mode with the speaker ID
            logger.info(f"Using SFT mode with speaker_id={normalized_name}")
            return None, None, normalized_name

    # 1. Check uploaded refs
    ref_dir = Path(settings.ECHOES_MODELS_DIR) / "voice_refs"
    if ref_dir.exists():
        # Check exact ID match
        matches = list(ref_dir.glob(f"{normalized_name}.*"))
        if matches:
            # Check if there's a .pt file with embedding
            pt_file = ref_dir / f"{normalized_name}.pt"
            if pt_file.exists():
                # Use SFT mode with the ref_id as speaker_id
                logger.info(f"Using SFT mode with speaker_id={normalized_name} (from .pt)")
                return None, None, normalized_name
            # Fallback to zero_shot with audio file
            return str(matches[0]), _default_prompt_text(), None

    # 2. Check shared voice assets bundled with Echoes-AI
    shared_voice_dir = PROJECT_ROOT / "data" / "voice_assets" / "shared" / normalized_name
    if shared_voice_dir.exists():
        source_dir = shared_voice_dir / "source"
        if source_dir.exists():
            # Prefer explicit ref.wav if present
            for ext in ("wav", "mp3"):
                candidate = source_dir / f"ref.{ext}"
                if candidate.exists() and _is_probably_audio_file(candidate):
                    return str(candidate), _default_prompt_text(), None
            # Fallback: any audio file in source dir
            for f in source_dir.iterdir():
                if f.suffix.lower() in {".wav", ".mp3"} and _is_probably_audio_file(f):
                    return str(f), _default_prompt_text(), None

    # 3. Check repo assets (CosyVoice/asset or reference-audio folders)
    repo_path = Path(settings.COSYVOICE_REPO_DIR)
    candidates = [
        repo_path / "reference_audio",
        repo_path / "\u53c2\u8003\u97f3\u9891",
        repo_path / "asset",
        settings.VOICE_REF_BASE_PATH / "reference_audio",
        settings.VOICE_REF_BASE_PATH / "参考音频",
    ]

    for c in candidates:
        if c and c.exists():
            # Fallback prompt for default narrator if no exact match
            if normalized_name in {"narrator_female", "default"}:
                zp = c / "zero_shot_prompt.wav"
                if zp.exists() and _is_probably_audio_file(zp):
                    return str(zp), "hello", None

            # Try exact match
            for ext in ("wav", "mp3"):
                f = c / f"{normalized_name}.{ext}"
                if f.exists() and _is_probably_audio_file(f):
                    return str(f), f.stem, None

            # Try partial match
            for f in c.iterdir():
                if normalized_name in f.stem:
                    return str(f), f.stem, None

    # 4. Try to download from OSS if not found locally
    logger.info(f"Voice not found locally, trying to download from OSS: {normalized_name}")
    downloaded_path = download_embedding_from_oss(normalized_name)
    if downloaded_path and downloaded_path.exists():
        logger.info(f"Successfully downloaded .pt from OSS, using SFT mode with speaker_id={normalized_name}")
        return None, None, normalized_name

    return None, None, None
