from flask import Blueprint, jsonify, request
from backend.services.translation_service import translation_service, SUPPORTED_LANGUAGES

translations_bp = Blueprint("translations", __name__)


@translations_bp.route("/api/translations/languages", methods=["GET"])
def list_languages():
    """Returns list of supported languages for interface localization."""
    return jsonify({
        "languages": translation_service.get_supported_languages()
    }), 200


@translations_bp.route("/api/translations/<target_lang>", methods=["GET"])
def get_ui_translations(target_lang):
    """Returns complete validated and cached UI dictionary for the given target language."""
    target_lang = (target_lang or "en").lower().strip()
    if not translation_service.is_valid_language(target_lang):
        return jsonify({
            "error": f"Unsupported language '{target_lang}'. Supported: {', '.join(SUPPORTED_LANGUAGES.keys())}"
        }), 400

    data = translation_service.get_ui_translations(target_lang)
    return jsonify(data), 200


@translations_bp.route("/api/translations/batch", methods=["POST"])
def translate_batch():
    """Validates and translates a custom batch of strings."""
    payload = request.get_json(silent=True) or {}
    target_lang = (payload.get("target_lang") or "en").lower().strip()
    strings_to_translate = payload.get("strings")

    if not translation_service.is_valid_language(target_lang):
        return jsonify({
            "error": f"Unsupported target language '{target_lang}'."
        }), 400

    if not isinstance(strings_to_translate, dict) or not strings_to_translate:
        return jsonify({
            "error": "'strings' must be a non-empty JSON object."
        }), 400

    # If target is English, return strings as-is
    if target_lang == "en":
        return jsonify({
            "lang": "en",
            "translated": strings_to_translate,
            "is_fallback": False,
            "source": "cache"
        }), 200

    translated, success = translation_service.translate_batch_with_ai(target_lang, strings_to_translate)
    if success and translated:
        return jsonify({
            "lang": target_lang,
            "translated": translated,
            "is_fallback": False,
            "source": "gemini"
        }), 200

    # Fallback response
    return jsonify({
        "lang": target_lang,
        "translated": strings_to_translate,
        "is_fallback": True,
        "source": "offline",
        "notice": "Translation provider unavailable; returned source strings."
    }), 200
