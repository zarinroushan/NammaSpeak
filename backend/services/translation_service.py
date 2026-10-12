import json
import logging
import hashlib
from pathlib import Path
from backend.config import Config
from backend.models import get_db_connection
from backend.services.ai_provider import get_ai_provider

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "en": {"code": "en", "name": "English", "native": "English"},
    "hi": {"code": "hi", "name": "Hindi", "native": "हिन्दी"},
    "bn": {"code": "bn", "name": "Bengali", "native": "বাংলা"},
    "ta": {"code": "ta", "name": "Tamil", "native": "தமிழ்"},
    "te": {"code": "te", "name": "Telugu", "native": "తెలుగు"}
}

# Load source English dictionary
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EN_STRINGS_PATH = DATA_DIR / "en_ui_strings.json"
OFFLINE_TRANSLATIONS_PATH = DATA_DIR / "offline_translations.json"

_EN_STRINGS = {}
if EN_STRINGS_PATH.exists():
    with open(EN_STRINGS_PATH, "r", encoding="utf-8") as f:
        _EN_STRINGS = json.load(f)

_OFFLINE_TRANSLATIONS = {}
if OFFLINE_TRANSLATIONS_PATH.exists():
    with open(OFFLINE_TRANSLATIONS_PATH, "r", encoding="utf-8") as f:
        _OFFLINE_TRANSLATIONS = json.load(f)

SOURCE_VERSION = hashlib.sha256(
    json.dumps(_EN_STRINGS, ensure_ascii=False, sort_keys=True).encode("utf-8")
).hexdigest()[:16]


