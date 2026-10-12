import json
import logging
import hashlib
import time
import requests
from abc import ABC, abstractmethod
from backend.config import Config

logger = logging.getLogger(__name__)

_MODEL_CACHE_TTL = 300
_model_inventory_cache = {}
_model_failure_until = {}

LANG_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu"
}

AI_UNAVAILABLE_MESSAGES = {
    "en": "AI generation is temporarily unavailable because the service quota has been reached. Please try again later.",
    "hi": "सेवा की सीमा पूरी होने के कारण AI जनरेशन अभी अस्थायी रूप से उपलब्ध नहीं है। कृपया बाद में फिर कोशिश करें।",
    "bn": "সেবার কোটা পূর্ণ হওয়ায় AI তৈরি সাময়িকভাবে উপলব্ধ নয়। অনুগ্রহ করে পরে আবার চেষ্টা করুন।",
    "ta": "சேவை ஒதுக்கீடு முடிந்ததால் AI உருவாக்கம் தற்காலிகமாக கிடைக்கவில்லை. தயவுசெய்து பின்னர் முயற்சிக்கவும்.",
    "te": "సేవా కోటా పూర్తైనందున AI జనరేషన్ తాత్కాలికంగా అందుబాటులో లేదు. దయచేసి తర్వాత మళ్లీ ప్రయత్నించండి."
}

AI_GENERIC_UNAVAILABLE_MESSAGES = {
    "en": "AI generation is temporarily unavailable. Please try again later.",
    "hi": "AI जनरेशन अभी अस्थायी रूप से उपलब्ध नहीं है। कृपया बाद में फिर कोशिश करें।",
    "bn": "AI তৈরি সাময়িকভাবে উপলব্ধ নয়। অনুগ্রহ করে পরে আবার চেষ্টা করুন।",
    "ta": "AI உருவாக்கம் தற்காலிகமாக கிடைக்கவில்லை. தயவுசெய்து பின்னர் முயற்சிக்கவும்.",
    "te": "AI జనరేషన్ తాత్కాలికంగా అందుబాటులో లేదు. దయచేసి తర్వాత మళ్లీ ప్రయత్నించండి."
}

AI_UNAVAILABLE_TIPS = {
    "en": "Please try again later when the AI service is available.",
    "hi": "AI सेवा उपलब्ध होने पर कृपया बाद में फिर कोशिश करें।",
    "bn": "AI পরিষেবা উপলব্ধ হলে অনুগ্রহ করে পরে আবার চেষ্টা করুন।",
    "ta": "AI சேவை கிடைக்கும்போது தயவுசெய்து பின்னர் முயற்சிக்கவும்.",
    "te": "AI సేవ అందుబాటులో ఉన్నప్పుడు దయచేసి తర్వాత మళ్లీ ప్రయత్నించండి."
}


class BaseAIProvider(ABC):
    """Abstract base class for replaceable AI conversation providers."""

    @abstractmethod
    def generate_reply(self, scenario_context: str, user_message: str, history: list = None, target_lang: str = "en") -> dict:
        """Generates a structured phrase lesson for practice."""
        pass

    @abstractmethod
    def explain_phrase(self, phrase_text: str, user_question: str = "", target_lang: str = "en") -> dict:
        """Explains a Kannada phrase nuances, politeness, and usage."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Returns the name and mode of the provider."""
        pass


