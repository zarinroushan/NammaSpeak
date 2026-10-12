def test_ai_chat_local_fallback(monkeypatch, client):
    from backend.config import Config

    monkeypatch.setattr(Config, "AI_PROVIDER", "local")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    res = client.post("/api/ai/chat", json={
        "message": "How do I ask if the bus goes to Mysuru?",
        "context": "At a BMTC bus station"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert "reply_kn" in data
    assert "reply_roman" in data
    assert "reply_en" in data
    assert "learner_tip" in data
    assert "provider" in data
    assert data["provider_source"] == "offline"


def test_arbitrary_chat_does_not_return_unrelated_hardcoded_lesson(monkeypatch, client):
    from backend.config import Config

    monkeypatch.setattr(Config, "AI_PROVIDER", "local")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    inputs = [
        "I love turtles.",
        "How do I ask someone where the railway station is?",
        "Can you explain a newly invented question for me?",
    ]
    responses = []
    for message in inputs:
        res = client.post("/api/ai/chat", json={"message": message})
        assert res.status_code == 200
        data = res.get_json()
        assert data["mode"] == "offline_fallback"
        assert data["provider_source"] == "offline"
        assert "masala dosa" not in data["reply_en"].lower()
        responses.append(data["reply_en"])
    assert len(set(responses)) == len(inputs)
    for message, response in zip(inputs, responses):
        assert message in response
        assert "phrase-specific" in response.lower()


def test_gemini_chat_returns_provider_specific_result(monkeypatch, client):
    from backend.config import Config
    from backend.services.ai_provider import GeminiProvider

    monkeypatch.setattr(Config, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "test-key")
    prompts = []
    monkeypatch.setattr(
        GeminiProvider,
        "_call_gemini",
        lambda self, prompt: (prompts.append(prompt) or '{"phrase_kn":"ನನಗೆ ಚಹಾ ಇಷ್ಟ","phrase_roman":"Nanage cahā iṣṭa","meaning":"I love tea","explanation":"Use this to say that you love tea.","learner_tip":"Use ಇಷ್ಟ to express that you like something."}'),
    )

    res = client.post("/api/ai/chat", json={"message": "I love tea", "lang": "en"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["mode"] == "live_ai"
    assert data["provider_source"] == "gemini"
    assert data["reply_en"] == "I love tea"
    assert 'Learner query: "I love tea"' in prompts[0]


def test_gemini_quota_failure_is_explicit_and_not_a_hardcoded_lesson(monkeypatch, client):
    from backend.config import Config
    from backend.services.ai_provider import GeminiProvider

    monkeypatch.setattr(Config, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        GeminiProvider,
        "_call_gemini",
        lambda self, prompt: (_ for _ in ()).throw(RuntimeError("Gemini generation failed: HTTP 429")),
    )

    res = client.post("/api/ai/chat", json={"message": "I love tea", "lang": "en"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["mode"] == "ai_unavailable"
    assert data["provider_source"] == "unavailable"
    assert data["fallback_reason"] == "ai_quota_exhausted"
    assert data["original_query"] == "I love tea"
    assert "quota" in data["reply_en"].lower()
    assert "coffee" not in data["reply_en"].lower()


def test_openai_provider_forwards_exact_query_and_language(monkeypatch, client):
    from backend.config import Config
    from backend.services.ai_provider import OpenAIProvider

    class Response:
        ok = True
        status_code = 200

        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": '{"phrase_kn":"ನನಗೆ ಚಹಾ ಇಷ್ಟ","phrase_roman":"Nanage cahā iṣṭa","meaning":"I love tea","explanation":"A natural way to say you love tea.","learner_tip":"Use ಇಷ್ಟ to express preference."}'
                    }
                }]
            }

    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(Config, "AI_PROVIDER", "openai")
    monkeypatch.setattr(Config, "OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(Config, "OPENAI_MODEL", "gpt-test")
    monkeypatch.setattr("backend.services.ai_provider.requests.post", fake_post)

    res = client.post("/api/ai/chat", json={"message": "I love tea", "lang": "hi"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["provider_source"] == "openai"
    assert data["mode"] == "live_ai"
    assert data["reply_en"] == "I love tea"
    assert calls[0][0].endswith("/v1/chat/completions")
    request = calls[0][1]["json"]
    assert request["model"] == "gpt-test"
    assert "I love tea" in request["messages"][1]["content"]
    assert "Hindi" in request["messages"][1]["content"]


def test_openai_quota_failure_returns_unavailable_response(monkeypatch, client):
    from backend.config import Config

    class Response:
        ok = False
        status_code = 429

        def json(self):
            return {"error": {"message": "quota exceeded"}}

    monkeypatch.setattr(Config, "AI_PROVIDER", "openai")
    monkeypatch.setattr(Config, "OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr("backend.services.ai_provider.requests.post", lambda *args, **kwargs: Response())

    res = client.post("/api/ai/chat", json={"message": "I love tea"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["mode"] == "ai_unavailable"
    assert data["provider_source"] == "unavailable"
    assert data["fallback_reason"] == "ai_quota_exhausted"
    assert data["original_query"] == "I love tea"
    assert "coffee" not in data["reply_en"].lower()
    assert "quota" in data["reply_en"].lower()


def test_ai_unavailable_message_uses_selected_language(monkeypatch, client):
    from backend.config import Config
    from backend.services.ai_provider import GeminiProvider

    monkeypatch.setattr(Config, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        GeminiProvider,
        "_call_gemini",
        lambda self, prompt: (_ for _ in ()).throw(RuntimeError("Gemini generation failed: HTTP 429")),
    )

    response = client.post("/api/ai/chat", json={"message": "I love tea", "lang": "ta"})
    data = response.get_json()
    assert data["lang"] == "ta"
    assert data["original_query"] == "I love tea"
    assert "AI" in data["reply_en"]
    assert data["learner_tip"] != "Please try again later when Gemini is available."


def test_invalid_language_defaults_to_english_and_preserves_kannada(monkeypatch, client):
    from backend.config import Config
    from backend.services.ai_provider import GeminiProvider

    monkeypatch.setattr(Config, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        GeminiProvider,
        "_call_gemini",
        lambda self, prompt: (_ for _ in ()).throw(RuntimeError("provider down")),
    )

    response = client.post("/api/ai/chat", json={"message": "I love tea", "lang": "xx"})
    data = response.get_json()
    assert data["lang"] == "en"
    assert "ಕ್ಷಮಿಸಿ" in data["reply_kn"]
    assert "Kṣamisi" in data["reply_roman"]


def test_local_chat_supports_all_preferred_languages(monkeypatch, client):
    from backend.config import Config

    monkeypatch.setattr(Config, "AI_PROVIDER", "local")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    for language in ("en", "hi", "bn", "ta", "te"):
        response = client.post(
            "/api/ai/chat",
            json={"message": "How do I order dosa?", "lang": language},
        )
        data = response.get_json()
        assert response.status_code == 200
        assert data["lang"] == language
        assert data["reply_kn"] == "ಒಂದು ಮಸಾಲ ದೋಸೆ ಕೊಡಿ"
        assert data["reply_roman"] == "Ondu masāla dōse koḍi"


def test_ai_quota_response_localizes_all_user_facing_fields(monkeypatch, client):
    from backend.config import Config
    from backend.services.ai_provider import GeminiProvider

    monkeypatch.setattr(Config, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        GeminiProvider,
        "_call_gemini",
        lambda self, prompt: (_ for _ in ()).throw(RuntimeError("Gemini generation failed: HTTP 429")),
    )
    expected = {
        "en": "Please try again later when the AI service is available.",
        "hi": "AI सेवा उपलब्ध होने पर कृपया बाद में फिर कोशिश करें।",
        "bn": "AI পরিষেবা উপলব্ধ হলে অনুগ্রহ করে পরে আবার চেষ্টা করুন।",
        "ta": "AI சேவை கிடைக்கும்போது தயவுசெய்து பின்னர் முயற்சிக்கவும்.",
        "te": "AI సేవ అందుబాటులో ఉన్నప్పుడు దయచేసి తర్వాత మళ్లీ ప్రయత్నించండి.",
    }
    for language, tip in expected.items():
        response = client.post(
            "/api/ai/chat",
            json={"message": "I love tea", "lang": language},
        )
        data = response.get_json()
        assert data["lang"] == language
        assert data["mode"] == "ai_unavailable"
        assert data["reply_kn"] == "ಕ್ಷಮಿಸಿ, AI ಸೇವೆ ಈಗ ಲಭ್ಯವಿಲ್ಲ."
        assert data["reply_roman"] == "Kṣamisi, AI sēve īga labhyavilla."
        assert data["reply_en"] == data["explanation"] == data["disclaimer"]
        assert data["learner_tip"] == tip
        assert data["original_query"] == "I love tea"


def test_ai_chat_missing_message(client):
    res = client.post("/api/ai/chat", json={})
    assert res.status_code == 400


def test_ai_chat_excessive_length(client):
    res = client.post("/api/ai/chat", json={"message": "x" * 600})
    assert res.status_code == 400


def test_ai_explain_endpoint(client):
    res = client.post("/api/ai/explain", json={
        "phrase": "ದಯವಿಟ್ಟು ಸಹಾಯ ಮಾಡಿ",
        "question": "Is this polite to use with strangers?"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert "explanation" in data
    assert "formality" in data


def test_ai_healthcare_disclaimer_behavior(monkeypatch, client):
    from backend.config import Config

    monkeypatch.setattr(Config, "AI_PROVIDER", "local")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    res = client.post("/api/ai/chat", json={
        "message": "I need a doctor, hospital nearby",
        "context": "Medical assistance"
    })
    assert res.status_code == 200
    data = res.get_json()
    # Ensure health reply includes local health advice/reminder
    assert "reply_kn" in data
    assert any(term in (data.get("learner_tip", "") + data.get("disclaimer", "")).lower() for term in ["health", "emergency", "108", "diagnosis", "assistance"])
