def test_guest_identity_persists_and_isolated(client):
    first = client.post("/api/auth/guest", json={})
    assert first.status_code == 200
    guest_id = first.get_json()["user"]["id"]
    assert first.get_json()["user"]["account_type"] == "guest"

    assert client.post("/api/phrasebook", json={"phrase_id": "p1"}).status_code == 201
    assert client.get("/api/phrasebook").get_json()["count"] == 1
    assert client.get("/api/auth/me").get_json()["user"]["id"] == guest_id

    other = client.application.test_client()
    assert other.post("/api/auth/guest", json={}).status_code == 200
    assert other.get("/api/phrasebook").get_json()["count"] == 0
    assert other.get("/api/progress").get_json()["saved_count"] == 0


def test_registration_duplicate_login_logout_and_language(client):
    assert client.post("/api/auth/register", json={
        "name": "Asha",
        "email": "asha@example.com",
        "password": "secure-pass-1",
        "language": "hi",
    }).status_code == 201
    me = client.get("/api/auth/me").get_json()
    assert me["user"]["email"] == "asha@example.com"
    assert me["user"]["preferred_language"] == "hi"

    duplicate = client.post("/api/auth/register", json={
        "name": "Other",
        "email": "asha@example.com",
        "password": "secure-pass-2",
        "language": "en",
    })
    assert duplicate.status_code == 400

    assert client.post("/api/auth/logout").status_code == 200
    assert client.post("/api/auth/login", json={
        "email": "asha@example.com",
        "password": "secure-pass-1",
    }).status_code == 200
    assert client.post("/api/auth/language", json={"language": "ta"}).get_json()["user"]["preferred_language"] == "ta"


def test_guest_progress_transfers_to_registered_account(client):
    client.post("/api/auth/guest", json={})
    client.post("/api/phrasebook", json={"phrase_id": "p1"})
    answer = client.post("/api/practice/answer", json={
        "scenario_id": "s1",
        "option_id": "o1",
        "lang": "en",
    })
    assert answer.status_code == 200

    registered = client.post("/api/auth/register", json={
        "name": "Ravi",
        "email": "ravi@example.com",
        "password": "secure-pass-1",
        "language": "en",
    })
    assert registered.status_code == 201
    assert registered.get_json()["user"]["account_type"] == "registered"
    assert client.get("/api/phrasebook").get_json()["count"] == 1
    assert client.get("/api/progress").get_json()["answered"] == 1


def test_registered_users_cannot_see_each_others_data(client):
    client.post("/api/auth/register", json={
        "name": "One",
        "email": "one@example.com",
        "password": "secure-pass-1",
        "language": "en",
    })
    client.post("/api/phrasebook", json={"phrase_id": "p1"})
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={
        "name": "Two",
        "email": "two@example.com",
        "password": "secure-pass-2",
        "language": "en",
    })
    assert client.get("/api/phrasebook").get_json()["count"] == 0


def test_signout_then_continue_as_guest_never_exposes_registered_data(client):
    client.post("/api/auth/register", json={
        "name": "Private learner",
        "email": "private@example.com",
        "password": "secure-pass-1",
        "language": "en",
    })
    client.post("/api/phrasebook", json={"phrase_id": "p1"})
    client.post("/api/practice/answer", json={
        "scenario_id": "s1",
        "option_id": "o1",
        "lang": "en",
    })
    registered_id = client.get("/api/auth/me").get_json()["user"]["id"]
    assert client.post("/api/auth/logout").get_json()["authenticated"] is False

    guest = client.post("/api/auth/guest", json={}).get_json()["user"]
    assert guest["account_type"] == "guest"
    assert guest["id"] != registered_id
    assert guest["name"] != "Private learner"
    assert guest["email"] is None
    assert client.get("/api/phrasebook").get_json()["count"] == 0
    assert client.get("/api/progress").get_json()["answered"] == 0


def test_guest_session_is_replaced_if_guest_endpoint_is_called_while_registered(client):
    client.post("/api/auth/register", json={
        "name": "Registered",
        "email": "registered@example.com",
        "password": "secure-pass-1",
        "language": "en",
    })
    registered_id = client.get("/api/auth/me").get_json()["user"]["id"]

    guest = client.post("/api/auth/guest", json={}).get_json()["user"]
    assert guest["account_type"] == "guest"
    assert guest["id"] != registered_id
    assert client.get("/api/auth/me").get_json()["user"]["account_type"] == "guest"


