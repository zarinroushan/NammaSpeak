import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from backend.config import Config


def get_db_connection(db_path=None):
    path = db_path or Config.DATABASE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path=None):
    """Creates schema and seeds initial phrase and scenario data idempotently."""
    conn = get_db_connection(db_path)
    with conn:
        # Phrases table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS phrases (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                kn TEXT NOT NULL,
                roman TEXT NOT NULL,
                meaning TEXT NOT NULL,
                context TEXT NOT NULL,
                tag TEXT NOT NULL,
                formality TEXT,
                speech TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Scenarios table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenarios (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                speaker TEXT NOT NULL,
                speaker_avatar TEXT NOT NULL,
                question TEXT NOT NULL,
                context TEXT NOT NULL,
                prompt TEXT NOT NULL,
                related_phrase_id TEXT,
                options_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Phrasebook (saved phrases)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_phrases (
                phrase_id TEXT PRIMARY KEY,
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (phrase_id) REFERENCES phrases(id) ON DELETE CASCADE
            );
        """)

        # User progress tracking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                user_id TEXT PRIMARY KEY,
                answered_count INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                best_score INTEGER DEFAULT 0,
                last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Phrase-level learning stats (adaptive revision)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS phrase_learning_stats (
                phrase_id TEXT PRIMARY KEY,
                attempts INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                mistakes INTEGER DEFAULT 0,
                needs_revision INTEGER DEFAULT 0,
                last_attempt_at TIMESTAMP,
                FOREIGN KEY (phrase_id) REFERENCES phrases(id) ON DELETE CASCADE
            );
        """)

        # Central UI translation cache keyed by source_version, target_lang, translation_key
        conn.execute("""
            CREATE TABLE IF NOT EXISTS translation_cache (
                source_version TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                translation_key TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (source_version, target_lang, translation_key)
            );
        """)

        # Multilingual phrase meanings & usage context
        conn.execute("""
            CREATE TABLE IF NOT EXISTS phrase_translations (
                phrase_id TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                meaning TEXT NOT NULL,
                context TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (phrase_id, target_lang),
                FOREIGN KEY (phrase_id) REFERENCES phrases(id) ON DELETE CASCADE
            );
        """)

        # Multilingual scenario context, prompts & explanations
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenario_translations (
                scenario_id TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                context TEXT NOT NULL,
                prompt TEXT NOT NULL,
                options_why_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (scenario_id, target_lang),
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
            );
        """)

    # Seed data
    seed_data_if_empty(conn)
    conn.close()


def seed_data_if_empty(conn):
    data_dir = Path(__file__).resolve().parent / "data"
    phrases_file = data_dir / "seed_phrases.json"
    scenarios_file = data_dir / "seed_scenarios.json"

    # Seed phrases
    if phrases_file.exists():
        with open(phrases_file, "r", encoding="utf-8") as f:
            phrases = json.load(f)
            for p in phrases:
                conn.execute("""
                    INSERT OR IGNORE INTO phrases (id, category, kn, roman, meaning, context, tag, formality, speech)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p["id"],
                    p["category"],
                    p["kn"],
                    p["roman"],
                    p["meaning"],
                    p["context"],
                    p["tag"],
                    p.get("formality", "Standard"),
                    p["speech"]
                ))

    # Seed scenarios
    if scenarios_file.exists():
        with open(scenarios_file, "r", encoding="utf-8") as f:
            scenarios = json.load(f)
            for s in scenarios:
                conn.execute("""
                    INSERT OR IGNORE INTO scenarios (id, title, category, speaker, speaker_avatar, question, context, prompt, related_phrase_id, options_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s["id"],
                    s["title"],
                    s["category"],
                    s["speaker"],
                    s.get("speaker_avatar", "💬"),
                    s["question"],
                    s["context"],
                    s["prompt"],
                    s.get("related_phrase_id"),
                    json.dumps(s["options"], ensure_ascii=False)
                ))

    # Ensure default user row exists in user_progress
    conn.execute("""
        INSERT OR IGNORE INTO user_progress (user_id, answered_count, correct_count, best_score, last_active_at)
        VALUES ('default', 0, 0, 0, CURRENT_TIMESTAMP)
    """)
    conn.commit()

