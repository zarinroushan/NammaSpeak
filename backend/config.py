import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory is the project root (one level up from backend)
BACKEND_DIR = Path(__file__).resolve().parent
BASE_DIR = BACKEND_DIR.parent

# Load .env file from project root if it exists
dotenv_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=dotenv_path)


def _env_float(name, default):
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "nammaspeak-dev-secret-key-change-in-prod")
    DEBUG = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "t")
    PORT = int(os.getenv("FLASK_PORT", 5000))
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() in ("true", "1", "t")

    # Database
    INSTANCE_DIR = BASE_DIR / "instance"
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
    # Retained only so the explicit legacy exporter can locate the old file.
    DATABASE_PATH = os.getenv("DATABASE_PATH", str(INSTANCE_DIR / "nammaspeak.db"))

    # AI Configuration
    AI_PROVIDER = os.getenv("AI_PROVIDER", "local").lower()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    # Leave model selection to the provider when AI_MODEL is not configured.
    AI_MODEL = os.getenv("AI_MODEL", "").strip()
    GEMINI_REQUEST_TIMEOUT = _env_float("GEMINI_REQUEST_TIMEOUT", 8)
    GEMINI_MODEL_DISCOVERY_TIMEOUT = _env_float("GEMINI_MODEL_DISCOVERY_TIMEOUT", 4)
    GEMINI_MODEL_FAILURE_COOLDOWN = _env_float("GEMINI_MODEL_FAILURE_COOLDOWN", 300)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    OPENAI_REQUEST_TIMEOUT = _env_float("OPENAI_REQUEST_TIMEOUT", 15)
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_v3").strip()
    ELEVENLABS_TTS_TIMEOUT = _env_float("ELEVENLABS_TTS_TIMEOUT", 15)
    ELEVENLABS_TTS_CACHE_SIZE = int(os.getenv("ELEVENLABS_TTS_CACHE_SIZE", "64"))
