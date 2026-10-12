import pytest
import json
import os

from backend.app import create_app
from backend.models import init_db
from backend.services import translation_service as translation_module
from backend.services.ai_provider import GeminiProvider


@pytest.fixture()
def client(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE_PATH": str(tmp_path / "test.db"),
        "DATABASE_URL": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
    })
    return app.test_client()


def test_translation_endpoint_returns_complete_localized_dictionary(client):
    response = client.get("/api/translations/bn")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["lang"] == "bn"
    assert payload["strings"]["nav_explore"]
    assert payload["strings"]["hero_h1_part1"]
    assert payload["provider"]
    assert payload["source"] in {"cache", "offline", "gemini"}


def test_phrase_localization_preserves_kannada_and_translates_meaning(client):
    response = client.get("/api/phrases?lang=ta")
    phrase = response.get_json()["phrases"][0]

    assert response.status_code == 200
    assert phrase["kn"] == "ನಮಸ್ಕಾರ"
    assert phrase["roman"] == "Namaskāra"
    assert phrase["meaning"] != "Hello / Universal Respectful Greeting"


def test_ai_partner_returns_structured_dosa_lesson_in_selected_language(monkeypatch, client):
    from backend.config import Config

    monkeypatch.setattr(Config, "AI_PROVIDER", "local")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    response = client.post(
        "/api/ai/chat",
        json={"message": "How do I order dosa?", "lang": "bn"},
    )
    lesson = response.get_json()

    assert response.status_code == 200
    assert lesson["reply_kn"] == "ಒಂದು ಮಸಾಲ ದೋಸೆ ಕೊಡಿ"
    assert lesson["reply_en"] == "দয়া করে আমাকে একটি মসলা দোসা দিন"
    assert lesson["mode"] in {"offline_fallback", "live_ai"}


def test_ai_explanation_uses_selected_language_without_replacing_phrase(client):
    response = client.post(
        "/api/ai/explain",
        json={"phrase": "ಒಂದು ದೋಸೆ ಕೊಡಿ", "lang": "ta"},
    )
    explanation = response.get_json()

    assert response.status_code == 200
    assert explanation["phrase"] == "ಒಂದು ದೋಸೆ ಕೊಡಿ"
    assert "கன்னடத்தில்" in explanation["explanation"]


def test_static_ui_translations_use_offline_dictionary_without_provider_call(tmp_path, monkeypatch):
    db_path = str(tmp_path / "gemini.db")
    init_db(db_path)
    monkeypatch.setattr(translation_module.Config, "DATABASE_PATH", db_path)
    monkeypatch.setattr(translation_module.Config, "DATABASE_URL", f"sqlite:///{db_path.replace(os.sep, '/')}")
    monkeypatch.setattr(translation_module.Config, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(translation_module.Config, "GEMINI_API_KEY", "test-key")

    class MockGemini:
        calls = 0

        def _call_gemini(self, prompt):
            self.calls += 1
            return json.dumps({
                key: f"AI:{value}"
                for key, value in service.source_strings.items()
            }, ensure_ascii=False)

    service = translation_module.TranslationService()
    provider = MockGemini()
    monkeypatch.setattr(translation_module, "get_ai_provider", lambda: provider)

    first = service.get_ui_translations("bn")
    second = service.get_ui_translations("bn")

    assert first["source"] == "offline"
    assert first["sources"]["hero_h1_part1"] == "offline"
    assert second["source"] == "offline"
    assert second["sources"]["hero_h1_part1"] == "offline"
    assert provider.calls == 0


def test_explicit_batch_translation_still_uses_configured_provider(tmp_path, monkeypatch):
    db_path = str(tmp_path / "batch.db")
    init_db(db_path)
    monkeypatch.setattr(translation_module.Config, "DATABASE_PATH", db_path)
    monkeypatch.setattr(translation_module.Config, "DATABASE_URL", f"sqlite:///{db_path.replace(os.sep, '/')}")
    monkeypatch.setattr(translation_module.Config, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(translation_module.Config, "GEMINI_API_KEY", "test-key")

    class MockGemini:
        calls = 0

        def _call_gemini(self, prompt):
            self.calls += 1
            return json.dumps({"greeting": "नमस्ते"})

    provider = MockGemini()
    monkeypatch.setattr(translation_module, "get_ai_provider", lambda: provider)
    service = translation_module.TranslationService()

    translated, success = service.translate_batch_with_ai("hi", {"greeting": "Hello"})

    assert success is True
    assert translated == {"greeting": "नमस्ते"}
    assert provider.calls == 1


def test_configured_provider_failure_uses_offline_without_caching_as_translation(tmp_path, monkeypatch):
    db_path = str(tmp_path / "failure.db")
    init_db(db_path)
    monkeypatch.setattr(translation_module.Config, "DATABASE_PATH", db_path)
    monkeypatch.setattr(translation_module.Config, "DATABASE_URL", f"sqlite:///{db_path.replace(os.sep, '/')}")
    monkeypatch.setattr(translation_module.Config, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(translation_module.Config, "GEMINI_API_KEY", "test-key")

    class FailingGemini:
        def _call_gemini(self, prompt):
            raise RuntimeError("mock provider failure")

    monkeypatch.setattr(
        translation_module,
        "get_ai_provider",
        lambda: FailingGemini(),
    )

    service = translation_module.TranslationService()
    result = service.get_ui_translations("ta")
    conn = translation_module.get_db_connection(db_path)
    cached_count = conn.execute(
        "SELECT COUNT(*) AS c FROM translation_cache WHERE target_lang = ?",
        ("ta",),
    ).fetchone()["c"]
    conn.close()

    assert result["source"] == "offline"
    assert result["sources"]["hero_h1_part1"] == "offline"
    assert cached_count == 0


def test_gemini_discovers_supported_model_and_uses_header(monkeypatch):
    requests_seen = []

    class Response:
        ok = True
        status_code = 200

        def json(self):
            if requests_seen[-1]["method"] == "GET":
                return {
                    "models": [
                        {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
                        {"name": "models/text-embedding-005", "supportedGenerationMethods": ["embedContent"]},
                    ]
                }
            return {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}

    def fake_request(method, url, **kwargs):
        requests_seen.append({"method": method, "url": url, **kwargs})
        return Response()

    monkeypatch.setattr("backend.services.ai_provider.requests.get", lambda url, **kwargs: fake_request("GET", url, **kwargs))
    monkeypatch.setattr("backend.services.ai_provider.requests.post", lambda url, **kwargs: fake_request("POST", url, **kwargs))

    provider = GeminiProvider("secret-test-key", "gemini-2.5-flash")
    assert provider.probe() == "OK"
    assert provider.model_name == "gemini-2.0-flash"
    assert requests_seen[0]["headers"] == {"x-goog-api-key": "secret-test-key"}
    assert "key=" not in requests_seen[1]["url"]
    assert requests_seen[1]["headers"]["x-goog-api-key"] == "secret-test-key"


def test_gemini_http_errors_are_sanitized(monkeypatch):
    from backend.services import ai_provider as ai_provider_module

    ai_provider_module._model_inventory_cache.clear()
    class Response:
        ok = False
        status_code = 404

        def json(self):
            return {"error": {"message": "model not found"}}

    monkeypatch.setattr("backend.services.ai_provider.requests.get", lambda *args, **kwargs: Response())
    provider = GeminiProvider("secret-test-key", "missing-model")

    with pytest.raises(RuntimeError, match="HTTP 404"):
        provider.list_models()
