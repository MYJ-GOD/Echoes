import os
import sys
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings

# Calculate the project root (where .env should be)
# This assumes config.py is in common/config.py, so root is one level up
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

class Settings(BaseSettings):
    # Service
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Java API (Voice Service) callback authentication
    JAVA_API_BASE: str = "http://localhost:8082"
    INTERNAL_API_KEY: str = "change-me-internal-callback-key"

    # Paths
    COSYVOICE_REPO_DIR: str
    ECHOES_MODELS_DIR: str
    COSYVOICE_MODEL_SUBDIR: str = "cosyvoice2-0.5b"
    # Base path for voice reference audio (replaces hardcoded machine path)
    VOICE_REF_BASE_PATH: Path = Field(default=Path("./reference_audio"))
    # Default SFT speaker .pt path (can be absolute path or relative to project root)
    DEFAULT_SFT_SPEAKER_PT: Optional[str] = "data/voice_assets/shared/narrator_female/features/narrator_female.pt"

    # Model
    TTS_SAMPLE_RATE: int = 24000

    class Config:
        env_file = str(ENV_PATH)
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

def setup_cosyvoice_path():
    """
    Add CosyVoice repository to sys.path to allow direct imports.
    This must be called before importing any cosyvoice modules.
    """
    # Check if paths are set (they might be missing if .env failed to load)
    if not settings.COSYVOICE_REPO_DIR:
        raise ValueError(f"COSYVOICE_REPO_DIR not set. Checked .env at: {ENV_PATH}")

    repo_path = Path(settings.COSYVOICE_REPO_DIR).resolve()
    if not repo_path.exists():
        raise FileNotFoundError(f"CosyVoice repository not found at: {repo_path}")
    
    # Add to sys.path if not already there
    repo_str = str(repo_path)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)
        print(f"Added CosyVoice to sys.path: {repo_str}")
        
    # Also add the third_party/Matcha-TTS directory inside CosyVoice if it exists
    # CosyVoice often relies on Matcha-TTS
    matcha_path = repo_path / "third_party" / "Matcha-TTS"
    if matcha_path.exists():
        matcha_str = str(matcha_path)
        if matcha_str not in sys.path:
            sys.path.append(matcha_str)
            print(f"Added Matcha-TTS to sys.path: {matcha_str}")

# Run setup immediately when config is imported
setup_cosyvoice_path()
