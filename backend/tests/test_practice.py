def test_list_scenarios(client):
    res = client.get("/api/practice/scenarios")
    assert res.status_code == 200
    data = res.get_json()
    assert "scenarios" in data
    assert data["count"] > 0
    s = data["scenarios"][0]
    assert "title" in s
    assert "options" in s
    assert len(s["options"]) >= 2


def test_get_scenario_by_id(client):
    res = client.get("/api/practice/scenarios/s1")
    assert res.status_code == 200
    s = res.get_json()
    assert s["id"] == "s1"
    assert "options" in s


def test_get_scenario_by_id_unknown(client):
    res = client.get("/api/practice/scenarios/invalid_999")
    assert res.status_code == 404


def test_submit_correct_answer(client):
    # s1 option o1 is the correct answer
    res = client.post("/api/practice/answer", json={
        "scenario_id": "s1",
        "option_id": "o1"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["is_correct"] is True
    assert "why" in data
    assert len(data["why"]) > 0


def test_submit_incorrect_answer(client):
    # s1 option o2 is incorrect
    res = client.post("/api/practice/answer", json={
        "scenario_id": "s1",
        "option_id": "o2"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["is_correct"] is False
    assert "why" in data

    # Verify that the related phrase is queued in adaptive revision
    rev_res = client.get("/api/revision")
    assert rev_res.status_code == 200
    rev_data = rev_res.get_json()
    assert rev_data["count"] >= 1
    assert any(p["id"] == "p3" for p in rev_data["phrases"])


def test_submit_answer_missing_fields(client):
    res = client.post("/api/practice/answer", json={"scenario_id": "s1"})
    assert res.status_code == 400

    res2 = client.post("/api/practice/answer", data="not json", content_type="text/plain")
    assert res2.status_code == 400


def test_submit_answer_invalid_option(client):
    res = client.post("/api/practice/answer", json={
        "scenario_id": "s1",
        "option_id": "non_existent_option"
    })
    assert res.status_code == 400

