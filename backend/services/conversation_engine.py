from backend.services.ai_provider import get_ai_provider
from backend.services.revision_service import get_all_scenarios, get_scenario_by_id, validate_and_record_answer, get_adaptive_revision_list


class ConversationEngine:
    """Coordinates practice dialogues, answer evaluations, and AI interactions."""

    def __init__(self):
        self.ai_provider = get_ai_provider()

    def list_scenarios(self):
        return get_all_scenarios()

    def get_scenario(self, scenario_id):
        return get_scenario_by_id(scenario_id)

    def evaluate_response(self, scenario_id, option_id, user_id="default"):
        return validate_and_record_answer(scenario_id, option_id, user_id=user_id)

    def get_revision_plan(self):
        return get_adaptive_revision_list()

    def chat_turn(self, context, message, history=None, target_lang="en"):
        return self.ai_provider.generate_reply(
            scenario_context=context or "Everyday life in Bengaluru and Karnataka",
            user_message=message,
            history=history or [],
            target_lang=target_lang
        )

    def explain(self, phrase, question="", target_lang="en"):
        return self.ai_provider.explain_phrase(phrase, question, target_lang=target_lang)
