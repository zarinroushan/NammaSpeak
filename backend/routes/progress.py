from flask import Blueprint, jsonify, request
from backend.services.phrase_service import get_saved_phrases, save_phrase, unsave_phrase
from backend.services.revision_service import get_user_progress, get_adaptive_revision_list, mark_phrase_revised
from backend.models import get_db_connection

progress_bp = Blueprint("progress", __name__)


@progress_bp.route("/api/progress", methods=["GET"])
def get_progress():
    user_id = request.args.get("user_id", "default")
    prog = get_user_progress(user_id=user_id)
    return jsonify(prog), 200


@progress_bp.route("/api/progress", methods=["POST"])
def update_progress():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "default")
    action = data.get("action")

    if action == "reset":
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("UPDATE user_progress SET answered_count = 0, correct_count = 0, best_score = 0 WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM phrase_learning_stats")
            return jsonify({"status": "progress reset"}), 200
        finally:
            conn.close()

    prog = get_user_progress(user_id=user_id)
    return jsonify(prog), 200


@progress_bp.route("/api/phrasebook", methods=["GET"])
def list_phrasebook():
    lang = (request.args.get("lang") or "en").lower().strip()
    saved = get_saved_phrases(lang=lang)
    return jsonify({
        "count": len(saved),
        "lang": lang,
        "phrases": saved
    }), 200


@progress_bp.route("/api/phrasebook", methods=["POST"])
def add_to_phrasebook():
    data = request.get_json(silent=True)
    if not data or "phrase_id" not in data:
        return jsonify({"error": "phrase_id is required"}), 400

    phrase_id = data.get("phrase_id")
    success, message = save_phrase(phrase_id)
    if not success:
        return jsonify({"error": message}), 404

    return jsonify({"status": "saved", "phrase_id": phrase_id, "message": message}), 201


@progress_bp.route("/api/phrasebook/<phrase_id>", methods=["DELETE"])
def remove_from_phrasebook(phrase_id):
    success, message = unsave_phrase(phrase_id)
    if not success:
        return jsonify({"error": message, "phrase_id": phrase_id}), 404

    return jsonify({"status": "removed", "phrase_id": phrase_id, "message": message}), 200


@progress_bp.route("/api/revision", methods=["GET"])
def list_revision_queue():
    lang = (request.args.get("lang") or "en").lower().strip()
    items = get_adaptive_revision_list(lang=lang)
    return jsonify({
        "count": len(items),
        "lang": lang,
        "phrases": items
    }), 200


@progress_bp.route("/api/revision/resolve", methods=["POST"])
def resolve_revision_phrase():
    data = request.get_json(silent=True) or {}
    phrase_id = data.get("phrase_id")
    if not phrase_id:
        return jsonify({"error": "phrase_id is required"}), 400

    mark_phrase_revised(phrase_id)
    return jsonify({"status": "resolved", "phrase_id": phrase_id}), 200
