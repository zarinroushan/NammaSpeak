"""ElevenLabs speech generation for Kannada pronunciation."""

import hashlib
import logging
import re
import threading
from collections import OrderedDict

import requests

from backend.config import Config

logger = logging.getLogger(__name__)

_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
_KANNADA_TEXT = re.compile(r"[\u0C80-\u0CFF]")
_cache = OrderedDict()
_cache_lock = threading.Lock()


class SpeechGenerationError(RuntimeError):
    """Safe, user-facing category for speech generation failures."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class ElevenLabsSpeechService:
    """Generate and cache Kannada audio without exposing ElevenLabs credentials."""

    def __init__(self, api_key=None, voice_id=None, model=None, timeout=None, cache_size=None):
        self.api_key = (api_key if api_key is not None else Config.ELEVENLABS_API_KEY).strip()
        self.voice_id = (voice_id if voice_id is not None else Config.ELEVENLABS_VOICE_ID).strip()
        self.model = (model or Config.ELEVENLABS_MODEL).strip()
        self.timeout = timeout if timeout is not None else Config.ELEVENLABS_TTS_TIMEOUT
        self.cache_size = cache_size if cache_size is not None else Config.ELEVENLABS_TTS_CACHE_SIZE

    def _cache_key(self, phrase, speed=1.0):
        value = f"{self.model}\0{self.voice_id}\0kn\0{speed:g}\0{phrase}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _looks_like_audio(content, content_type):
        if not content:
            return False
        media_type = (content_type or "").split(";", 1)[0].lower().strip()
        return media_type in {"audio/mpeg", "audio/mp3", "audio/wav", "audio/ogg", "audio/opus"} or content[:3] == b"ID3" or content[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")

    @staticmethod
    def _error_detail(response):
        """Return only documented, non-secret upstream error fields for diagnostics."""
        try:
            payload = response.json()
        except (AttributeError, ValueError, TypeError):
            return "", ""
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if not isinstance(detail, dict):
            return "", ""
        status = detail.get("status")
        message = detail.get("message")
        if not isinstance(status, str):
            status = ""
        if not isinstance(message, str):
            message = ""
        return status[:120], message[:300]

    def generate(self, phrase, speed=1.0):
        phrase = (phrase or "").strip()
        if not phrase:
            raise SpeechGenerationError("invalid_input", "A Kannada phrase is required.")
        if not _KANNADA_TEXT.search(phrase):
            raise SpeechGenerationError("invalid_input", "Input must contain Kannada text.")
        if len(phrase) > 500:
            raise SpeechGenerationError("invalid_input", "The Kannada phrase is too long.")
        if not self.api_key or not self.voice_id:
            raise SpeechGenerationError("not_configured", "ElevenLabs pronunciation is not configured.")
        if self.model != "eleven_v3":
            raise SpeechGenerationError("not_configured", "ElevenLabs Kannada pronunciation requires the eleven_v3 model.")
        try:
            speed = float(speed)
        except (TypeError, ValueError) as exc:
            raise SpeechGenerationError("invalid_input", "Playback speed is invalid.") from exc
        if not 0.25 <= speed <= 4.0:
            raise SpeechGenerationError("invalid_input", "Playback speed is outside the supported range.")

        key = self._cache_key(phrase, speed)
        with _cache_lock:
            cached = _cache.get(key)
            if cached is not None:
                _cache.move_to_end(key)
                return cached

        body = {
            "text": phrase,
            "model_id": self.model,
            "language_code": "kn",
        }
        if speed != 1.0:
            body["voice_settings"] = {"speed": speed}
        try:
            response = requests.post(
                _TTS_URL.format(voice_id=self.voice_id),
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json=body,
                params={"output_format": "mp3_44100_128"},
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            logger.warning("ElevenLabs TTS timed out")
            raise SpeechGenerationError("timeout", "Pronunciation audio took too long to generate.") from exc
        except requests.RequestException as exc:
            logger.warning("ElevenLabs TTS network error (%s)", type(exc).__name__)
            raise SpeechGenerationError("provider_error", "Pronunciation audio is temporarily unavailable.") from exc

        if response.status_code == 429:
            logger.warning("ElevenLabs TTS rate limited")
            raise SpeechGenerationError("rate_limited", "Pronunciation audio is temporarily busy.")
        if response.status_code in (401, 403):
            detail_status, detail_message = self._error_detail(response)
            logger.warning(
                "ElevenLabs TTS access failure (http_status=%s, detail_status=%s, detail_message=%s)",
                response.status_code,
                detail_status or "unknown",
                detail_message or "unavailable",
            )
            raise SpeechGenerationError("provider_error", "ElevenLabs pronunciation is not available for this configuration.")
        if not response.ok:
            detail_status, detail_message = self._error_detail(response)
            logger.warning(
                "ElevenLabs TTS failed (http_status=%s, detail_status=%s, detail_message=%s)",
                response.status_code,
                detail_status or "unknown",
                detail_message or "unavailable",
            )
            raise SpeechGenerationError("provider_error", "Pronunciation audio could not be generated.")
        if not self._looks_like_audio(response.content, response.headers.get("Content-Type")):
            logger.warning("ElevenLabs TTS returned malformed audio")
            raise SpeechGenerationError("invalid_audio", "The pronunciation response was invalid.")

        audio = response.content
        with _cache_lock:
            _cache[key] = audio
            _cache.move_to_end(key)
            while len(_cache) > max(1, self.cache_size):
                _cache.popitem(last=False)
        return audio


def clear_speech_cache():
    with _cache_lock:
        _cache.clear()
