import os
import sys
from pathlib import Path
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

# Ensure project root is in Python sys.path
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import Config
from backend.models import init_db, seed_database, verify_database
from backend.routes.health import health_bp
from backend.routes.phrases import phrases_bp
from backend.routes.practice import practice_bp
from backend.routes.progress import progress_bp
from backend.routes.ai import ai_bp
from backend.routes.translations import translations_bp
from backend.routes.speech import speech_bp
from backend.routes.auth import auth_bp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=Config.SECRET_KEY,
        DATABASE_URL=Config.DATABASE_URL,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=Config.SESSION_COOKIE_SECURE,
        PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 365,
    )

    if test_config:
        app.config.update(test_config)
        if not app.config.get("DATABASE_URL") and app.config.get("DATABASE_PATH"):
            path = Path(app.config["DATABASE_PATH"]).resolve().as_posix()
            app.config["DATABASE_URL"] = f"sqlite:///{path}"

    # Enable CORS for local API access
    CORS(app)

    database_url = app.config.get("DATABASE_URL")
    if database_url and database_url.startswith("postgresql"):
        verify_database(database_url)
        seed_database(database_url)
    else:
        # SQLite is intentionally limited to explicit test configurations.
        if not app.config.get("TESTING") and os.getenv("NAMMASPEAK_TESTING") != "1":
            raise RuntimeError("A PostgreSQL DATABASE_URL is required for runtime application access")
        init_db(database_url)

    # Register API Blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(phrases_bp)
    app.register_blueprint(practice_bp)
    app.register_blueprint(progress_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(translations_bp)
    app.register_blueprint(speech_bp)
    app.register_blueprint(auth_bp)

    frontend_dir = PROJECT_ROOT / "frontend"

    # Serve Single Page Application and static files
    @app.route("/")
    def serve_index():
        # First check root index.html, then frontend/index.html
        if (PROJECT_ROOT / "index.html").exists():
            return send_from_directory(PROJECT_ROOT, "index.html")
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/frontend/<path:filename>")
    def serve_frontend_assets(filename):
        return send_from_directory(frontend_dir, filename)

    @app.route("/<path:filename>")
    def serve_root_fallback(filename):
        # Prevent intercepting API routes
        if filename.startswith("api/"):
            return jsonify({"error": "API route not found", "path": filename}), 404

        # Check in frontend directory (e.g. styles.css, app.js, api.js)
        if (frontend_dir / filename).exists():
            return send_from_directory(frontend_dir, filename)

        # Check in project root
        if (PROJECT_ROOT / filename).exists():
            return send_from_directory(PROJECT_ROOT, filename)

        return jsonify({"error": "File not found", "path": filename}), 404

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def handle_server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    port = Config.PORT
    debug = Config.DEBUG
    print(f"[NammaSpeak] Server running on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
