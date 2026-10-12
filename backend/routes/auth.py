from flask import Blueprint, jsonify, request, session
from backend.auth import current_user, ensure_guest_session
from backend.models import get_db_connection
from backend.services.auth_service import (
    authenticate,
    create_account,
    create_account_with_guest,
    normalize_language,
    transfer_guest_data,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/me", methods=["GET"])
def auth_me():
    user = current_user(required=False)
    if not user:
        return jsonify({"authenticated": False}), 200
    return jsonify({"authenticated": True, "user": user}), 200


@auth_bp.route("/api/auth/guest", methods=["POST"])
def create_guest():
    # This endpoint represents an explicit access choice. Always establish a
    # fresh guest identity rather than reusing a registered session.
    user_id = ensure_guest_session(force_new=True)
    language = normalize_language((request.get_json(silent=True) or {}).get("language"))
    if language:
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("UPDATE users SET preferred_language = ? WHERE id = ?", (language, user_id))
        finally:
            conn.close()
    return jsonify({"authenticated": True, "user": current_user()}), 200


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    guest_id = session.get("user_id") if session.get("account_type") == "guest" else None
    create = create_account_with_guest if guest_id else create_account
    args = (
        data.get("name"),
        data.get("email"),
        data.get("password"),
        data.get("language"),
        guest_id,
    ) if guest_id else (
        data.get("name"),
        data.get("email"),
        data.get("password"),
        data.get("language"),
    )
    user, error = create(*args)
    if error:
        return jsonify({"error": error}), 400
    session.clear()
    session["user_id"] = user["id"]
    session["account_type"] = "registered"
    session.permanent = True
    return jsonify({"authenticated": True, "user": user}), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    user = authenticate(data.get("email"), data.get("password"))
    if not user:
        return jsonify({"error": "Email or password is incorrect"}), 401
    guest_id = session.get("user_id") if session.get("account_type") == "guest" else None
    if guest_id:
        transfer_guest_data(guest_id, user["id"])
    session.clear()
    session["user_id"] = user["id"]
    session["account_type"] = "registered"
    session.permanent = True
    return jsonify({"authenticated": True, "user": user}), 200


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"authenticated": False}), 200


@auth_bp.route("/api/auth/language", methods=["POST"])
def update_language():
    user = current_user()
    language = normalize_language((request.get_json(silent=True) or {}).get("language"))
    if not language:
        return jsonify({"error": "Unsupported language"}), 400
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("UPDATE users SET preferred_language = ? WHERE id = ?", (language, user["id"]))
        return jsonify({"user": {**user, "preferred_language": language}}), 200
    finally:
        conn.close()
