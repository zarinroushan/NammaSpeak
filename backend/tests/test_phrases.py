def test_list_categories(client):
    res = client.get("/api/categories")
    assert res.status_code == 200
    data = res.get_json()
    assert "categories" in data
    assert len(data["categories"]) >= 5


def test_list_phrases(client):
    res = client.get("/api/phrases")
    assert res.status_code == 200
    data = res.get_json()
    assert "phrases" in data
    assert data["count"] > 0
    # Every phrase must have id, kn, roman, meaning, context, tag, speech
    for p in data["phrases"]:
        assert "id" in p
        assert "kn" in p
        assert "roman" in p
        assert "meaning" in p
        assert "context" in p


def test_filter_phrases_by_category(client):
    res = client.get("/api/phrases?category=transport")
    assert res.status_code == 200
    data = res.get_json()
    for p in data["phrases"]:
        assert p["category"] == "transport"


def test_search_phrases(client):
    # Search by English meaning
    res = client.get("/api/phrases?search=coffee")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] >= 1
    assert any("coffee" in p["meaning"].lower() for p in data["phrases"])

    # Search by Kannada text
    res = client.get("/api/phrases?search=ನಮಸ್ಕಾರ")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] >= 1
    assert any("ನಮಸ್ಕಾರ" in p["kn"] for p in data["phrases"])


def test_search_phrases_can_return_legitimate_zero_results(client):
    res = client.get("/api/phrases?search=not-a-real-namma-phrase")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] == 0
    assert data["search"] == "not-a-real-namma-phrase"


def test_get_phrase_by_id_success(client):
    res = client.get("/api/phrases/p1")
    assert res.status_code == 200
    p = res.get_json()
    assert p["id"] == "p1"
    assert "ನಮಸ್ಕಾರ" in p["kn"]


def test_get_phrase_by_id_unknown_returns_404(client):
    res = client.get("/api/phrases/non_existent_999")
    assert res.status_code == 404
    data = res.get_json()
    assert "error" in data
