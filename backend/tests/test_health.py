def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["app"] == "NammaSpeak"
    assert "ai_provider" in data
    assert data["database"] == "connected"