def test_guest_login_merges_guest_data_without_exposing_account_data(client):
    client.post("/api/auth/register", json={
        "name": "Account owner",
        "email": "owner@example.com",
        "password": "secure-pass-1",
        "language": "en",
    })
    client.post("/api/phrasebook", json={"phrase_id": "p1"})
    client.post("/api/auth/logout")

    guest = client.post("/api/auth/guest", json={}).get_json()["user"]
    assert guest["account_type"] == "guest"
    client.post("/api/phrasebook", json={"phrase_id": "p2"})
    client.post("/api/auth/login", json={
        "email": "owner@example.com",
        "password": "secure-pass-1",
    })

    merged = client.get("/api/phrasebook").get_json()
    assert {phrase["id"] for phrase in merged["phrases"]} == {"p1", "p2"}
    assert client.get("/api/auth/me").get_json()["user"]["account_type"] == "registered"


def test_two_guest_sessions_are_isolated_after_explicit_guest_transitions(client):
    first = client.post("/api/auth/guest", json={}).get_json()["user"]
    client.post("/api/phrasebook", json={"phrase_id": "p1"})

    second_client = client.application.test_client()
    second = second_client.post("/api/auth/guest", json={}).get_json()["user"]
    second_client.post("/api/phrasebook", json={"phrase_id": "p2"})

    assert first["id"] != second["id"]
    assert {p["id"] for p in client.get("/api/phrasebook").get_json()["phrases"]} == {"p1"}
    assert {p["id"] for p in second_client.get("/api/phrasebook").get_json()["phrases"]} == {"p2"}


def test_signout_clears_session_and_me_endpoint_returns_unauthenticated(client):
    client.post("/api/auth/register", json={
        "name": "Signout Tester",
        "email": "signout@example.com",
        "password": "secure-pass-1",
        "language": "en",
    })
    me = client.get("/api/auth/me").get_json()
    assert me["authenticated"] is True
    assert me["user"]["email"] == "signout@example.com"

    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200
    assert logout_res.get_json()["authenticated"] is False

    after = client.get("/api/auth/me").get_json()
    assert after["authenticated"] is False
    assert "user" not in after


def test_guest_account_creation_initializes_empty_progress_and_phrasebook(client):
    res = client.post("/api/auth/guest", json={"language": "hi"})
    assert res.status_code == 200
    user = res.get_json()["user"]
    assert user["account_type"] == "guest"
    assert user["email"] is None
    assert user["preferred_language"] == "hi"

    # Verify empty phrasebook, progress, and revision
    assert client.get("/api/phrasebook").get_json()["count"] == 0
    prog = client.get("/api/progress").get_json()
    assert prog["answered"] == 0
    assert prog["saved_count"] == 0
    assert prog["revision_count"] == 0
    assert client.get("/api/revision").get_json()["count"] == 0


def test_guest_to_account_transfer_preserves_learning_stats_and_revision_queue(client):
    # 1. Start guest
    guest = client.post("/api/auth/guest", json={"language": "en"}).get_json()["user"]
    guest_id = guest["id"]

    # 2. Guest saves phrase and answers incorrectly so phrase enters revision
    assert client.post("/api/phrasebook", json={"phrase_id": "p1"}).status_code == 201
    answer = client.post("/api/practice/answer", json={
        "scenario_id": "s1",
        "option_id": "o2",
        "lang": "en",
    })
    assert answer.status_code == 200
    assert answer.get_json()["is_correct"] is False

    assert client.get("/api/phrasebook").get_json()["count"] == 1
    assert client.get("/api/progress").get_json()["answered"] == 1
    assert client.get("/api/revision").get_json()["count"] >= 1

    # 3. Guest registers account
    reg_res = client.post("/api/auth/register", json={
        "name": "Progress Holder",
        "email": "progress_holder@example.com",
        "password": "secure-pass-1",
        "language": "en",
    })
    assert reg_res.status_code == 201
    reg_user = reg_res.get_json()["user"]
    assert reg_user["id"] != guest_id
    assert reg_user["account_type"] == "registered"

    # 4. Registered user has transferred progress, saved phrase, and revision item
    phrases = client.get("/api/phrasebook").get_json()
    assert phrases["count"] == 1
    assert phrases["phrases"][0]["id"] == "p1"

    prog = client.get("/api/progress").get_json()
    assert prog["answered"] == 1
    assert prog["saved_count"] == 1

    rev = client.get("/api/revision").get_json()
    assert rev["count"] >= 1


