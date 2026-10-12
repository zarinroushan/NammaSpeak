import json
from pathlib import Path
from flask import current_app, has_app_context

from backend.config import Config
from backend.db import get_database_connection


TABLE_DDL = (
    """
    CREATE TABLE IF NOT EXISTS phrases (
        id VARCHAR(255) PRIMARY KEY,
        category VARCHAR(255) NOT NULL,
        kn TEXT NOT NULL,
        roman TEXT NOT NULL,
        meaning TEXT NOT NULL,
        context TEXT NOT NULL,
        tag VARCHAR(255) NOT NULL,
        formality VARCHAR(255),
        speech TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scenarios (
        id VARCHAR(255) PRIMARY KEY,
        title TEXT NOT NULL,
        category VARCHAR(255) NOT NULL,
        speaker TEXT NOT NULL,
        speaker_avatar TEXT NOT NULL,
        question TEXT NOT NULL,
        context TEXT NOT NULL,
        prompt TEXT NOT NULL,
        related_phrase_id VARCHAR(255),
        options_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id VARCHAR(255) PRIMARY KEY,
        account_type VARCHAR(32) NOT NULL CHECK (account_type IN ('guest', 'registered')),
        name VARCHAR(80) NOT NULL,
        email VARCHAR(254) UNIQUE,
        password_hash TEXT,
        preferred_language VARCHAR(8),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS saved_phrases (
        user_id VARCHAR(255) NOT NULL,
        phrase_id VARCHAR(255) NOT NULL,
        saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, phrase_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (phrase_id) REFERENCES phrases(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_progress (
        user_id VARCHAR(255) PRIMARY KEY,
        answered_count INTEGER DEFAULT 0,
        correct_count INTEGER DEFAULT 0,
        best_score INTEGER DEFAULT 0,
        last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS phrase_learning_stats (
        user_id VARCHAR(255) NOT NULL,
        phrase_id VARCHAR(255) NOT NULL,
        attempts INTEGER DEFAULT 0,
        correct_count INTEGER DEFAULT 0,
        mistakes INTEGER DEFAULT 0,
        needs_revision INTEGER DEFAULT 0,
        last_attempt_at TIMESTAMP,
        PRIMARY KEY (user_id, phrase_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (phrase_id) REFERENCES phrases(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS translation_cache (
        source_version VARCHAR(255) NOT NULL,
        target_lang VARCHAR(8) NOT NULL,
        translation_key VARCHAR(255) NOT NULL,
        translated_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (source_version, target_lang, translation_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS phrase_translations (
        phrase_id VARCHAR(255) NOT NULL,
        target_lang VARCHAR(8) NOT NULL,
        meaning TEXT NOT NULL,
        context TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (phrase_id, target_lang),
        FOREIGN KEY (phrase_id) REFERENCES phrases(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scenario_translations (
        scenario_id VARCHAR(255) NOT NULL,
        target_lang VARCHAR(8) NOT NULL,
        context TEXT NOT NULL,
        prompt TEXT NOT NULL,
        options_why_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (scenario_id, target_lang),
        FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
    )
    """,
)


def resolve_database_url(db_url=None):
    configured = db_url
    if configured is None and has_app_context():
        configured = current_app.config.get("DATABASE_URL")
    if configured is None:
        configured = Config.DATABASE_URL
    if configured:
        return configured
    raise RuntimeError(
        "DATABASE_URL is required. SQLite files are supported only through "
        "the explicit legacy export/import utility."
    )


def get_db_connection(db_path=None):
    # db_path remains an explicit test/legacy utility argument. It is not
    # consulted for normal application requests.
    if db_path:
        if "://" not in db_path:
            db_path = f"sqlite:///{Path(db_path).resolve().as_posix()}"
        return get_database_connection(db_path)
    return get_database_connection(resolve_database_url())


def init_db(db_url=None):
    """Create the current schema and seed curated data.

    Production calls must provide DATABASE_URL. A filesystem path is accepted
    only by isolated tests and the legacy migration utility.
    """
    connection = get_db_connection(db_url)
    with connection:
        for ddl in TABLE_DDL:
            connection.execute(ddl)
        connection.execute(
            """
            INSERT INTO users (id, account_type, name, preferred_language)
            VALUES (?, 'guest', 'Local learner', 'en')
            ON CONFLICT (id) DO NOTHING
            """,
            ("default",),
        )
        seed_data_if_empty(connection)
    connection.close()


def verify_database(db_url=None):
    connection = get_db_connection(db_url)
    try:
        connection.execute("SELECT 1").fetchone()
        tables = {
            row["table_name"]
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                """
            ).fetchall()
        }
        required = {"phrases", "scenarios", "users", "saved_phrases", "user_progress"}
        missing = required - tables
        if missing:
            raise RuntimeError(
                "Database schema is incomplete. Run `alembic upgrade head` before starting the app. "
                f"Missing tables: {', '.join(sorted(missing))}"
            )
    finally:
        connection.close()


def seed_database(db_url=None):
    connection = get_db_connection(db_url)
    try:
        with connection:
            seed_data_if_empty(connection)
    finally:
        connection.close()


def seed_data_if_empty(conn):
    data_dir = Path(__file__).resolve().parent / "data"
    phrases_file = data_dir / "seed_phrases.json"
    scenarios_file = data_dir / "seed_scenarios.json"

    if phrases_file.exists():
        with open(phrases_file, "r", encoding="utf-8") as file:
            for phrase in json.load(file):
                conn.execute(
                    """
                    INSERT INTO phrases
                        (id, category, kn, roman, meaning, context, tag, formality, speech)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        phrase["id"], phrase["category"], phrase["kn"], phrase["roman"],
                        phrase["meaning"], phrase["context"], phrase["tag"],
                        phrase.get("formality", "Standard"), phrase["speech"],
                    ),
                )

    if scenarios_file.exists():
        with open(scenarios_file, "r", encoding="utf-8") as file:
            for scenario in json.load(file):
                conn.execute(
                    """
                    INSERT INTO scenarios
                        (id, title, category, speaker, speaker_avatar, question, context,
                         prompt, related_phrase_id, options_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        scenario["id"], scenario["title"], scenario["category"],
                        scenario["speaker"], scenario.get("speaker_avatar", "💬"),
                        scenario["question"], scenario["context"], scenario["prompt"],
                        scenario.get("related_phrase_id"),
                        json.dumps(scenario["options"], ensure_ascii=False),
                    ),
                )

    conn.execute(
        """
        INSERT INTO user_progress (user_id, answered_count, correct_count, best_score)
        VALUES (?, 0, 0, 0)
        ON CONFLICT (user_id) DO NOTHING
        """,
        ("default",),
    )


def create_guest_user(conn):
    import uuid

    user_id = f"guest_{uuid.uuid4().hex}"
    conn.execute(
        """
        INSERT INTO users (id, account_type, name, preferred_language)
        VALUES (?, 'guest', 'Guest learner', NULL)
        """,
        (user_id,),
    )
    return user_id
