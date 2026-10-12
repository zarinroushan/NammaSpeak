from flask import Blueprint, jsonify, request
from backend.services.conversation_engine import ConversationEngine

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/api/ai/chat", methods=["POST"])
def ai_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message text is required"}), 400

    if len(message) > 500:
        return jsonify({"error": "Message exceeds maximum allowed length of 500 characters"}), 400

    context = (data.get("context") or "Everyday Kannada communication").strip()
    history = data.get("history") or []
    lang = (data.get("lang") or "en").lower().strip()

    engine = ConversationEngine()
    reply = engine.chat_turn(context, message, history=history, target_lang=lang)
    return jsonify(reply), 200


@ai_bp.route("/api/ai/explain", methods=["POST"])
def ai_explain():
    data = request.get_json(silent=True) or {}
    phrase = (data.get("phrase") or "").strip()
    if not phrase:
        return jsonify({"error": "Phrase text is required"}), 400

    question = (data.get("question") or "").strip()
    lang = (data.get("lang") or "en").lower().strip()

    engine = ConversationEngine()
    explanation = engine.explain(phrase, question, target_lang=lang)
    return jsonify(explanation), 200
