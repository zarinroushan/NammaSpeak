from flask import Blueprint, jsonify, request, Response

from backend.services.speech_service import ElevenLabsSpeechService, SpeechGenerationError

speech_bp = Blueprint("speech", __name__)


@speech_bp.route("/api/speech/kannada", methods=["POST"])
def generate_kannada_speech():
    data = request.get_json(silent=True) or {}
    phrase = data.get("phrase")
    speed = data.get("speed", 1.0)
    if not isinstance(phrase, str) or not phrase.strip():
        return jsonify({"error": "A Kannada phrase is required.", "code": "invalid_input"}), 400
    if len(phrase.strip()) > 500:
        return jsonify({"error": "The Kannada phrase is too long.", "code": "invalid_input"}), 400

    try:
        audio = ElevenLabsSpeechService().generate(phrase, speed=speed)
        return Response(audio, mimetype="audio/mpeg", headers={"Cache-Control": "private, max-age=3600"})
    except SpeechGenerationError as exc:
        status = 400 if exc.code == "invalid_input" else 503
        return jsonify({"error": exc.message, "code": exc.code}), status