class TranslationService:
    """Dedicated service for UI string localization, validation, and SQLite caching."""

    def __init__(self):
        self.source_version = SOURCE_VERSION
        self.source_strings = dict(_EN_STRINGS)
        self.offline_translations = dict(_OFFLINE_TRANSLATIONS)

    @staticmethod
    def get_supported_languages():
        return list(SUPPORTED_LANGUAGES.values())

    @staticmethod
    def is_valid_language(lang_code: str) -> bool:
        return bool(lang_code and lang_code.lower() in SUPPORTED_LANGUAGES)

    def get_source_strings(self) -> dict:
        return dict(self.source_strings)

    def validate_translation_payload(self, target_keys: set, candidate_data: any) -> tuple[bool, dict, list]:
        """Validates that candidate_data is a dict containing non-empty string values for target_keys.
        
        Returns:
            (is_valid, validated_dict, errors)
        """
        errors = []
        if not isinstance(candidate_data, dict):
            return False, {}, ["Payload must be a JSON object mapping keys to translated strings."]

        validated = {}
        missing_keys = []
        type_errors = []
        unexpected_keys = set(candidate_data) - target_keys

        for key in target_keys:
            if key not in candidate_data:
                missing_keys.append(key)
                continue

            val = candidate_data[key]
            if not isinstance(val, str) or not val.strip():
                type_errors.append(f"Key '{key}' must be a non-empty string, got {type(val).__name__}")
                continue

            validated[key] = val.strip()

        if missing_keys:
            errors.append(f"Missing {len(missing_keys)} translation keys: {', '.join(missing_keys[:5])}...")
        if type_errors:
            errors.extend(type_errors[:5])
        if unexpected_keys:
            errors.append(f"Unexpected translation keys: {', '.join(sorted(unexpected_keys)[:5])}...")

        is_valid = len(errors) == 0 and len(validated) == len(target_keys)
        return is_valid, validated, errors

    def get_cached_strings(self, target_lang: str) -> dict:
        """Retrieves cached translations from SQLite for target_lang."""
        conn = get_db_connection()
        try:
            cursor = conn.execute("""
                SELECT translation_key, translated_text 
                FROM translation_cache
                WHERE source_version = ? AND target_lang = ?
            """, (self.source_version, target_lang))
            return {row["translation_key"]: row["translated_text"] for row in cursor.fetchall()}
        finally:
            conn.close()

    def cache_strings(self, target_lang: str, translations: dict):
        """Persists validated translations into SQLite translation_cache."""
        if not translations:
            return
        conn = get_db_connection()
        try:
            with conn:
                for key, text in translations.items():
                    conn.execute("""
                        INSERT INTO translation_cache
                        (source_version, target_lang, translation_key, translated_text, created_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT (source_version, target_lang, translation_key)
                        DO UPDATE SET translated_text = EXCLUDED.translated_text,
                                      created_at = EXCLUDED.created_at
                    """, (self.source_version, target_lang, key, text))
        finally:
            conn.close()

    def translate_batch_with_ai(self, target_lang: str, batch: dict) -> tuple[dict, bool]:
        """Attempts batch translation with configured Gemini provider.
        
        Returns:
            (translated_dict, success_bool)
        """
        provider = get_ai_provider()
        if (
            Config.AI_PROVIDER != "gemini"
            or not Config.GEMINI_API_KEY
            or not callable(getattr(provider, "_call_gemini", None))
        ):
            return {}, False

        target_info = SUPPORTED_LANGUAGES.get(target_lang, {"name": target_lang})
        lang_name = target_info["name"]

        prompt = f"""
You are NammaSpeak's official UI translator.
Translate the following dictionary of interface strings from English into {lang_name}.

CRITICAL REQUIREMENTS:
1. Return strictly valid JSON with no markdown formatting, no code fences, and no surrounding commentary.
2. Preserve all translation keys EXACTLY as given. Do not rename, drop, or invent keys.
3. Every value must be a natural, respectful, accurate translation in {lang_name} suitable for an Indian language learning app.
4. Do NOT translate technical placeholder tokens, numbers, or brand names like 'NammaSpeak'.
5. All values must be strings.

Input dictionary to translate:
{json.dumps(batch, ensure_ascii=False, indent=2)}
"""
        try:
            raw_text = provider._call_gemini(prompt)
            cleaned = raw_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            parsed = json.loads(cleaned.strip())

            is_valid, validated, errors = self.validate_translation_payload(set(batch.keys()), parsed)
            if is_valid:
                return validated, True
            else:
                logger.warning(f"Gemini batch translation validation failed for {target_lang}: {errors}")
                return {}, False
        except Exception as e:
            logger.warning(f"Gemini translation call failed for {target_lang}: {e}")
            return {}, False

    def get_ui_translations(self, target_lang: str) -> dict:
        """Main method returning full UI string dictionary for target_lang.
        
        Guarantees:
        - Never returns blank/partial UI
        - Falls back gracefully to offline starter translations or English
        - Uses SQLite cache to prevent redundant API calls
        """
        target_lang = (target_lang or "en").lower().strip()
        if target_lang not in SUPPORTED_LANGUAGES:
            target_lang = "en"

        # English is source of truth
        if target_lang == "en":
            return {
                "lang": "en",
                "strings": dict(self.source_strings),
                "is_fallback": False,
                "provider": "Source English",
                "source": "cache",
                "sources": {key: "cache" for key in self.source_strings}
            }

        # 1. Check SQLite cache
        cached = self.get_cached_strings(target_lang)
        all_keys = set(self.source_strings.keys())
        missing_keys = all_keys - set(cached.keys())

        if not missing_keys:
            logger.info("UI translations resolved: lang=%s source=cache keys=%d", target_lang, len(all_keys))
            return {
                "lang": target_lang,
                "strings": {k: cached[k] for k in all_keys if k in cached},
                "is_fallback": False,
                "provider": "SQLite Cache",
                "source": "cache",
                "sources": {key: "cache" for key in all_keys}
            }

        # Static UI strings must not wait for or trigger Gemini. Use the complete
        # curated dictionary immediately; Gemini remains available for dynamic AI.
        offline_dict = self.offline_translations.get(target_lang, {})
        fallback_used = False
        sources = {key: "cache" for key in cached}

        for k in missing_keys:
            if k in offline_dict:
                cached[k] = offline_dict[k]
                sources[k] = "offline"
                fallback_used = True
            else:
                cached[k] = self.source_strings[k]
                sources[k] = "offline"
                fallback_used = True

        source_values = set(sources.values())
        source = "offline" if "offline" in source_values else "cache"
        logger.info(
            "UI translations resolved: lang=%s source=%s offline_keys=%d cached_keys=%d",
            target_lang,
            source,
            sum(value == "offline" for value in sources.values()),
            sum(value == "cache" for value in sources.values()),
        )

        return {
            "lang": target_lang,
            "strings": {k: cached.get(k, self.source_strings[k]) for k in all_keys},
            "is_fallback": fallback_used,
            "provider": "Offline Curated Fallback",
            "source": source,
            "sources": sources
        }

    def localize_phrases(self, phrases: list, target_lang: str) -> list:
        """Localizes phrase meanings and contexts into target_lang while strictly preserving Kannada script and transliteration.
        """
        if not phrases or target_lang == "en" or not self.is_valid_language(target_lang):
            return phrases

        # Check phrase_translations in SQLite
        conn = get_db_connection()
        try:
            cursor = conn.execute("""
                SELECT phrase_id, meaning, context 
                FROM phrase_translations 
                WHERE target_lang = ?
            """, (target_lang,))
            cached_map = {row["phrase_id"]: {"meaning": row["meaning"], "context": row["context"]} for row in cursor.fetchall()}
        finally:
            conn.close()

        # Build localized phrases list
        localized = []
        uncached_phrases = []

        for p in phrases:
            item = dict(p)
            if item["id"] in cached_map:
                item["meaning"] = cached_map[item["id"]]["meaning"]
                item["context"] = cached_map[item["id"]]["context"]
            else:
                uncached_phrases.append(item)
            localized.append(item)

        # If uncached phrases exist, attempt translation
        if uncached_phrases:
            self._translate_and_cache_phrases(uncached_phrases, target_lang)
            # Re-fetch cached
            conn = get_db_connection()
            try:
                cursor = conn.execute("""
                    SELECT phrase_id, meaning, context 
                    FROM phrase_translations 
                    WHERE target_lang = ?
                """, (target_lang,))
                updated_map = {row["phrase_id"]: {"meaning": row["meaning"], "context": row["context"]} for row in cursor.fetchall()}
                for item in localized:
                    if item["id"] in updated_map:
                        item["meaning"] = updated_map[item["id"]]["meaning"]
                        item["context"] = updated_map[item["id"]]["context"]
            finally:
                conn.close()

        return localized

    def _translate_and_cache_phrases(self, phrases: list, target_lang: str):
        provider = get_ai_provider()
        target_name = SUPPORTED_LANGUAGES.get(target_lang, {}).get("name", target_lang)

        # If Gemini is available
        if (
            Config.AI_PROVIDER == "gemini"
            and Config.GEMINI_API_KEY
            and callable(getattr(provider, "_call_gemini", None))
        ):
            prompt_items = [{"id": p["id"], "meaning": p["meaning"], "context": p["context"]} for p in phrases]
            prompt = f"""
Translate the 'meaning' and 'context' of these Kannada phrases into {target_name}.
Do not change the 'id'.
Return strictly valid JSON:
[
  {{"id": "p1", "meaning": "<meaning in {target_name}>", "context": "<context in {target_name}>"}}, ...
]

Items:
{json.dumps(prompt_items, ensure_ascii=False)}
"""
            try:
                raw_text = provider._call_gemini(prompt)
                cleaned = raw_text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                parsed = json.loads(cleaned.strip())

                if isinstance(parsed, list):
                    conn = get_db_connection()
                    try:
                        with conn:
                            for item in parsed:
                                if isinstance(item, dict) and "id" in item and "meaning" in item and "context" in item:
                                    conn.execute("""
                                        INSERT INTO phrase_translations (phrase_id, target_lang, meaning, context)
                                        VALUES (?, ?, ?, ?)
                                        ON CONFLICT (phrase_id, target_lang)
                                        DO UPDATE SET meaning = EXCLUDED.meaning,
                                                      context = EXCLUDED.context
                                    """, (item["id"], target_lang, str(item["meaning"]), str(item["context"])))
                    finally:
                        conn.close()
                    return
            except Exception as e:
                logger.warning(f"AI phrase translation failed for {target_lang}: {e}")

        # Offline fallback for phrase meanings in Hindi, Bengali, Tamil, Telugu
        offline_phrase_meanings = {
            "hi": {
                "p1": {"meaning": "नमस्ते / अभिवादन", "context": "दिन के किसी भी समय और किसी के लिए भी एक सार्वभौमिक, विनम्र अभिवादन।"},
                "p2": {"meaning": "धन्यवाद", "context": "सच्चा आभार व्यक्त करता है। सभी रोज़मर्रा की बातचीत में अत्यंत उपयोगी।"},
                "p3": {"meaning": "क्या यह बस मैसूर जाती है?", "context": "बस में चढ़ने से पहले गंतव्य की पुष्टि करने के लिए महत्वपूर्ण।"},
                "p4": {"meaning": "बस स्टैंड कहाँ है?", "context": "आसपास के लोगों से नज़दीकी बस स्टॉप का पता पूछने के लिए।"},
                "p5": {"meaning": "कृपया यहाँ रोकिए", "context": "ऑटो या बस चालक को अपने गंतव्य पर उतरने के लिए कहने का विनम्र तरीका।"},
                "p6": {"meaning": "मेट्रो स्टेशन कैसे जाएँ?", "context": "मेट्रो कनेक्टिविटी और दिशा-निर्देश जानने के लिए राहगीरों से पूछें।"},
                "p7": {"meaning": "कृपया एक गरम फ़िल्टर कॉफ़ी दीजिए", "context": "कर्नाटक भर के दर्शिनि और होटलों में मानक कॉफ़ी ऑर्डर।"},
                "p8": {"meaning": "इसकी कीमत कितनी है?", "context": "दुकानों, बाज़ारों और खान-पान काउंटरों पर पूछने के लिए उपयोगी।"},
                "p9": {"meaning": "कृपया पानी दीजिए", "context": "भोजन के समय पानी माँगने का सीधा और विनम्र अनुरोध।"},
                "p10": {"meaning": "तीखा थोड़ा कम कीजिए", "context": "दुकानदार या रसोइये से मिर्च/मसाला कम करने का अनुरोध।"},
                "p11": {"meaning": "क्या थोड़ा कम करेंगे?", "context": "स्थानीय बाज़ार में शालीनता से मोलभाव करने का आदरणीय तरीका।"},
                "p12": {"meaning": "मुझे यह चाहिए", "context": "दुकान में किसी वस्तु की ओर इशारा करके पसंद बताने के लिए।"},
                "p14": {"meaning": "कृपया मेरी मदद कीजिए", "context": "मदद मांगने या रास्ता भटक जाने पर इस्तेमाल होने वाला स्पष्ट वाक्य।"},
                "p15": {"meaning": "मुझे थोड़ी कन्नड़ आती है", "context": "स्थानीय लोगों से तुरंत आत्मीयता जोड़ने और सीखने का प्रयास बताने वाला वाक्य।"},
                "p17": {"meaning": "नज़दीकी अस्पताल कहाँ है?", "context": "आपातकालीन चिकित्सा सहायता या अस्पताल का पता लगाने के लिए।"},
                "p18": {"meaning": "मेरी तबीयत ठीक नहीं है, क्या डॉक्टर हैं?", "context": "क्लिनिक या प्राथमिक स्वास्थ्य केंद्र में डॉक्टर की उपस्थिति पूछने के लिए।"},
                "p19": {"meaning": "दवा की दुकान कहाँ है?", "context": "आवश्यक दवाइयाँ खरीदने के लिए मेडिकल स्टोर का पता पूछने हेतु।"}
            },
            "ta": {
                "p1": {"meaning": "வணக்கம் / நல்வரவு", "context": "எந்த நேரத்திலும் அனைவருக்கும் பொருத்தமான உலகளாவிய மரியாதை வணக்கம்."},
                "p2": {"meaning": "நன்றி", "context": "உண்மையான நன்றியை வெளிப்படுத்த அனைத்து அன்றாட உரையாடல்களிலும் பயன்படுகிறது."},
                "p3": {"meaning": "இந்த பேருந்து மைசூருக்குப் போகுமா?", "context": "பேருந்தில் ஏறுவதற்கு முன் இலக்கை உறுதிப்படுத்த மிக முக்கியம்."},
                "p4": {"meaning": "பேருந்து நிறுத்தம் எங்கே உள்ளது?", "context": "அருகிலுள்ள பேருந்து நிறுத்தத்தின் இருப்பிடத்தைக் கேட்க."},
                "p5": {"meaning": "தயவுசெய்து இங்கே நிறுத்துங்கள்", "context": "ஆட்டோ அல்லது பேருந்து ஓட்டுநரிடம் இறங்குமிடம் சொல்ல."},
                "p7": {"meaning": "ஒரு சூடான ஃபில்டர் காபி கொடுங்கள்", "context": "கர்நாடக உணவகங்களில் காபி ஆர்டர் செய்ய உதவும்."},
                "p8": {"meaning": "இதன் விலை என்ன?", "context": "கடைகள் மற்றும் சந்தைகளில் விலை கேட்கும் எளிய வழி."},
                "p11": {"meaning": "கொஞ்சம் குறைப்பீர்களா?", "context": "சந்தையில் கனிவாகப் பேரம் பேசுவதற்குப் பயன்படும்."},
                "p15": {"meaning": "எனக்குக் கொஞ்சம் கன்னடம் தெரியும்", "context": "கன்னடம் கற்று வருகிறேன் என்பதைத் தெரிவிக்க உதவும் நட்பு வாக்கியம்."},
                "p17": {"meaning": "அருகிலுள்ள மருத்துவமனை எங்கே உள்ளது?", "context": "அவசர மருத்துவ உதவிக்கு மருத்துவமனையைக் கண்டறிய."},
                "p18": {"meaning": "எனக்கு உடம்பு சரியில்லை, மருத்துவர் இருக்கிறாரா?", "context": "மருத்துவமனையில் மருத்துவர் வருகை குறித்து விசாரிக்க."}
            },
            "te": {
                "p1": {"meaning": "నమస్కారం / శుభాకాంక్షలు", "context": "ఎవరితోనైనా మర్యాదగా పలకరించడానికి సార్వత్రిక శుభాకాంక్షలు."},
                "p2": {"meaning": "ధన్యవాదాలు", "context": "కృతజ్ఞతను వ్యక్తపరచడానికి రోజువారీ పరస్పర చర్యలలో ఉపయోగపడుతుంది."},
                "p3": {"meaning": "ఈ బస్సు మైసూర్‌కు వెళ్తుందా?", "context": "బస్సు ఎక్కే ముందు గమ్యస్థానాన్ని ధృవీకరించుకోవడానికి అవసరం."},
                "p4": {"meaning": "బస్ స్టాప్ ఎక్కడ ఉంది?", "context": "సమీపంలోని బస్ స్టాప్ లొకేషన్ గురించి అడగడానికి."},
                "p5": {"meaning": "దయచేసి ఇక్కడ ఆపండి", "context": "మీ డ్రాప్ పాయింట్ వద్ద ఆటో లేదా బస్సు డ్రైవర్‌కు చెప్పడానికి."},
                "p7": {"meaning": "దయచేసి ఒక వేడి ఫిల్టర్ కాఫీ ఇవ్వండి", "context": "దర్శిని హోటళ్లలో కాఫీ ఆర్డర్ చేయడానికి ప్రామాణిక వాక్యం."},
                "p8": {"meaning": "దీని ధర ఎంత?", "context": "దుకాణాలు మరియు మార్కెట్లలో ధరను అడగడానికి."},
                "p11": {"meaning": "కొంచెం తగ్గిస్తారా?", "context": "మార్కెట్లలో మర్యాదపూర్వకంగా బేరసారాలు చేయడానికి."},
                "p15": {"meaning": "నాకు కన్నడ కొద్దిగా వచ్చు", "context": "కన్నడ ఇంకా నేర్చుకుంటున్నానని స్నేహపూర్వకంగా చెప్పడానికి."},
                "p17": {"meaning": "సమీప ఆసుపత్రి ఎక్కడ ఉంది?", "context": "అత్యవసర వైద్య సంరక్షణ కోసం ఆసుపత్రిని కనుగొనడానికి."},
                "p18": {"meaning": "నాకు ఒంట్లో బాగోలేదు, డాక్టర్ ఉన్నారా?", "context": "క్లినిక్‌లో డాక్టర్ లభ్యత గురించి అడగడానికి."}
            },
            "bn": {
                "p1": {"meaning": "নমস্কার / অভিবাদন", "context": "যেকোনো সময় যেকোনো মানুষের জন্য সার্বজনীন শ্রদ্ধাশীল অভিবাদন।"},
                "p2": {"meaning": "ধন্যবাদ", "context": "কৃতজ্ঞতা প্রকাশ করতে প্রতিটি দৈনন্দিন কথোপকথনে ব্যবহৃত হয়।"},
                "p3": {"meaning": "এই বাসটি কি মহীশূর যাবে?", "context": "বাসে ওঠার আগে গন্তব্য নিশ্চিত করার জন্য অত্যন্ত প্রয়োজনীয়।"},
                "p4": {"meaning": "বাস স্টপটি কোথায়?", "context": "নিকটস্থ বাস স্টপের অবস্থান জিজ্ঞেস করার জন্য।"},
                "p5": {"meaning": "দয়া করে এখানে থামান", "context": "অটো বা বাসে নিজের গন্তব্যে নামার জন্য ভদ্র অনুরোধ।"},
                "p7": {"meaning": "দয়া করে এক কাপ গরম ফিল্টার কফি দিন", "context": "কর্ণাটকের রেস্তোরাঁয় কফি অর্ডারের সাধারণ বাক্য।"},
                "p8": {"meaning": "এটার দাম কত?", "context": "দোকানে এবং বাজারে দাম জিজ্ঞেস করার সহজ উপায়।"},
                "p11": {"meaning": "একটু কম রাখবেন কি?", "context": "বাজারে ভদ্রভাবে দরদাম করার উপযোগী বাক্য।"},
                "p15": {"meaning": "আমি একটু কন্নড় জানি", "context": "আমি এখনো কন্নড় শিখছি তা স্থানীয়দের বোঝানোর সুন্দর বাক্য।"},
                "p17": {"meaning": "কাছের হাসপাতালটি কোথায়?", "context": "জরুরি চিকিৎসা সেবা বা হাসপাতালের খোঁজ নেওয়ার জন্য।"},
                "p18": {"meaning": "আমার শরীর ভালো নেই, ডাক্তারবাবু আছেন কি?", "context": "ক্লিনিকে ডাক্তারের উপস্থিতি জানতে চাওয়ার জন্য।"}
            }
        }

        lang_offline = offline_phrase_meanings.get(target_lang, {})
        if lang_offline:
            conn = get_db_connection()
            try:
                with conn:
                    for pid, data in lang_offline.items():
                        conn.execute("""
                            INSERT INTO phrase_translations (phrase_id, target_lang, meaning, context)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT (phrase_id, target_lang)
                            DO UPDATE SET meaning = EXCLUDED.meaning,
                                          context = EXCLUDED.context
                        """, (pid, target_lang, data["meaning"], data["context"]))
            finally:
                conn.close()

    def localize_scenarios(self, scenarios: list, target_lang: str) -> list:
        """Localizes scenario context, prompt, and options explanations into target_lang while strictly keeping Kannada dialogue quotes intact.
        """
        if not scenarios or target_lang == "en" or not self.is_valid_language(target_lang):
            return scenarios

        # Offline localized explanations for scenarios
        scenario_offline = {
            "hi": {
                "s1": {
                    "context": "आप बस टर्मिनल पर हैं और पुष्टि करना चाहते हैं कि क्या यह बस मैसूर जा रही है।",
                    "prompt": "कौन सा वाक्य विनम्रता से पूछता है कि क्या बस मैसूर जाती है?",
                    "why": {
                        "o1": "सही उत्तर! यह बस में चढ़ने से पहले सीधे और विनम्रता से गंतव्य की पुष्टि करता है।",
                        "o2": "इसका अर्थ है 'कृपया एक गरम फ़िल्टर कॉफ़ी दीजिए।' यह कैफ़े में काम आता है, बस में नहीं।",
                        "o3": "इसका अर्थ है 'धन्यवाद।' यह विनम्र है, परंतु आपके गंतव्य को नहीं बताता।"
                    }
                },
                "s2": {
                    "context": "आप एक चौराहे पर खड़े हैं और नज़दीकी बस स्टॉप खोजना चाहते हैं।",
                    "prompt": "वह वाक्य चुनें जो बस स्टॉप का पता पूछता है।",
                    "why": {
                        "o1": "इसका अर्थ है 'मुझे यह चाहिए।' सामान खरीदते समय इसका प्रयोग करें।",
                        "o2": "बिल्कुल सही! 'ಬಸ್ ನಿಲ್ದಾಣ ಎಲ್ಲಿದೆ?' का अर्थ है 'बस स्टैंड कहाँ है?'",
                        "o3": "इसका अर्थ है 'कृपया पानी दीजिए।' यह भोजनालय में काम आता है।"
                    }
                },
                "s3": {
                    "context": "आप सुबह ताज़ा साउथ इंडियन फ़िल्टर कॉफ़ी का ऑर्डर देना चाहते हैं।",
                    "prompt": "कौन सा वाक्य गरम फ़िल्टर कॉफ़ी का ऑर्डर देने के लिए सही है?",
                    "why": {
                        "o1": "उत्तम! 'ಒಂದು ಬಿಸಿ ಫಿಲ್ಟರ್ ಕಾಫಿ ಕೊಡಿ' एक गरम फ़िल्टर कॉफ़ी ऑर्डर करता है।",
                        "o2": "यह बस स्टॉप का पता पूछता है।",
                        "o3": "इसका अर्थ है 'कृपया मेरी मदद कीजिए।' ऑर्डर देने के लिए यह उपयुक्त नहीं है।"
                    }
                },
                "s4": {
                    "context": "आप बाज़ार में सामान देख रहे हैं और कीमत जानना चाहते हैं।",
                    "prompt": "कीमत पूछने के लिए मानक वाक्य चुनें।",
                    "why": {
                        "o1": "यह एक अभिवादन है: 'नमस्ते।' कीमत नहीं पूछता।",
                        "o2": "सही! 'ಇದರ ಬೆಲೆ ಎಷ್ಟು?' का अर्थ है 'इसकी कीमत कितनी है?'",
                        "o3": "इसका अर्थ है 'कृपया यहाँ रोकिए।' यह ऑटो में काम आता है।"
                    }
                },
                "s5": {
                    "context": "आपको लगता है कि फल थोड़े महंगे हैं और आप थोड़ी छूट का अनुरोध करना चाहते हैं।",
                    "prompt": "कौन सा वाक्य शालीनता से थोड़ी कीमत कम करने का अनुरोध करता है?",
                    "why": {
                        "o1": "विनम्र और प्रभावी! 'ಸ್ವಲ್ಪ ಕಡಿಮೆ ಮಾಡುತ್ತೀರಾ?' पूछता है कि क्या कीमत थोड़ी कम हो सकती है।",
                        "o2": "इसका अर्थ है 'मसाला थोड़ा कम कीजिए' जो खाने के लिए उपयोगी है।",
                        "o3": "यह नज़दीकी अस्पताल का पता पूछता है।"
                    }
                },
                "s6": {
                    "context": "आपकी तबीयत ठीक नहीं है और आप पूछना चाहते हैं कि क्या डॉक्टर उपस्थित हैं।",
                    "prompt": "कौन सा वाक्य आदरपूर्वक बताता है कि आप अस्वस्थ हैं और डॉक्टर के बारे में पूछता है?",
                    "why": {
                        "o1": "सटीक और आदरणीय! यह बताता है कि आप अस्वस्थ हैं और पूछता है कि क्या डॉक्टर मौजूद हैं।",
                        "o2": "इसका अर्थ है 'क्या दूसरा रंग है?' खरीदारी में उपयोगी।",
                        "o3": "यह पूछता है कि मीटिंग कब शुरू होगी।"
                    }
                }
            },
            "ta": {
                "s1": {
                    "context": "நீங்கள் பேருந்து நிலையத்தில் இருக்கிறீர்கள், இந்த பேருந்து மைசூருக்குச் செல்கிறதா என்பதை உறுதிப்படுத்த வேண்டும்.",
                    "prompt": "பேருந்து மைசூருக்குப் போகுமா என்று பணிவாகக் கேட்கும் வாக்கியம் எது?",
                    "why": {
                        "o1": "சரியான விடை! ஏறுவதற்கு முன் இலக்கை நேரடியாக உறுதி செய்கிறது.",
                        "o2": "இதன் பொருள் 'ஒரு சூடான ஃபில்டர் காபி கொடுங்கள்.' இது உணவகத்தில் பயன்படும்.",
                        "o3": "இதன் பொருள் 'நன்றி.' ஆனால் வழியைக் கேட்காது."
                    }
                },
                "s2": {
                    "context": "நீங்கள் அருகிலுள்ள பேருந்து நிறுத்தத்தைக் கண்டறிய வேண்டும்.",
                    "prompt": "பேருந்து நிறுத்தம் எங்கே என்று கேட்கும் வாக்கியத்தைத் தேர்ந்தெடுக்கவும்.",
                    "why": {
                        "o1": "இதன் பொருள் 'எனக்கு இது வேண்டும்.'",
                        "o2": "மிகச் சரி! 'ಬಸ್ ನಿಲ್ದಾಣ ಎಲ್ಲಿದೆ?' என்றால் 'பேருந்து நிறுத்தம் எங்கே?'",
                        "o3": "இதன் பொருள் 'தயவுசெய்து தண்ணீர் கொடுங்கள்.'"
                    }
                }
            },
            "te": {
                "s1": {
                    "context": "మీరు బస్ టెర్మినల్ వద్ద ఉన్నారు మరియు ఈ బస్సు మైసూర్‌కు వెళ్తుందో లేదో నిర్ధారించుకోవాలి.",
                    "prompt": "ఈ బస్సు మైసూర్‌కు వెళ్తుందా అని మర్యాదగా అడిగే కన్నడ వాక్యం ఏది?",
                    "why": {
                        "o1": "సరైన సమాధానం! ఎక్కే ముందు గమ్యస్థానాన్ని నేరుగా నిర్ధారిస్తుంది.",
                        "o2": "దీని అర్థం 'దయచేసి ఒక వేడి ఫిల్టర్ కాఫీ ఇవ్వండి.' ఇది కేఫ్‌లో ఉపయోగపడుతుంది.",
                        "o3": "దీని అర్థం 'ధన్యవాదాలు.' ఇది రూట్ గురించి అడగదు."
                    }
                },
                "s2": {
                    "context": "మీరు సమీపంలోని బస్ స్టాప్‌ను కనుగొనవలసి ఉంది.",
                    "prompt": "బస్ స్టాప్ ఎక్కడ ఉందో అడిగే వాక్యాన్ని ఎంచుకోండి.",
                    "why": {
                        "o1": "దీని అర్థం 'నాకు ఇది కావాలి.'",
                        "o2": "చాలా బాగుంది! 'ಬಸ್ ನಿಲ್ದಾಣ ಎಲ್ಲಿದೆ?' అంటే 'బస్ స్టాప్ ఎక్కడ ఉంది?'",
                        "o3": "దీని అర్థం 'దయచేసి నీరు ఇవ్వండి.'"
                    }
                }
            },
            "bn": {
                "s1": {
                    "context": "আপনি বাস টার্মিনালে আছেন এবং বাসটি মহীশূর যাচ্ছে কিনা তা নিশ্চিত করতে চান।",
                    "prompt": "কোন বাক্যটি ভদ্রভাবে জানতে চায় বাসটি মহীশূর যায় কিনা?",
                    "why": {
                        "o1": "সঠিক উত্তর! বাসে ওঠার আগে গন্তব্য নিশ্চিত করার উপযুক্ত বাক্য।",
                        "o2": "এর অর্থ 'এক কাপ গরম ফিল্টার কফি দিন।' ক্যাফেতে প্রযোজ্য।",
                        "o3": "এর অর্থ 'ধন্যবাদ।' এটি রুট সম্পর্কে জিজ্ঞাসা করে না।"
                    }
                },
                "s2": {
                    "context": "আপনি নিকটবর্তী বাস স্টপটি খুঁজে পেতে চান।",
                    "prompt": "বাস স্টপ কোথায় তা জানতে চাওয়ার বাক্যটি বাছুন।",
                    "why": {
                        "o1": "এর অর্থ 'আমি এটি চাই।'",
                        "o2": "একেবারে সঠিক! 'ಬಸ್ ನಿಲ್ದಾಣ ಎಲ್ಲಿದೆ?' মানে 'বাস স্টপ কোথায়?'",
                        "o3": "এর অর্থ 'দয়া করে জল দিন।'"
                    }
                }
            }
        }

        lang_scenarios = scenario_offline.get(target_lang, {})

        localized_list = []
        for s in scenarios:
            item = dict(s)
            item["options"] = [dict(o) for o in s.get("options", [])]
            sid = item["id"]

            if sid in lang_scenarios:
                item["context"] = lang_scenarios[sid]["context"]
                item["prompt"] = lang_scenarios[sid]["prompt"]
                why_map = lang_scenarios[sid].get("why", {})
                for opt in item["options"]:
                    oid = opt.get("id")
                    if oid in why_map:
                        opt["why"] = why_map[oid]

            localized_list.append(item)

        return localized_list


# Singleton instance
translation_service = TranslationService()
