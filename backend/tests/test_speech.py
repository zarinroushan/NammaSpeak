import pytest

from backend.services import speech_service
from backend.services.speech_service import ElevenLabsSpeechService, SpeechGenerationError


class FakeResponse:
    def __init__(self, status_code=200, content=b"ID3fake-mp3", content_type="audio/mpeg"):
        self.status_code = status_code
        self.content = content
        self.ok = status_code < 400
        self.headers = {"Content-Type": content_type}


@pytest.fixture(autouse=True)
def clear_audio_cache():
    speech_service.clear_speech_cache()
    yield
    speech_service.clear_speech_cache()


def test_speech_rejects_empty_and_non_kannada_input():
    service = ElevenLabsSpeechService(api_key="test-key", voice_id="voice")
    for phrase in (" ", "Namaskara"):
        with pytest.raises(SpeechGenerationError) as error:
            service.generate(phrase)
        assert error.value.code == "invalid_input"


def test_speech_requires_credentials():
    with pytest.raises(SpeechGenerationError) as error:
        ElevenLabsSpeechService(api_key="", voice_id="").generate("ನಮಸ್ಕಾರ")
    assert error.value.code == "not_configured"


def test_speech_provider_failure_is_safe(monkeypatch):
    monkeypatch.setattr(
        speech_service.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(500, b'{"error":"private details"}', "application/json"),
    )
    with pytest.raises(SpeechGenerationError) as error:
        ElevenLabsSpeechService(api_key="test-key", voice_id="voice").generate("ನಮಸ್ಕಾರ")
    assert error.value.code == "provider_error"
    assert "private details" not in error.value.message


def test_speech_logs_sanitized_upstream_detail(monkeypatch, caplog):
    response = FakeResponse(402, b"", "application/json")
    response.json = lambda: {
        "detail": {
            "status": "payment_required",
            "message": "The request requires a paid plan.",
            "api_key": "must-not-log",
        }
    }
    monkeypatch.setattr(speech_service.requests, "post", lambda *args, **kwargs: response)

    with caplog.at_level("WARNING"):
        with pytest.raises(SpeechGenerationError):
            ElevenLabsSpeechService(api_key="test-key", voice_id="voice").generate("ನಮಸ್ಕಾರ")

    assert "payment_required" in caplog.text
    assert "paid plan" in caplog.text
    assert "must-not-log" not in caplog.text
    assert "test-key" not in caplog.text


def test_speech_audio_is_cached_and_uses_kannada_payload(monkeypatch):
    calls = []

    def generate(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse()

    monkeypatch.setattr(speech_service.requests, "post", generate)
    service = ElevenLabsSpeechService(api_key="test-key", voice_id="voice")
    first = service.generate("ನಮಸ್ಕಾರ")
    second = service.generate("ನಮಸ್ಕಾರ")

    assert first == second == b"ID3fake-mp3"
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0].endswith("/v1/text-to-speech/voice")
    assert kwargs["headers"]["xi-api-key"] == "test-key"
    assert kwargs["json"]["model_id"] == "eleven_v3"
    assert kwargs["json"]["language_code"] == "kn"
    assert kwargs["json"]["text"] == "ನಮಸ್ಕಾರ"
    assert kwargs["params"]["output_format"] == "mp3_44100_128"


def test_slow_speech_uses_provider_speed_and_separate_cache(monkeypatch):
    calls = []

    def generate(*args, **kwargs):
        calls.append(kwargs)
        return FakeResponse()

    monkeypatch.setattr(speech_service.requests, "post", generate)
    service = ElevenLabsSpeechService(api_key="test-key", voice_id="voice")
    service.generate("ನಮಸ್ಕಾರ", speed=0.7)
    service.generate("ನಮಸ್ಕಾರ", speed=0.7)
    service.generate("ನಮಸ್ಕಾರ")

    assert len(calls) == 2
    assert calls[0]["json"]["voice_settings"] == {"speed": 0.7}
    assert "voice_settings" not in calls[1]["json"]


def test_speech_rejects_malformed_audio(monkeypatch):
    monkeypatch.setattr(
        speech_service.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(content=b"not audio", content_type="application/json"),
    )
    with pytest.raises(SpeechGenerationError) as error:
        ElevenLabsSpeechService(api_key="test-key", voice_id="voice").generate("ನಮಸ್ಕಾರ")
    assert error.value.code == "invalid_audio"


def test_speech_endpoint_returns_mp3(client, monkeypatch):
    monkeypatch.setattr(
        speech_service.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(),
    )
    monkeypatch.setattr("backend.services.speech_service.Config.ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr("backend.services.speech_service.Config.ELEVENLABS_VOICE_ID", "voice")

    response = client.post("/api/speech/kannada", json={"phrase": "ನಮಸ್ಕಾರ"})

    assert response.status_code == 200
    assert response.mimetype == "audio/mpeg"
    assert response.data == b"ID3fake-mp3"


def test_speech_endpoint_handles_missing_configuration(client, monkeypatch):
    monkeypatch.setattr("backend.services.speech_service.Config.ELEVENLABS_API_KEY", "")
    monkeypatch.setattr("backend.services.speech_service.Config.ELEVENLABS_VOICE_ID", "")

    response = client.post("/api/speech/kannada", json={"phrase": "ನಮಸ್ಕಾರ"})

    assert response.status_code == 503
    assert response.get_json()["code"] == "not_configured"