def test_return_to_guest_isolation_after_registered_user_session(client):
    # 1. Registered user with data
    client.post("/api/auth/register", json={
        "name": "Owner One",
        "email": "owner_one@example.com",
        "password": "secure-pass-1",
        "language": "en",
    })
    client.post("/api/phrasebook", json={"phrase_id": "p1"})
    assert client.get("/api/phrasebook").get_json()["count"] == 1

    # 2. Sign out
    client.post("/api/auth/logout")

    # 3. Return as guest
    guest = client.post("/api/auth/guest", json={}).get_json()["user"]
    assert guest["account_type"] == "guest"
    assert guest["email"] is None

    # Guest should have completely empty data
    assert client.get("/api/phrasebook").get_json()["count"] == 0
    assert client.get("/api/progress").get_json()["answered"] == 0
    assert client.get("/api/revision").get_json()["count"] == 0

    # 4. Guest saves p2
    client.post("/api/phrasebook", json={"phrase_id": "p2"})
    assert client.get("/api/phrasebook").get_json()["count"] == 1

    # 5. Sign out guest, log back into Owner One
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={
        "email": "owner_one@example.com",
        "password": "secure-pass-1",
    })
    # Owner One still has only their original p1 phrase
    owner_phrases = client.get("/api/phrasebook").get_json()
    assert owner_phrases["count"] == 1
    assert owner_phrases["phrases"][0]["id"] == "p1"


def test_guest_with_progress_login_merges_progress_retaining_higher_scores(client):
    # 1. Registered user with some progress
    client.post("/api/auth/register", json={
        "name": "Initial User",
        "email": "initial@example.com",
        "password": "secure-pass-1",
        "language": "en",
    })
    # Answer 1 correctly
    client.post("/api/practice/answer", json={
        "scenario_id": "s1",
        "option_id": "o1",
        "lang": "en",
    })
    client.post("/api/phrasebook", json={"phrase_id": "p1"})
    client.post("/api/auth/logout")

    # 2. Guest with higher progress
    guest = client.post("/api/auth/guest", json={}).get_json()["user"]
    assert guest["account_type"] == "guest"
    client.post("/api/phrasebook", json={"phrase_id": "p2"})
    # Answer 2 correctly
    client.post("/api/practice/answer", json={
        "scenario_id": "s1",
        "option_id": "o1",
        "lang": "en",
    })
    client.post("/api/practice/answer", json={
        "scenario_id": "s2",
        "option_id": "o1",
        "lang": "en",
    })
    guest_prog = client.get("/api/progress").get_json()
    assert guest_prog["answered"] == 2

    # 3. Guest logs in to Initial User
    login_res = client.post("/api/auth/login", json={
        "email": "initial@example.com",
        "password": "secure-pass-1",
    })
    assert login_res.status_code == 200

    # 4. Check merged progress and phrases
    merged_phrases = client.get("/api/phrasebook").get_json()
    assert {p["id"] for p in merged_phrases["phrases"]} == {"p1", "p2"}
    merged_prog = client.get("/api/progress").get_json()
    assert merged_prog["answered"] >= 2


def test_failed_registration_preserves_guest_session_and_data(client):
    # Register an account first to hold the email
    client.post("/api/auth/register", json={
        "name": "First Account",
        "email": "duplicate@example.com",
        "password": "secure-pass-1",
        "language": "en",
    })
    client.post("/api/auth/logout")

    # Guest session with data
    guest = client.post("/api/auth/guest", json={}).get_json()["user"]
    guest_id = guest["id"]
    client.post("/api/phrasebook", json={"phrase_id": "p1"})

    # Try registering with duplicate email
    fail_res = client.post("/api/auth/register", json={
        "name": "Second Account",
        "email": "duplicate@example.com",
        "password": "secure-pass-1",
        "language": "en",
    })
    assert fail_res.status_code == 400

    # Guest session and phrasebook must still be intact
    me = client.get("/api/auth/me").get_json()
    assert me["authenticated"] is True
    assert me["user"]["id"] == guest_id
    assert me["user"]["account_type"] == "guest"
    assert client.get("/api/phrasebook").get_json()["count"] == 1


def test_failed_login_preserves_guest_session_and_data(client):
    # Guest session with data
    guest = client.post("/api/auth/guest", json={}).get_json()["user"]
    guest_id = guest["id"]
    client.post("/api/phrasebook", json={"phrase_id": "p1"})

    # Try logging in with invalid credentials
    fail_res = client.post("/api/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "wrong-password",
    })
    assert fail_res.status_code == 401

    # Guest session and phrasebook must still be intact
    me = client.get("/api/auth/me").get_json()
    assert me["authenticated"] is True
    assert me["user"]["id"] == guest_id
    assert me["user"]["account_type"] == "guest"
    assert client.get("/api/phrasebook").get_json()["count"] == 1
