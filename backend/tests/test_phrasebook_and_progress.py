def test_phrasebook_crud_and_progress(client):
    # Initial phrasebook should be empty
    pb_res = client.get("/api/phrasebook")
    assert pb_res.status_code == 200
    assert pb_res.get_json()["count"] == 0

    # Add p1 to phrasebook
    add_res = client.post("/api/phrasebook", json={"phrase_id": "p1"})
    assert add_res.status_code == 201
    assert add_res.get_json()["status"] == "saved"

    # Verify p1 is in phrasebook
    pb_res2 = client.get("/api/phrasebook")
    assert pb_res2.status_code == 200
    data2 = pb_res2.get_json()
    assert data2["count"] == 1
    assert data2["phrases"][0]["id"] == "p1"

    # Progress should reflect saved count
    prog_res = client.get("/api/progress")
    assert prog_res.status_code == 200
    assert prog_res.get_json()["saved_count"] == 1

    # Remove p1 from phrasebook
    del_res = client.delete("/api/phrasebook/p1")
    assert del_res.status_code == 200
    assert del_res.get_json()["status"] == "removed"

    # Verify empty again
    pb_res3 = client.get("/api/phrasebook")
    assert pb_res3.get_json()["count"] == 0


def test_phrasebook_invalid_operations(client):
    # Missing phrase_id
    res1 = client.post("/api/phrasebook", json={})
    assert res1.status_code == 400

    # Non-existent phrase
    res2 = client.post("/api/phrasebook", json={"phrase_id": "invalid_id_999"})
    assert res2.status_code == 404

    # Delete non-existent phrase
    res3 = client.delete("/api/phrasebook/non_existent_id")
    assert res3.status_code == 404

