from flask import Blueprint, jsonify
from backend.services.ai_provider import get_ai_provider
from backend.models import get_db_connection

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health", methods=["GET"])
def health_check():
    ai = get_ai_provider()
    db_status = "connected"
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception as e:
        db_status = f"error: {str(e)}"

    return jsonify({
        "status": "ok",
        "app": "NammaSpeak",
        "version": "1.0.0",
        "theme": "Kannada in Everyday Life",
        "ai_provider": ai.get_provider_name(),
        "database": db_status
    }), 200