class LocalFallbackProvider(BaseAIProvider):
    """Deterministic, offline conversational provider for Kannada learners."""

    def get_provider_name(self) -> str:
        return "Local Offline Engine (Deterministic)"

    def generate_reply(self, scenario_context: str, user_message: str, history: list = None, target_lang: str = "en") -> dict:
        msg_lower = (user_message or "").lower()
        target_lang = (target_lang or "en").lower().strip()
        if target_lang not in LANG_NAMES:
            target_lang = "en"

        # Structured phrase lessons based on practical everyday communication
        if any(w in msg_lower for w in ["dosa", "dose", "ದೋಸೆ"]):
            phrase_kn = "ಒಂದು ಮಸಾಲ ದೋಸೆ ಕೊಡಿ"
            phrase_roman = "Ondu masāla dōse koḍi"
            meanings = {
                "en": "Please give me one masala dosa",
                "hi": "कृपया मुझे एक मसाला डोसा दीजिए",
                "bn": "দয়া করে আমাকে একটি মসলা দোসা দিন",
                "ta": "எனக்கு ஒரு மசாలా தோசை கொடுங்கள்",
                "te": "దయచేసి నాకు ఒక మసాలా దోశ ఇవ్వండి"
            }
            explanations = {
                "en": "Use this phrase at the billing or serving counter in any darshini restaurant.",
                "hi": "किसी भी दर्शिनि होटल के काउंटर पर ऑर्डर देते समय इस वाक्य का प्रयोग करें।",
                "bn": "যেকোনো দর্শনীয় রেস্তোরাঁর কাউন্টারে অর্ডার করার সময় এই বাক্যটি বলুন।",
                "ta": "உணவக கவுண்டரில் தோசை ஆர்டர் செய்யும்போது இந்த வாக்கியத்தைப் பயன்படுத்துங்கள்.",
                "te": "దర్శిని రెస్టారెంట్‌లో కౌంటర్ వద్ద ఆర్డర్ ఇచ్చేటప్పుడు ఈ వాక్యాన్ని ఉపయోగించండి."
            }
            tips = {
                "en": "Add 'ದಯವಿಟ್ಟು' (Dayaviṭṭu) for extra politeness.",
                "hi": "अधिक विनम्रता के लिए 'ದಯವಿಟ್ಟು' (దయవిట్టు - कृपया) जोड़ें।",
                "bn": "অতিরিক্ত ভদ্রতার জন্য 'ದಯವಿಟ್ಟು' (দয়া করে) যোগ করুন।",
                "ta": "கூடுதல் மரியாதைக்கு 'ದಯವಿಟ್ಟು' (தயவுசெய்து) சேர்க்கலாம்.",
                "te": "మరింత మర్యాద కోసం 'ದಯವಿಟ್ಟು' (దయచేసి) జోడించవచ్చు."
            }
        elif any(w in msg_lower for w in ["coffee", "tea", "kaapi", "ಕಾಫಿ", "ಚಹಾ"]):
            phrase_kn = "ಒಂದು ಬಿಸಿ ಫಿಲ್ಟರ್ ಕಾಫಿ ಕೊಡಿ"
            phrase_roman = "Ondu bisi philtar kāphi koḍi"
            meanings = {
                "en": "Please give me one hot filter coffee",
                "hi": "कृपया एक गरम फ़िल्टर कॉफ़ी दीजिए",
                "bn": "দয়া করে এক কাপ গরম ফিল্টার কফি দিন",
                "ta": "ஒரு சூடான ஃபில்டர் காபி கொடுங்கள்",
                "te": "దయచేసి ఒక వేడి ఫిల్టర్ కాఫీ ఇవ్వండి"
            }
            explanations = {
                "en": "Standard order across Bengaluru darshinis. Pay at token counter first if required.",
                "hi": "बेंगलुरु के दर्शिनि होटलों में मानक कॉफ़ी ऑर्डर। आवश्यकता पड़ने पर पहले टोकन लें।",
                "bn": "বেঙ্গালুরুর রেস্তোরাঁয় ফিল্টার কফির সাধারণ অর্ডার।",
                "ta": "பெங்களூரு உணவகங்களில் ஃபில்டர் காபி ஆர்டர் செய்யும் முறை.",
                "te": "బెంగళూరులోని దర్శినిలలో ఫిల్టర్ కాఫీ ఆర్డర్ చేయడానికి ప్రామాణిక పద్ధతి."
            }
            tips = {
                "en": "Say 'ಬಿಸಿ' (Bisi) to emphasize you want it piping hot.",
                "hi": "'ಬಿಸಿ' (बिसि) का अर्थ गरम होता है।",
                "bn": "'ಬಿಸಿ' মানে গরম।",
                "ta": "'ಬಿಸಿ' என்றால் சூடான என்று பொருள்.",
                "te": "'ಬಿಸಿ' అంటే వేడి అని అర్థం."
            }
        elif any(w in msg_lower for w in ["bus", "bengaluru", "mysuru", "route", "bus stop", "ಹೋಗ"]):
            phrase_kn = "ಈ ಬಸ್ ಮೈಸೂರುಗೆ ಹೋಗುತ್ತದೆಯೇ?"
            phrase_roman = "Ī bas Mysūrige hōguttadeyē?"
            meanings = {
                "en": "Does this bus go to Mysuru?",
                "hi": "क्या यह बस मैसूर जाती है?",
                "bn": "এই বাসটি কি মহীশূর যাবে?",
                "ta": "இந்த பேருந்து மைசூருக்குப் போகுமா?",
                "te": "ఈ బస్సు మైసూర్‌కు వెళ్తుందా?"
            }
            explanations = {
                "en": "Ask this to the conductor or driver before boarding the bus.",
                "hi": "बस में चढ़ने से पहले कंडक्टर या ड्राइवर से यह प्रश्न पूछें।",
                "bn": "বাসে ওঠার আগে কন্ডাক্টর বা চালককে এই প্রশ্নটি করুন।",
                "ta": "பேருந்தில் ஏறும் முன் நடத்துனர் அல்லது ஓட்டுநரிடம் கேளுங்கள்.",
                "te": "బస్సు ఎక్కే ముందు కండక్టర్ లేదా డ్రైవర్‌ను అడగండి."
            }
            tips = {
                "en": "Replace 'Mysūrige' with your target place + 'ge' (e.g. 'Majestic-ge').",
                "hi": "स्थान के नाम के आगे '-गे' लगाकर पूछें (जैसे 'Majestic-ge').",
                "bn": "গন্তব্যের নামের সাথে '-গে' যোগ করুন (যেমন 'Majestic-ge').",
                "ta": "இடத்தின் பெயருடன் '-ge' சேர்த்துப் பேசலாம்.",
                "te": "గమ్యస్థానానికి '-ge' జోడించి అడగవచ్చు."
            }
        elif any(w in msg_lower for w in ["price", "cost", "rate", "how much", "bargain", "ಎಷ್ಟು", "ಕಡಿಮೆ"]):
            phrase_kn = "ಇದರ ಬೆಲೆ ಎಷ್ಟು? ಸ್ವಲ್ಪ ಕಡಿಮೆ ಮಾಡುತ್ತೀರಾ?"
            phrase_roman = "Idara bele eṣṭu? Svalpa kaḍime māḍuttīrā?"
            meanings = {
                "en": "How much does this cost? Could you reduce the price a little?",
                "hi": "इसकी कीमत कितनी है? क्या थोड़ा कम करेंगे?",
                "bn": "এটার দাম কত? একটু কম করবেন কি?",
                "ta": "இதன் விலை என்ன? கொஞ்சம் குறைப்பீர்களா?",
                "te": "దీని ధర ఎంత? కొంచెం తగ్గిస్తారా?"
            }
            explanations = {
                "en": "Polite two-step phrase for asking prices and courteous bargaining at local markets.",
                "hi": "स्थानीय बाज़ारों में कीमत पूछने और शालीनता से मोलभाव करने का आदरणीय तरीका।",
                "bn": "বাজারে দাম জানতে এবং ভদ্রভাবে দরদাম করার উপযোগী বাক্য।",
                "ta": "விலை கேட்டு பேரம் பேசுவதற்கான கண்ணியமான முறை.",
                "te": "ధర అడిగి మర్యాదగా బేరమాడటానికి ఉపయోగపడుతుంది."
            }
            tips = {
                "en": "'Svalpa' means a little. It softens your negotiation politely.",
                "hi": "'ಸ್ವಲ್ಪ' (स्वल्प) का अर्थ थोड़ा होता है, जिससे बातचीत विनम्र लगती है।",
                "bn": "'ಸ್ವಲ್ಪ' মানে একটু। এটি আলোচনাকে ভদ্র করে।",
                "ta": "'Svalpa' என்றால் கொஞ்சம் என்று பொருள்.",
                "te": "'Svalpa' అంటే కొంచెం అని అర్థం."
            }
        elif any(w in msg_lower for w in ["doctor", "clinic", "hospital", "pain", "fever", "sick", "ఆస్పತ್ರೆ", "ಆಸ್ಪತ್ರೆ", "ಹುಷಾರಿಲ್ಲ"]):
            phrase_kn = "ನನಗೆ ಹುಷಾರಿಲ್ಲ, ವೈದ್ಯರು ಇದ್ದಾರಾ?"
            phrase_roman = "Nanage huṣārilla, vaidyaru iddārā?"
            meanings = {
                "en": "I am not well, is the doctor available?",
                "hi": "मेरी तबीयत ठीक नहीं है, क्या डॉक्टर उपलब्ध हैं?",
                "bn": "আমার শরীর ভালো নেই, ডাক্তারবাবু কি আছেন?",
                "ta": "எனக்கு உடம்பு சரியில்லை, மருத்துவர் இருக்கிறாரா?",
                "te": "నాకు ఒంట్లో బాగోలేదు, డాక్టర్ ఉన్నారా?"
            }
            explanations = {
                "en": "Use at any clinic reception or primary health centre to explain urgency.",
                "hi": "क्लिनिक रिसेप्शन या स्वास्थ्य केंद्र पर डॉक्टर की उपलब्धता जानने के लिए कहें।",
                "bn": "ক্লিনিকের অভ্যর্থনায় ডাক্তারের উপস্থিতি জানতে এটি বলুন।",
                "ta": "கிளினிக்கில் மருத்துவர் வருகை குறித்து விசாரிக்கப் பயன்படும்.",
                "te": "క్లినిక్ వద్ద డాక్టర్ లభ్యత గురించి అడగడానికి ఉపయోగించండి."
            }
            tips = {
                "en": "Healthcare Notice: Communication aid only. In emergencies call 108 or 112.",
                "hi": "स्वास्थ्य सूचना: केवल भाषा सहायता। आपातकाल में 108 या 112 पर कॉल करें।",
                "bn": "স্বাস্থ্য বিজ্ঞপ্তি: শুধুমাত্র ভাষা সহায়তা। জরুরি অবস্থায় ১০৮ বা ১১২ নম্বরে ফোন করুন।",
                "ta": "மருத்துவ அறிவிப்பு: மொழி உதவி மட்டுமே. அவசரத்திற்கு 108 அல்லது 112 ஐ அழைக்கவும்.",
                "te": "ఆరోగ్య ప్రకటన: కేవలం భాషా సహాయం మాత్రమే. అత్యవసరంలో 108 లేదా 112 కు కాల్ చేయండి."
            }
        elif any(w in msg_lower for w in ["namaskara", "hello", "hi", "how are you", "ನಮಸ್ಕಾರ"]):
            phrase_kn = "ನಮಸ್ಕಾರ, ಹೇಗಿದ್ದೀರಾ?"
            phrase_roman = "Namaskāra, hēgiddīrā?"
            meanings = {
                "en": "Hello, how are you?",
                "hi": "नमस्ते, आप कैसे हैं?",
                "bn": "নমস্কার, কেমন আছেন?",
                "ta": "வணக்கம், எப்படி இருக்கிறீர்கள்?",
                "te": "నమస్కారం, ఎలా ఉన్నారు?"
            }
            explanations = {
                "en": "Universal respectful greeting suitable for neighbors, elders, and colleagues.",
                "hi": "पड़ोसियों, बड़ों और सहकर्मियों के लिए सार्वभौमिक आदरणीय अभिवादन।",
                "bn": "প্রতিবেশী, গুরুজন এবং সহকর্মীদের সাথে সর্বজনীন শ্রদ্ধাশীল সম্ভাষণ।",
                "ta": "அனைவரிடமும் மரியாதை செலுத்தப் பயன்படும் வாழ்த்து.",
                "te": "ఎవరితోనైనా మర్యాదగా పలకరించడానికి ప్రామాణిక పద్ధతి."
            }
            tips = {
                "en": "Reply with 'ಚೆನ್ನಾಗಿದ್ದೀನಿ' (Chennāgiddīni - I am doing well).",
                "hi": "उत्तर में 'ಚೆನ್ನಾಗಿದ್ದೀನಿ' (चेन्नागिद्दीनि - मैं ठीक हूँ) कहें।",
                "bn": "উত্তরে 'ಚೆನ್ನಾಗಿದ್ದೀನಿ' (আমি ভালো আছি) বলুন।",
                "ta": "பதிலுக்கு 'Chennāgiddīni' (நன்றாக இருக்கிறேன்) என்று சொல்லலாம்.",
                "te": "సమాధానంగా 'Chennāgiddīni' (బాగున్నాను) అని చెప్పండి."
            }
        else:
            phrase_kn = "ಕ್ಷಮಿಸಿ, ಈ ವಿನಂತಿಗೆ ಆಫ್‌ಲೈನ್ ಅನುವಾದ ಲಭ್ಯವಿಲ್ಲ."
            phrase_roman = "Kṣamisi, ī vinantige āphlaina anuvāda labhyavilla."
            meanings = {
                "en": "I could not generate a phrase-specific translation while offline.",
                "hi": "मुझे थोड़ी कन्नड़ आती है (मैं अभी सीख रहा हूँ)",
                "bn": "আমি একটু কন্নড় জানি (আমি এখনো শিখছি)",
                "ta": "எனக்குக் கொஞ்சம் கன்னடம் தெரியும் (கற்றுக் கொண்டிருக்கிறேன்)",
                "te": "నాకు కన్నడ కొద్దిగా వచ్చు (నేను ఇంకా నేర్చుకుంటున్నాను)"
            }
            meanings["en"] = (
                f'I could not generate a phrase-specific translation for "{user_message}" while offline. '
                "Configure Gemini or try again when it is available."
            )
            explanations = {
                "en": "Connect Gemini to generate an exact Kannada phrase for this request.",
                "hi": "स्थानीय लोगों से तुरंत आत्मीयता जोड़ने वाला अत्यंत उपयोगी वाक्य।",
                "bn": "স্থানীয়দের সাথে অবিলম্বে আন্তরিকতা তৈরি করার সুন্দর বাক্য।",
                "ta": "உள்ளூர் மக்களிடம் அன்பாகப் பேச உதவும் மிகச் சிறந்த வாக்கியம்.",
                "te": "స్థానికులతో మాట్లాడేటప్పుడు సాన్నిహిత్యాన్ని పెంచే ఉపయోగకరమైన వాక్యం."
            }
            tips = {
                "en": "This is an offline fallback, not a generated answer to your exact request.",
                "hi": "कन्नड़ में बोलने के प्रयास की स्थानीय लोग दिल से सराहना करते हैं!",
                "bn": "কন্নড়ে কথা বলার প্রচেষ্টাকে স্থানীয়রা অত্যন্ত প্রশংসা করেন!",
                "ta": "கன்னடத்தில் பேச முயற்சிப்பதை மக்கள் மனதாரப் பாராட்டுவார்கள்!",
                "te": "కన్నడలో మాట్లాడే ప్రయత్నాన్ని స్థానికులు ఎంతగానో అభినందిస్తారు!"
            }

        meaning_text = meanings.get(target_lang, meanings["en"])
        explanation_text = explanations.get(target_lang, explanations["en"])
        tip_text = tips.get(target_lang, tips["en"])

        return {
            "phrase_kn": phrase_kn,
            "phrase_roman": phrase_roman,
            "meaning": meaning_text,
            "explanation": explanation_text,
            "learner_tip": tip_text,
            "lang": target_lang,
            # Backwards compatibility fields
            "reply_kn": phrase_kn,
            "reply_roman": phrase_roman,
            "reply_en": meaning_text,
            "provider": self.get_provider_name(),
            "provider_source": "offline",
            "mode": "offline_fallback",
            "disclaimer": "Offline lesson engine active. To enable live generative AI, configure GEMINI_API_KEY."
        }

    def explain_phrase(self, phrase_text: str, user_question: str = "", target_lang: str = "en") -> dict:
        target_lang = (target_lang or "en").lower().strip()
        localized = {
            "en": {
                "explanation": f"In everyday Kannada, '{phrase_text}' is used with respectful tone in everyday situations.",
                "formality": "Everyday polite conversational style",
                "cultural_context": "Karnataka culture values respectful suffixes like 'ದಯವಿಟ್ಟು' (please) and plural pronouns."
            },
            "hi": {
                "explanation": f"रोज़मर्रा की कन्नड़ में '{phrase_text}' का प्रयोग सम्मानजनक लहजे में किया जाता है।",
                "formality": "रोज़मर्रा की विनम्र बातचीत",
                "cultural_context": "कर्नाटक में 'ದಯವಿಟ್ಟು' (कृपया) जैसे विनम्र शब्दों और आदरसूचक संबोधन को महत्व दिया जाता है।"
            },
            "bn": {
                "explanation": f"দৈনন্দিন কন্নড়ে ‘{phrase_text}’ সম্মানজনক ভঙ্গিতে ব্যবহার করা হয়।",
                "formality": "দৈনন্দিন ভদ্র কথোপকথনের ধরন",
                "cultural_context": "কর্ণাটকে ‘ದಯವಿಟ್ಟು’ (দয়া করে)-এর মতো সম্মানসূচক শব্দ ব্যবহার করা হয়।"
            },
            "ta": {
                "explanation": f"அன்றாட கன்னடத்தில் ‘{phrase_text}’ மரியாதையான தொனியில் பயன்படுத்தப்படுகிறது.",
                "formality": "அன்றாட மரியாதையான உரையாடல்",
                "cultural_context": "கர்நாடகத்தில் ‘ದಯವಿಟ್ಟು’ (தயவுசெய்து) போன்ற மரியாதைச் சொற்களுக்கு முக்கியத்துவம் உண்டு."
            },
            "te": {
                "explanation": f"రోజువారీ కన్నడలో ‘{phrase_text}’ను గౌరవప్రదమైన స్వరంతో ఉపయోగిస్తారు.",
                "formality": "రోజువారీ మర్యాదపూర్వక సంభాషణ",
                "cultural_context": "కర్ణాటకలో ‘ದಯವಿಟ್ಟು’ (దయచేసి) వంటి గౌరవ సూచక పదాలకు ప్రాధాన్యం ఉంది."
            }
        }
        copy = localized.get(target_lang, localized["en"])

        return {
            "phrase": phrase_text,
            **copy,
            "lang": target_lang,
            "provider": self.get_provider_name(),
            "provider_source": "offline",
            "mode": "offline_fallback"
        }

    def generate_practice_scenario(self, category: str, situation_prompt: str) -> dict:
        return {
            "title": f"Practice in {category.capitalize()}",
            "situation": situation_prompt or "A realistic everyday interaction in Karnataka.",
            "speaker": "Local Resident",
            "speaker_kn": "ಸ್ಥಳೀಯ ನಿವಾಸಿ",
            "prompt": "Choose the most appropriate response for this situation.",
            "provider": self.get_provider_name(),
            "mode": "offline_fallback"
        }


