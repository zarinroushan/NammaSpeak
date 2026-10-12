from flask import Blueprint, jsonify, request
from backend.services.revision_service import get_all_scenarios, get_scenario_by_id, validate_and_record_answer
from backend.auth import require_user

practice_bp = Blueprint("practice", __name__)


@practice_bp.route("/api/practice/scenarios", methods=["GET"])
def list_scenarios():
    lang = (request.args.get("lang") or "en").lower().strip()
    scenarios = get_all_scenarios(lang=lang)
    return jsonify({
        "count": len(scenarios),
        "lang": lang,
        "scenarios": scenarios
    }), 200


@practice_bp.route("/api/practice/scenarios/<scenario_id>", methods=["GET"])
def get_scenario(scenario_id):
    lang = (request.args.get("lang") or "en").lower().strip()
    scenario = get_scenario_by_id(scenario_id, lang=lang)
    if not scenario:
        return jsonify({"error": "Scenario not found", "id": scenario_id}), 404
    return jsonify(scenario), 200


@practice_bp.route("/api/practice/answer", methods=["POST"])
@require_user
def submit_answer(user):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    scenario_id = data.get("scenario_id")
    option_id = data.get("option_id")
    user_id = user["id"]
    lang = (data.get("lang") or "en").lower().strip()

    if not scenario_id or not option_id:
        return jsonify({"error": "Both scenario_id and option_id are required"}), 400

    result, err = validate_and_record_answer(scenario_id, option_id, user_id=user_id, lang=lang)
    if err:
        return jsonify({"error": err}), 404 if "not found" in err.lower() else 400

    return jsonify(result), 200
