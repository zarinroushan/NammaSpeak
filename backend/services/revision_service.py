import json
from datetime import datetime, timezone
from backend.models import get_db_connection


def get_all_scenarios(lang="en"):
    from backend.services.translation_service import translation_service
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT * FROM scenarios ORDER BY id ASC")
        rows = cursor.fetchall()
        scenarios = []
        for r in rows:
            s = dict(r)
            s["options"] = json.loads(s["options_json"])
            del s["options_json"]
            scenarios.append(s)

        if lang and lang != "en":
            scenarios = translation_service.localize_scenarios(scenarios, lang)

        return scenarios
    finally:
        conn.close()


def get_scenario_by_id(scenario_id, lang="en"):
    from backend.services.translation_service import translation_service
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,))
        row = cursor.fetchone()
        if not row:
            return None
        s = dict(row)
        s["options"] = json.loads(s["options_json"])
        del s["options_json"]

        if lang and lang != "en":
            localized = translation_service.localize_scenarios([s], lang)
            if localized:
                s = localized[0]

        return s
    finally:
        conn.close()


def validate_and_record_answer(scenario_id, option_id, user_id="default", lang="en"):
    scenario = get_scenario_by_id(scenario_id, lang=lang)
    if not scenario:
        return None, "Scenario not found"

    selected_option = None
    correct_option = None
    for opt in scenario["options"]:
        if opt["id"] == option_id:
            selected_option = opt
        if opt.get("correct"):
            correct_option = opt

    if not selected_option:
        return None, "Invalid option ID"

    is_correct = bool(selected_option.get("correct", False))
    why = selected_option.get("why", "")
    related_phrase_id = scenario.get("related_phrase_id")

    # Update database progress and phrase learning stats
    conn = get_db_connection()
    try:
        with conn:
            # Update user_progress
            prog = conn.execute("SELECT * FROM user_progress WHERE user_id = ?", (user_id,)).fetchone()
            if not prog:
                conn.execute("""
                    INSERT INTO user_progress (user_id, answered_count, correct_count, best_score, last_active_at)
                    VALUES (?, 1, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, 1 if is_correct else 0, 100 if is_correct else 0))
            else:
                new_answered = prog["answered_count"] + 1
                new_correct = prog["correct_count"] + (1 if is_correct else 0)
                current_session_score = round((new_correct / new_answered) * 100)
                new_best = max(prog["best_score"], current_session_score)
                conn.execute("""
                    UPDATE user_progress 
                    SET answered_count = ?, correct_count = ?, best_score = ?, last_active_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (new_answered, new_correct, new_best, user_id))

            # Update phrase learning stats (adaptive revision)
            if related_phrase_id:
                stat = conn.execute("SELECT * FROM phrase_learning_stats WHERE user_id = ? AND phrase_id = ?", (user_id, related_phrase_id)).fetchone()
                if not stat:
                    conn.execute("""
                        INSERT INTO phrase_learning_stats (user_id, phrase_id, attempts, correct_count, mistakes, needs_revision, last_attempt_at)
                        VALUES (?, ?, 1, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        user_id,
                        related_phrase_id,
                        1 if is_correct else 0,
                        0 if is_correct else 1,
                        0 if is_correct else 1
                    ))
                else:
                    new_attempts = stat["attempts"] + 1
                    new_stat_correct = stat["correct_count"] + (1 if is_correct else 0)
                    new_mistakes = stat["mistakes"] + (0 if is_correct else 1)
                    needs_rev = 0 if (is_correct and stat["mistakes"] <= 1) else (1 if not is_correct else stat["needs_revision"])
                    conn.execute("""
                        UPDATE phrase_learning_stats
                        SET attempts = ?, correct_count = ?, mistakes = ?, needs_revision = ?, last_attempt_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND phrase_id = ?
                    """, (new_attempts, new_stat_correct, new_mistakes, needs_rev, user_id, related_phrase_id))

        result = {
            "scenario_id": scenario_id,
            "selected_option_id": option_id,
            "is_correct": is_correct,
            "why": why,
            "correct_option": correct_option,
            "related_phrase_id": related_phrase_id,
            "lang": lang
        }
        return result, None
    finally:
        conn.close()


def get_user_progress(user_id="default"):
    conn = get_db_connection()
    try:
        prog = conn.execute("SELECT * FROM user_progress WHERE user_id = ?", (user_id,)).fetchone()
        answered = prog["answered_count"] if prog else 0
        correct = prog["correct_count"] if prog else 0
        best = prog["best_score"] if prog else 0
        accuracy = round((correct / answered * 100)) if answered > 0 else 0

        saved_count = conn.execute("SELECT COUNT(*) AS c FROM saved_phrases WHERE user_id = ?", (user_id,)).fetchone()["c"]
        revision_count = conn.execute("SELECT COUNT(*) AS c FROM phrase_learning_stats WHERE user_id = ? AND needs_revision > 0", (user_id,)).fetchone()["c"]
        mastered_count = conn.execute("SELECT COUNT(*) AS c FROM phrase_learning_stats WHERE user_id = ? AND attempts > 0 AND mistakes = 0", (user_id,)).fetchone()["c"]

        # Category level breakdown
        category_stats_cursor = conn.execute("""
            SELECT p.category, 
                   COUNT(p.id) as total_phrases,
                   SUM(CASE WHEN s.attempts > 0 THEN 1 ELSE 0 END) as practiced,
                   SUM(CASE WHEN s.mistakes = 0 AND s.attempts > 0 THEN 1 ELSE 0 END) as mastered
            FROM phrases p
            LEFT JOIN phrase_learning_stats s ON p.id = s.phrase_id AND s.user_id = ?
            GROUP BY p.category
        """, (user_id,))
        category_breakdown = [dict(r) for r in category_stats_cursor.fetchall()]

        return {
            "answered": answered,
            "correct": correct,
            "accuracy": accuracy,
            "best_score": best,
            "saved_count": saved_count,
            "revision_count": revision_count,
            "mastered_count": mastered_count,
            "category_breakdown": category_breakdown
        }
    finally:
        conn.close()


def get_adaptive_revision_list(lang="en", user_id="default"):
    from backend.services.translation_service import translation_service
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT p.*, s.attempts, s.mistakes, s.correct_count, s.needs_revision, s.last_attempt_at
            FROM phrases p
            JOIN phrase_learning_stats s ON p.id = s.phrase_id AND s.user_id = ?
            WHERE s.needs_revision > 0 OR s.mistakes > 0
            ORDER BY s.mistakes DESC, s.last_attempt_at DESC
        """, (user_id,))
        rows = [dict(r) for r in cursor.fetchall()]

        if lang and lang != "en":
            rows = translation_service.localize_phrases(rows, lang)

        return rows
    finally:
        conn.close()


def mark_phrase_revised(phrase_id, user_id="default"):
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                UPDATE phrase_learning_stats
                SET needs_revision = 0
                WHERE user_id = ? AND phrase_id = ?
            """, (user_id, phrase_id))
        return True
    finally:
        conn.close()