class GeminiProvider(BaseAIProvider):
    """Google Gemini AI integration for contextual Kannada language learning."""

    API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
    provider_source = "gemini"

    def __init__(self, api_key: str, model_name: str = ""):
        self.api_key = api_key
        self.model_name = self._clean_model_name(model_name)
        self.fallback = LocalFallbackProvider()

    @staticmethod
    def _clean_model_name(model_name: str) -> str:
        return (model_name or "").strip().removeprefix("models/")

    @staticmethod
    def _safe_error_description(response) -> str:
        try:
            message = response.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError, TypeError):
            message = ""
        message = " ".join(str(message).split())
        return message[:160] or "provider returned an error"

    def list_models(self) -> list[dict]:
        """Return models visible to this key, without exposing credentials."""
        cache_key = hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()
        cached = _model_inventory_cache.get(cache_key)
        if cached and cached["expires_at"] > time.monotonic():
            return cached["models"]
        try:
            response = requests.get(
                f"{self.API_ROOT}/models",
                headers={"x-goog-api-key": self.api_key},
                timeout=Config.GEMINI_MODEL_DISCOVERY_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.warning("Gemini model discovery failed: network error (%s)", type(exc).__name__)
            raise RuntimeError("Gemini model discovery failed: network error") from exc
        if not response.ok:
            description = self._safe_error_description(response)
            logger.warning("Gemini model discovery failed: HTTP %s (%s)", response.status_code, description)
            raise RuntimeError(f"Gemini model discovery failed: HTTP {response.status_code}")
        try:
            models = response.json().get("models", [])
        except (ValueError, AttributeError, TypeError) as exc:
            raise RuntimeError("Gemini model discovery returned invalid JSON") from exc
        models = [
            model for model in models
            if isinstance(model, dict)
            and "generateContent" in model.get("supportedGenerationMethods", [])
        ]
        _model_inventory_cache[cache_key] = {
            "models": models,
            "expires_at": time.monotonic() + _MODEL_CACHE_TTL,
        }
        return models

    def _model_is_temporarily_failed(self, model_name: str) -> bool:
        cache_key = hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()
        return _model_failure_until.get((cache_key, model_name), 0) > time.monotonic()

    def _mark_model_failed(self, model_name: str):
        cache_key = hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()
        _model_failure_until[(cache_key, model_name)] = (
            time.monotonic() + Config.GEMINI_MODEL_FAILURE_COOLDOWN
        )

    def resolve_model(self) -> str:
        """Use the configured model when available, otherwise select an advertised stable model."""
        models = self.list_models()
        available = {
            self._clean_model_name(model.get("name", "")): model
            for model in models
            if self._clean_model_name(model.get("name", ""))
        }
        if (
            self.model_name
            and self.model_name in available
            and not self._model_is_temporarily_failed(self.model_name)
        ):
            return self.model_name

        stable_flash = [
            name for name in available
            if "flash" in name.lower()
            and not self._model_is_temporarily_failed(name)
            and not any(marker in name.lower() for marker in ("preview", "experimental", "exp"))
        ]
        available_stable = [
            name for name in available
            if not self._model_is_temporarily_failed(name)
        ]
        candidates = stable_flash or sorted(available_stable)
        if not candidates:
            raise RuntimeError("Gemini API advertised no model supporting generateContent")
        selected = candidates[0]
        logger.info("Gemini model selected from API inventory: %s", selected)
        self.model_name = selected
        return selected

    def diagnostic(self) -> dict:
        """Return safe model-access information for diagnostics and tests."""
        models = self.list_models()
        names = sorted(
            self._clean_model_name(model.get("name", ""))
            for model in models
            if model.get("name")
        )
        return {
            "configured_model": self.model_name or None,
            "generate_content_models": names,
            "selected_model": self.resolve_model(),
        }

    def probe(self) -> str:
        """Perform a minimal real generation request before application workflows."""
        return self._call_gemini("Reply with the single word OK.")

    def get_provider_name(self) -> str:
        return f"Gemini API ({self.model_name or 'model discovery'})"

    def _call_gemini(self, prompt: str) -> str:
        model_name = self.resolve_model()
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 800
            }
        }
        response = self._post_generation(model_name, payload)
        if response.status_code == 404:
            description = self._safe_error_description(response)
            self._mark_model_failed(model_name)
            alternatives = []
            for model in self.list_models():
                alternative = self._clean_model_name(model.get("name", ""))
                lower_name = alternative.lower()
                if (
                    alternative
                    and alternative != model_name
                    and not self._model_is_temporarily_failed(alternative)
                    and "flash" in lower_name
                    and not any(marker in lower_name for marker in (
                        "preview", "experimental", "exp", "image", "tts", "transcribe"
                    ))
                ):
                    alternatives.append(alternative)
            if alternatives:
                logger.warning(
                    "Gemini model unavailable: %s; retrying with an advertised model",
                    description,
                )
                candidates = sorted(
                    set(alternatives),
                    key=lambda name: (0 if "flash-lite" in name.lower() else 1, name),
                )
                for alternative in candidates[:1]:
                    retry = self._post_generation(alternative, payload)
                    if retry.ok:
                        self.model_name = alternative
                        response = retry
                        break
                else:
                    response = retry

        if not response.ok:
            description = self._safe_error_description(response)
            logger.warning("Gemini generation failed: HTTP %s (%s)", response.status_code, description)
            raise RuntimeError(f"Gemini generation failed: HTTP {response.status_code}")
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("No response candidate returned by Gemini API")
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return text

    def _post_generation(self, model_name: str, payload: dict):
        url = f"{self.API_ROOT}/models/{model_name}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        try:
            return requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=Config.GEMINI_REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.warning("Gemini generation failed: network error (%s)", type(exc).__name__)
            raise RuntimeError("Gemini generation failed: network error") from exc

    def generate_reply(self, scenario_context: str, user_message: str, history: list = None, target_lang: str = "en") -> dict:
        target_lang = (target_lang or "en").lower().strip()
        if target_lang not in LANG_NAMES:
            target_lang = "en"
        lang_name = LANG_NAMES.get(target_lang, "English")

        prompt = f"""
You are NammaSpeak's structured Kannada language learning tutor for everyday life.
Scenario context: {scenario_context}
Learner query: "{user_message}"
Learner's preferred language for explanations: {lang_name}

CRITICAL PEDAGOGICAL INSTRUCTIONS:
1. Provide a focused, structured Kannada phrase lesson that directly teaches the exact phrase needed for this request (for example, if asking how to order dosa, teach the exact Kannada phrase for ordering dosa).
2. 'phrase_kn' MUST be in Kannada script (never Devanagari, Bengali, Tamil, Telugu, or Latin script).
3. 'phrase_roman' MUST be clear, accessible Roman transliteration.
4. 'meaning' MUST be the translation in {lang_name}.
5. 'explanation' MUST be a concise usage explanation in {lang_name} indicating when and where to say it.
6. 'learner_tip' MUST be a cultural or polite phrasing tip in {lang_name}.
7. For health or emergency contexts, provide ONLY communication/translation aid. Do NOT give medical diagnosis or treatment advice. Include advice to seek qualified medical help.
8. Output strictly valid JSON with no markdown formatting and no extra text.

JSON Schema:
{{
  "phrase_kn": "<Exact Kannada phrase in Kannada script>",
  "phrase_roman": "<Roman transliteration>",
  "meaning": "<Translation in {lang_name}>",
  "explanation": "<Usage explanation in {lang_name}>",
  "learner_tip": "<Etiquette or grammar tip in {lang_name}>",
  "disclaimer": "AI-generated lesson. Verify unfamiliar phrases with native speakers."
}}
"""
        try:
            raw_text = self._call_gemini(prompt)
            cleaned = raw_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            parsed = json.loads(cleaned.strip())

            # Validate expected fields
            for field in ["phrase_kn", "phrase_roman", "meaning", "explanation"]:
                if field not in parsed or not isinstance(parsed[field], str):
                    raise ValueError(f"Missing or invalid field: {field}")

            parsed["lang"] = target_lang
            parsed["reply_kn"] = parsed["phrase_kn"]
            parsed["reply_roman"] = parsed["phrase_roman"]
            parsed["reply_en"] = parsed["meaning"]
            parsed["provider"] = self.get_provider_name()
            parsed["provider_source"] = self.provider_source
            parsed["mode"] = "live_ai"
            return parsed
        except (RuntimeError, ValueError, TypeError, json.JSONDecodeError) as exc:
            is_quota_error = "429" in str(exc)
            logger.warning(
                "%s lesson generation unavailable; returning explicit unavailable response (%s)",
                self.get_provider_name(),
                "quota" if is_quota_error else type(exc).__name__,
            )
            unavailable = (
                AI_UNAVAILABLE_MESSAGES[target_lang]
                if is_quota_error
                else AI_GENERIC_UNAVAILABLE_MESSAGES[target_lang]
            )
            return {
                "phrase_kn": "ಕ್ಷಮಿಸಿ, AI ಸೇವೆ ಈಗ ಲಭ್ಯವಿಲ್ಲ.",
                "phrase_roman": "Kṣamisi, AI sēve īga labhyavilla.",
                "meaning": unavailable,
                "explanation": unavailable,
                "learner_tip": AI_UNAVAILABLE_TIPS[target_lang],
                "reply_kn": "ಕ್ಷಮಿಸಿ, AI ಸೇವೆ ಈಗ ಲಭ್ಯವಿಲ್ಲ.",
                "reply_roman": "Kṣamisi, AI sēve īga labhyavilla.",
                "reply_en": unavailable,
                "lang": target_lang,
                "provider": self.get_provider_name(),
                "provider_source": "unavailable",
                "mode": "ai_unavailable",
                "original_query": user_message,
                "fallback_reason": "ai_quota_exhausted" if is_quota_error else "ai_unavailable_or_invalid_response",
                "disclaimer": unavailable,
            }

    def explain_phrase(self, phrase_text: str, user_question: str = "", target_lang: str = "en") -> dict:
        target_lang = (target_lang or "en").lower().strip()
        if target_lang not in LANG_NAMES:
            target_lang = "en"
        lang_name = LANG_NAMES.get(target_lang, "English")

        prompt = f"""
Explain this Kannada phrase for a language learner.
Phrase: "{phrase_text}"
Question: "{user_question}"
Target explanation language: {lang_name}

Return strictly valid JSON:
{{
  "phrase": "{phrase_text}",
  "explanation": "<Clear explanation of grammar, tone, and usage in {lang_name}>",
  "formality": "<Level of politeness in {lang_name}>",
  "cultural_context": "<When and where locals use this phrase in {lang_name}>",
  "disclaimer": "Educational AI explanation."
}}
"""
        try:
            raw_text = self._call_gemini(prompt)
            cleaned = raw_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            parsed = json.loads(cleaned.strip())
            parsed["provider"] = self.get_provider_name()
            parsed["provider_source"] = self.provider_source
            parsed["mode"] = "live_ai"
            parsed["lang"] = target_lang
            return parsed
        except (RuntimeError, ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("Gemini API explain failed; using offline fallback (%s)", type(exc).__name__)
            return self.fallback.explain_phrase(phrase_text, user_question, target_lang=target_lang)

    def generate_practice_scenario(self, category: str, situation_prompt: str) -> dict:
        return self.fallback.generate_practice_scenario(category, situation_prompt)


class OpenAIProvider(GeminiProvider):
    """OpenAI chat-completions provider using the shared structured lesson contract."""

    API_ROOT = "https://api.openai.com/v1"
    provider_source = "openai"

    def __init__(self, api_key: str, model_name: str = ""):
        self.api_key = api_key
        self.model_name = (model_name or "gpt-4o-mini").strip()
        self.fallback = LocalFallbackProvider()

    def get_provider_name(self) -> str:
        return f"OpenAI API ({self.model_name})"

    @staticmethod
    def _safe_openai_error_description(response) -> str:
        try:
            message = response.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError, TypeError):
            message = ""
        return " ".join(str(message).split())[:160] or "provider returned an error"

    def _call_gemini(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only valid JSON matching the requested schema."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 800,
            "response_format": {"type": "json_object"}
        }
        try:
            response = requests.post(
                f"{self.API_ROOT}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json=payload,
                timeout=Config.OPENAI_REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.warning("OpenAI generation failed: network error (%s)", type(exc).__name__)
            raise RuntimeError("OpenAI generation failed: network error") from exc

        if not response.ok:
            description = self._safe_openai_error_description(response)
            logger.warning("OpenAI generation failed: HTTP %s (%s)", response.status_code, description)
            raise RuntimeError(f"OpenAI generation failed: HTTP {response.status_code} {description}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError("OpenAI response did not contain message content") from exc
        if not isinstance(content, str) or not content.strip():
            raise ValueError("OpenAI response contained empty message content")
        return content


def get_ai_provider() -> BaseAIProvider:
    """Factory function returning the active AI provider based on configuration."""
    provider_type = Config.AI_PROVIDER
    if provider_type == "openai" and Config.OPENAI_API_KEY:
        return OpenAIProvider(api_key=Config.OPENAI_API_KEY, model_name=Config.OPENAI_MODEL)

    if provider_type == "gemini" and Config.GEMINI_API_KEY:
        return GeminiProvider(api_key=Config.GEMINI_API_KEY, model_name=Config.AI_MODEL)
    return LocalFallbackProvider()
