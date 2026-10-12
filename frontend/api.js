/**
 * NammaSpeak API Client
 * Centralized Fetch client with graceful fallbacks and consistent error handling.
 */

const API_BASE = window.location.origin.startsWith("http") ? "" : "http://127.0.0.1:5000";

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const defaultHeaders = {
    "Accept": "application/json",
    "Content-Type": "application/json"
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {})
      }
    });

    if (!response.ok) {
      let errBody;
      try {
        errBody = await response.json();
      } catch {
        errBody = { error: response.statusText };
      }
      const err = new Error(errBody.error || `HTTP ${response.status}`);
      err.status = response.status;
      err.data = errBody;
      throw err;
    }

    return await response.json();
  } catch (error) {
    console.warn(`[NammaSpeak API] Call to ${endpoint} failed:`, error.message);
    throw error;
  }
}

async function requestAudio(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Accept": "audio/mpeg, application/json",
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });
  if (!response.ok) {
    let body = {};
    try { body = await response.json(); } catch { /* non-JSON provider response */ }
    const error = new Error(body.error || `HTTP ${response.status}`);
    error.status = response.status;
    error.code = body.code;
    throw error;
  }
  return response.blob();
}

export const api = {
  async getAuth() {
    return request("/api/auth/me");
  },

  async createGuest(language = null) {
    return request("/api/auth/guest", {
      method: "POST",
      body: JSON.stringify({ language })
    });
  },

  async registerAccount(name, email, password, language) {
    return request("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password, language })
    });
  },

  async login(email, password) {
    return request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
  },

  async logout() {
    return request("/api/auth/logout", { method: "POST" });
  },

  async updateLanguage(language) {
    return request("/api/auth/language", {
      method: "POST",
      body: JSON.stringify({ language })
    });
  },

  // Health
  async getHealth() {
    return request("/api/health");
  },

  // Translations & Localization
  async getSupportedLanguages() {
    return request("/api/translations/languages");
  },

  async getTranslations(lang = "en") {
    return request(`/api/translations/${encodeURIComponent(lang)}`);
  },

  // Phrases & Categories
  async getCategories(lang = "en") {
    const qs = lang && lang !== "en" ? `?lang=${encodeURIComponent(lang)}` : "";
    return request(`/api/categories${qs}`);
  },

  async getPhrases(category = "all", search = "", lang = "en") {
    const params = new URLSearchParams();
    if (category && category !== "all") params.append("category", category);
    if (search) params.append("search", search);
    if (lang && lang !== "en") params.append("lang", lang);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request(`/api/phrases${qs}`);
  },

  async getPhrase(id, lang = "en") {
    const qs = lang && lang !== "en" ? `?lang=${encodeURIComponent(lang)}` : "";
    return request(`/api/phrases/${encodeURIComponent(id)}${qs}`);
  },

  // Practice Scenarios & Answer Submission
  async getScenarios(lang = "en") {
    const qs = lang && lang !== "en" ? `?lang=${encodeURIComponent(lang)}` : "";
    return request(`/api/practice/scenarios${qs}`);
  },

  async getScenario(id, lang = "en") {
    const qs = lang && lang !== "en" ? `?lang=${encodeURIComponent(lang)}` : "";
    return request(`/api/practice/scenarios/${encodeURIComponent(id)}${qs}`);
  },

  async submitAnswer(scenarioId, optionId, lang = "en") {
    return request("/api/practice/answer", {
      method: "POST",
      body: JSON.stringify({
        scenario_id: scenarioId,
        option_id: optionId,
        lang: lang
      })
    });
  },

  // Phrasebook (Saved Phrases)
  async getPhrasebook(lang = "en") {
    const qs = lang && lang !== "en" ? `?lang=${encodeURIComponent(lang)}` : "";
    return request(`/api/phrasebook${qs}`);
  },

  async savePhrase(phraseId) {
    return request("/api/phrasebook", {
      method: "POST",
      body: JSON.stringify({ phrase_id: phraseId })
    });
  },

  async unsavePhrase(phraseId) {
    return request(`/api/phrasebook/${encodeURIComponent(phraseId)}`, {
      method: "DELETE"
    });
  },

  // Progress & Adaptive Revision
  async getProgress() {
    return request("/api/progress");
  },

  async resetProgress() {
    return request("/api/progress", {
      method: "POST",
      body: JSON.stringify({ action: "reset" })
    });
  },

  async getRevisionList(lang = "en") {
    const qs = lang && lang !== "en" ? `?lang=${encodeURIComponent(lang)}` : "";
    return request(`/api/revision${qs}`);
  },

  async resolveRevision(phraseId) {
    return request("/api/revision/resolve", {
      method: "POST",
      body: JSON.stringify({ phrase_id: phraseId })
    });
  },

  // AI Assistant Structured Lessons & Explanations
  async sendAIChat(message, context = "", history = [], lang = "en") {
    return request("/api/ai/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        context,
        history,
        lang
      })
    });
  },

  async explainPhrase(phrase, question = "", lang = "en") {
    return request("/api/ai/explain", {
      method: "POST",
      body: JSON.stringify({
        phrase,
        question,
        lang
      })
    });
  },

  async getKannadaSpeech(phrase, signal) {
    return requestAudio("/api/speech/kannada", {
      method: "POST",
      signal,
      body: JSON.stringify({ phrase })
    });
  }
};
