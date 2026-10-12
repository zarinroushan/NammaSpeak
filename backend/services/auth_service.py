import re
import uuid
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
from backend.models import get_db_connection

SUPPORTED_LANGUAGES = {"en", "hi", "bn", "ta", "te"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_language(value):
    value = (value or "").lower().strip()
    return value if value in SUPPORTED_LANGUAGES else None


def validate_registration(name, email, password, language):
    name = (name or "").strip()
    email = (email or "").strip().lower()
    if not name or len(name) > 80:
        return None, "Name is required and must be 80 characters or fewer"
    if not EMAIL_RE.match(email) or len(email) > 254:
        return None, "A valid email address is required"
    if len(password or "") < 8:
        return None, "Password must be at least 8 characters"
    language = normalize_language(language)
    if not language:
        return None, "A supported preferred language is required"
    return {"name": name, "email": email, "password": password, "language": language}, None


def create_account(name, email, password, language):
    data, error = validate_registration(name, email, password, language)
    if error:
        return None, error
    conn = get_db_connection()
    try:
        with conn:
            return _create_account_on_connection(conn, data)
    finally:
        conn.close()


def create_account_with_guest(name, email, password, language, guest_id):
    data, error = validate_registration(name, email, password, language)
    if error:
        return None, error
    conn = get_db_connection()
    try:
        with conn:
            user, error = _create_account_on_connection(conn, data)
            if error:
                return None, error
            _transfer_guest_data_on_connection(conn, guest_id, user["id"])
            return user, None
    finally:
        conn.close()


def _create_account_on_connection(conn, data):
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (data["email"],)).fetchone()
    if existing:
        return None, "An account with that email already exists"
    try:
        conn.execute("""
            INSERT INTO users (id, account_type, name, email, password_hash, preferred_language)
            VALUES (?, 'registered', ?, ?, ?, ?)
        """, (
            f"user_{uuid.uuid4().hex}",
            data["name"],
            data["email"],
            generate_password_hash(data["password"]),
            data["language"],
        ))
    except IntegrityError:
        return None, "An account with that email already exists"
    user = conn.execute("""
        SELECT id, account_type, name, email, preferred_language
        FROM users WHERE email = ?
    """, (data["email"],)).fetchone()
    return dict(user), None


def authenticate(email, password):
    email = (email or "").strip().lower()
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not user["password_hash"] or not check_password_hash(user["password_hash"], password or ""):
            return None
        return {
            "id": user["id"],
            "account_type": user["account_type"],
            "name": user["name"],
            "email": user["email"],
            "preferred_language": user["preferred_language"],
        }
    finally:
        conn.close()


def transfer_guest_data(guest_id, account_id):
    if not guest_id or guest_id == account_id:
        return
    conn = get_db_connection()
    try:
        with conn:
            _transfer_guest_data_on_connection(conn, guest_id, account_id)
    finally:
        conn.close()


def _transfer_guest_data_on_connection(conn, guest_id, account_id):
    """Merge guest data transactionally, retaining the larger progress totals."""
    if not guest_id or guest_id == account_id:
        return

    guest = conn.execute(
        "SELECT id FROM users WHERE id = ? AND account_type = 'guest'",
        (guest_id,),
    ).fetchone()
    if not guest:
        return

    conn.execute("""
        INSERT OR IGNORE INTO saved_phrases (user_id, phrase_id, saved_at)
        SELECT ?, phrase_id, saved_at FROM saved_phrases WHERE user_id = ?
    """, (account_id, guest_id))
    conn.execute("""
        INSERT OR IGNORE INTO phrase_learning_stats
            (user_id, phrase_id, attempts, correct_count, mistakes, needs_revision, last_attempt_at)
        SELECT ?, phrase_id, attempts, correct_count, mistakes, needs_revision, last_attempt_at
        FROM phrase_learning_stats WHERE user_id = ?
    """, (account_id, guest_id))
    conn.execute("""
        INSERT INTO user_progress (user_id, answered_count, correct_count, best_score, last_active_at)
        SELECT ?, answered_count, correct_count, best_score, last_active_at
        FROM user_progress WHERE user_id = ?
        ON CONFLICT(user_id) DO UPDATE SET
            answered_count = CASE WHEN COALESCE(user_progress.answered_count, 0) > COALESCE(excluded.answered_count, 0)
                                  THEN COALESCE(user_progress.answered_count, 0)
                                  ELSE COALESCE(excluded.answered_count, 0) END,
            correct_count = CASE WHEN COALESCE(user_progress.correct_count, 0) > COALESCE(excluded.correct_count, 0)
                                 THEN COALESCE(user_progress.correct_count, 0)
                                 ELSE COALESCE(excluded.correct_count, 0) END,
            best_score = CASE WHEN COALESCE(user_progress.best_score, 0) > COALESCE(excluded.best_score, 0)
                              THEN COALESCE(user_progress.best_score, 0)
                              ELSE COALESCE(excluded.best_score, 0) END,
            last_active_at = excluded.last_active_at
    """, (account_id, guest_id))
    conn.execute("DELETE FROM saved_phrases WHERE user_id = ?", (guest_id,))
    conn.execute("DELETE FROM phrase_learning_stats WHERE user_id = ?", (guest_id,))
    conn.execute("DELETE FROM user_progress WHERE user_id = ?", (guest_id,))
    conn.execute("DELETE FROM users WHERE id = ? AND account_type = 'guest'", (guest_id,))
