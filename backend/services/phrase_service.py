from backend.models import get_db_connection


CATEGORIES = [
    {"id": "all", "name": "All phrases", "sub": "Comprehensive collection", "emoji": "✳", "bg": "#f7e5d8"},
    {"id": "transport", "name": "Getting around", "sub": "Buses, autos, directions", "emoji": "🚌", "bg": "#e3e9dc"},
    {"id": "food", "name": "Food & dining", "sub": "Cafés, darshinis, orders", "emoji": "☕", "bg": "#f5e8c8"},
    {"id": "shopping", "name": "Shopping & markets", "sub": "Prices, bargaining, items", "emoji": "🛍️", "bg": "#e9e4f4"},
    {"id": "health", "name": "Healthcare & clinic", "sub": "Pharmacy, doctor, emergency", "emoji": "🏥", "bg": "#fce4e4"},
    {"id": "work", "name": "Work & campus", "sub": "Greetings, meetings, office", "emoji": "💼", "bg": "#e0edf4"},
    {"id": "help", "name": "Everyday courtesy", "sub": "Polite requests & help", "emoji": "🤝", "bg": "#f4dfd7"}
]


def list_categories(lang="en"):
    from backend.services.translation_service import translation_service
    if lang == "en" or not translation_service.is_valid_language(lang):
        return CATEGORIES
    
    # Localize category names & subtitles using central translation dictionary
    ui_dict = translation_service.get_ui_translations(lang).get("strings", {})
    localized_cats = []
    for c in CATEGORIES:
        cid = c["id"]
        cat_name = ui_dict.get(f"cat_{cid}", c["name"])
        cat_sub = ui_dict.get(f"cat_{cid}_sub", c["sub"])
        localized_cats.append({
            **c,
            "name": cat_name,
            "sub": cat_sub
        })
    return localized_cats


def get_phrases(category="all", search="", lang="en", user_id="default"):
    from backend.services.translation_service import translation_service
    conn = get_db_connection()
    try:
        query = "SELECT * FROM phrases WHERE 1=1"
        params = []

        if category and category != "all":
            query += " AND category = ?"
            params.append(category)

        if search:
            search_pattern = f"%{search.strip().lower()}%"
            query += " AND (LOWER(kn) LIKE ? OR LOWER(roman) LIKE ? OR LOWER(meaning) LIKE ? OR LOWER(context) LIKE ? OR LOWER(tag) LIKE ?)"
            params.extend([search_pattern] * 5)

        query += " ORDER BY id ASC"
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        
        # Get list of saved phrase IDs to annotate response
        saved_cursor = conn.execute("SELECT phrase_id FROM saved_phrases WHERE user_id = ?", (user_id,))
        saved_set = {r["phrase_id"] for r in saved_cursor.fetchall()}

        result = []
        for r in rows:
            p = dict(r)
            p["is_saved"] = p["id"] in saved_set
            result.append(p)

        # Localize meanings and contexts for the target language (keeping Kannada script intact)
        if lang and lang != "en":
            result = translation_service.localize_phrases(result, lang)

        return result
    finally:
        conn.close()


def get_phrase_by_id(phrase_id, lang="en", user_id="default"):
    from backend.services.translation_service import translation_service
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT * FROM phrases WHERE id = ?", (phrase_id,))
        row = cursor.fetchone()
        if not row:
            return None
        p = dict(row)
        saved = conn.execute("SELECT 1 FROM saved_phrases WHERE user_id = ? AND phrase_id = ?", (user_id, phrase_id)).fetchone()
        p["is_saved"] = bool(saved)

        if lang and lang != "en":
            localized = translation_service.localize_phrases([p], lang)
            if localized:
                p = localized[0]

        return p
    finally:
        conn.close()


def get_saved_phrases(lang="en", user_id="default"):
    from backend.services.translation_service import translation_service
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT p.*, s.saved_at 
            FROM phrases p
            JOIN saved_phrases s ON p.id = s.phrase_id
            WHERE s.user_id = ?
            ORDER BY s.saved_at DESC
        """, (user_id,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            p = dict(r)
            p["is_saved"] = True
            result.append(p)

        if lang and lang != "en":
            result = translation_service.localize_phrases(result, lang)

        return result
    finally:
        conn.close()


def save_phrase(phrase_id, user_id="default"):
    conn = get_db_connection()
    try:
        phrase = conn.execute("SELECT id FROM phrases WHERE id = ?", (phrase_id,))
        if not phrase.fetchone():
            return False, "Phrase not found"

        with conn:
            conn.execute("""
                INSERT OR IGNORE INTO saved_phrases (user_id, phrase_id)
                VALUES (?, ?)
            """, (user_id, phrase_id))
        return True, "Phrase saved successfully"
    finally:
        conn.close()


def unsave_phrase(phrase_id, user_id="default"):
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.execute("DELETE FROM saved_phrases WHERE user_id = ? AND phrase_id = ?", (user_id, phrase_id))
            if cursor.rowcount == 0:
                return False, "Phrase was not in phrasebook"
        return True, "Phrase removed from phrasebook"
    finally:
        conn.close()
