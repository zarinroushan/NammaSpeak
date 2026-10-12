from flask import Blueprint, jsonify, request
from backend.services.phrase_service import get_phrases, get_phrase_by_id, list_categories
from backend.auth import require_user

phrases_bp = Blueprint("phrases", __name__)


@phrases_bp.route("/api/categories", methods=["GET"])
def get_categories():
    lang = (request.args.get("lang") or "en").lower().strip()
    categories = list_categories(lang=lang)
    return jsonify({"categories": categories}), 200


@phrases_bp.route("/api/phrases", methods=["GET"])
@require_user
def list_phrases(user):
    category = request.args.get("category", "all")
    search = request.args.get("search") or request.args.get("q") or ""
    lang = (request.args.get("lang") or "en").lower().strip()
    phrases = get_phrases(category=category, search=search, lang=lang, user_id=user["id"])
    return jsonify({
        "count": len(phrases),
        "category": category,
        "search": search,
        "lang": lang,
        "phrases": phrases
    }), 200


@phrases_bp.route("/api/phrases/<phrase_id>", methods=["GET"])
@require_user
def get_single_phrase(user, phrase_id):
    lang = (request.args.get("lang") or "en").lower().strip()
    phrase = get_phrase_by_id(phrase_id, lang=lang, user_id=user["id"])
    if not phrase:
        return jsonify({"error": "Phrase not found", "id": phrase_id}), 404
    return jsonify(phrase), 200
