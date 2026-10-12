from functools import wraps
from flask import jsonify, session
from backend.models import create_guest_user, get_db_connection


def ensure_guest_session(force_new=False):
    user_id = session.get("user_id")
    if not force_new and session.get("account_type") == "guest" and user_id:
        conn = get_db_connection()
        try:
            guest = conn.execute(
                "SELECT id FROM users WHERE id = ? AND account_type = 'guest'",
                (user_id,),
            ).fetchone()
        finally:
            conn.close()
        if guest:
            return user_id

    # A guest transition must never inherit a registered session or an
    # invalid/stale identity. The old session is discarded before issuing a
    # fresh server-owned guest identity.
    session.clear()
    conn = get_db_connection()
    try:
        user_id = create_guest_user(conn)
    finally:
        conn.close()
    session["user_id"] = user_id
    session["account_type"] = "guest"
    session.permanent = True
    return user_id


def current_user(required=True):
    user_id = session.get("user_id")
    if not user_id:
        if required:
            user_id = ensure_guest_session()
        else:
            return None
    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT id, account_type, name, email, preferred_language FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not user:
            session.clear()
            if required:
                user_id = ensure_guest_session(force_new=True)
                return current_user(required=True)
            return None
        return dict(user)
    finally:
        conn.close()


def require_user(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user(required=True)
        return view(user, *args, **kwargs)
    return wrapped


def auth_error(message, status=401):
    return jsonify({"error": message}), status
