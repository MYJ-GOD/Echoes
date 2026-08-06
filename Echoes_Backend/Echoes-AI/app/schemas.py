from typing import Optional, List, Union, Literal
from pydantic import BaseModel, Field

# --- Input Schemas ---

class ChatRequest(BaseModel):
    """
    User input payload via WebSocket.
    """
    message: str = Field(..., description="User's input text")
    session_id: str = Field(..., description="Conversation session ID")
    
    # Voice Cloning Params (Optional)
    ref_audio_path: Optional[str] = Field(None, description="Path to reference audio for zero-shot cloning")
    ref_text: Optional[str] = Field(None, description="Transcript of the reference audio")
    
    # Mode
    stream: bool = True

# --- Output Schemas ---

class ChatResponse(BaseModel):
    """
    Server response payload via WebSocket.
    """
    type: Literal["text", "audio", "error", "status"]
    content: Union[str, bytes] # Text content or Base64 audio
    is_final: bool = False
    
    # Optional metadata
    delta: Optional[str] = None # For text streaming deltas

# --- HTTP Schemas (for legacy compatibility) ---

class TTSRequest(BaseModel):
    text: str
    prompt_text: Optional[str] = None
    prompt_wav: Optional[str] = None
    speaker_id: str = "default"
    stream: bool = False
