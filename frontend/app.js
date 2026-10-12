/**
 * NammaSpeak — Main Application Controller
 */

import { api } from "./api.js";
import { 
  escapeHTML, 
  showToast, 
  speakKannada, 
  copyToClipboard, 
  createCategoryCardHTML, 
  createPhraseCardHTML,
  applyI18nToDOM,
  stopKannadaSpeech
} from "./ui.js";

// Application State
const state = {
  categories: [],
  phrases: [],
  savedPhrases: [],
  scenarios: [],
  revisionPhrases: [],
  progress: {
    answered: 0,
    correct: 0,
    accuracy: 0,
    best_score: 0,
    saved_count: 0,
    revision_count: 0
  },
  selectedCategory: "all",
  searchQuery: "",
  phraseLoadError: false,
  currentView: "explore",
  currentScenarioIndex: 0,
  scenarioAnswered: false,
  scenarioSessionCorrect: 0,
  aiHistory: [],
  backendConnected: false,
  aiProviderName: "Local Offline Engine",
  user: null,
  language: localStorage.getItem("nammaspeak_language") || "en",
  uiStrings: {},
  translationRequestId: 0,
  pendingRegistration: false
};

// DOM Helper
const $ = (id) => document.getElementById(id);

const LANGUAGE_KEY = "nammaspeak_language";

const uiTranslations = {
  en: {
    welcome: "Let's learn Kannada your way.",
    description: "Choose the language you're most comfortable with. We'll explain Kannada phrases in that language.",
    label: "I am most comfortable with",
    start: "Start learning Kannada",
    tagline: "Confidence grows with every conversation."
  },
  hi: {
    welcome: "आइए, अपनी भाषा में कन्नड़ सीखें।",
    description: "वह भाषा चुनें जिसमें आप सबसे सहज महसूस करते हैं।",
    label: "मेरी पसंदीदा भाषा",
    start: "कन्नड़ सीखना शुरू करें",
    tagline: "हर बातचीत के साथ आपका आत्मविश्वास बढ़ता है।"
  },
  bn: {
    welcome: "আপনার পছন্দের ভাষায় কন্নড় শিখুন।",
    description: "আপনি যে ভাষায় সবচেয়ে স্বচ্ছন্দ, সেটি বেছে নিন।",
    label: "আমার পছন্দের ভাষা",
    start: "কন্নড় শেখা শুরু করুন",
    tagline: "প্রতিটি কথোপকথনে আত্মবিশ্বাস বাড়ে।"
  },
  ta: {
    welcome: "உங்களுக்குப் பிடித்த மொழியில் கன்னடம் கற்போம்.",
    description: "நீங்கள் வசதியாகப் பேசும் மொழியைத் தேர்ந்தெடுக்கவும்.",
    label: "எனக்கு வசதியான மொழி",
    start: "கன்னடம் கற்கத் தொடங்குங்கள்",
    tagline: "ஒவ்வொரு உரையாடலும் நம்பிக்கையை வளர்க்கும்."
  },
  te: {
    welcome: "మీకు నచ్చిన భాషలో కన్నడ నేర్చుకుందాం.",
    description: "మీకు అత్యంత సౌకర్యంగా ఉండే భాషను ఎంచుకోండి.",
    label: "నాకు సౌకర్యమైన భాష",
    start: "కన్నడ నేర్చుకోవడం ప్రారంభించండి",
    tagline: "ప్రతి సంభాషణతో ఆత్మవిశ్వాసం పెరుగుతుంది."
  }
};

function getPreferredLanguage() {
  const language = localStorage.getItem(LANGUAGE_KEY) || "en";
  if (uiTranslations[language]) return language;
  localStorage.removeItem(LANGUAGE_KEY);
  return "en";
}

function text(key, fallback = "") {
  return state.uiStrings[key] || fallback || key;
}

function formatText(key, fallback, values = {}) {
  return Object.entries(values).reduce(
    (value, [name, replacement]) => value.replaceAll(`{${name}}`, String(replacement)),
    text(key, fallback)
  );
}

function initializeLanguageSelection() {
  const panel = $("language-view");
  const select = $("preferred-language");
  const saveButton = $("save-language");

  if (!panel || !select || !saveButton) {
    console.error("Language onboarding elements are missing from index.html");
    return;
  }

  select.value = getPreferredLanguage();

  function updateWelcome(language) {
    const t = uiTranslations[language] || uiTranslations.en;

    if ($("welcome-title")) $("welcome-title").textContent = text("onboarding_title", t.welcome);
    if ($("welcome-description")) $("welcome-description").textContent = text("onboarding_description", t.description);
    if ($("language-label")) $("language-label").textContent = text("onboarding_label", t.label);
    saveButton.textContent = text("onboarding_btn", `${t.start} →`);
  }

  updateWelcome(select.value);

  select.addEventListener("change", () => {
    updateWelcome(select.value);
  });

  saveButton.addEventListener("click", async () => {
    await changeLanguage(select.value);
    if (state.user) {
      try {
        const response = await api.updateLanguage(select.value);
        state.user = response.user || state.user;
      } catch (error) {
        console.warn("Could not save language preference:", error.message);
      }
    }
    showAppShell("explore");
    await loadApplicationData();
  });

  $("topbar-language")?.addEventListener("change", (event) => {
    changeLanguage(event.target.value);
  });
}

function showAuthScreen(screenName) {
  $("app-shell").hidden = true;
  const authScreens = ["welcome", "signin", "register", "language"];
  authScreens.forEach((name) => {
    const el = $(`${name}-view`);
    if (el) el.hidden = name !== screenName;
  });

  if (screenName === "signin") {
    if ($("sign-in-error")) $("sign-in-error").textContent = "";
    if ($("sign-in-password")) $("sign-in-password").value = "";
    const signinBackBtn = $("signin-back-btn");
    if (signinBackBtn) {
      signinBackBtn.textContent = state.user?.account_type === "guest" ? "← Back to Account" : "← Back to Welcome";
    }
    setTimeout(() => $("sign-in-email")?.focus(), 50);
  } else if (screenName === "register") {
    if ($("register-error")) $("register-error").textContent = "";
    if ($("register-password")) $("register-password").value = "";
    const banner = $("register-guest-merge-banner");
    const isGuest = state.user?.account_type === "guest";
    if (banner) {
      banner.hidden = !isGuest;
      banner.style.display = isGuest ? "" : "none";
    }
    const backBtn = $("register-back-btn");
    if (backBtn) {
      backBtn.textContent = isGuest ? "← Back to Account" : "← Back to Welcome";
    }
    if ($("register-language")) {
      $("register-language").value = state.language || getPreferredLanguage();
    }
    setTimeout(() => $("register-name")?.focus(), 50);
  } else if (screenName === "language") {
    if ($("preferred-language")) {
      $("preferred-language").value = state.language || getPreferredLanguage();
    }
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showAppShell(viewName = "explore") {
  ["welcome", "signin", "register", "language"].forEach((name) => {
    const el = $(`${name}-view`);
    if (el) el.hidden = true;
  });
  $("app-shell").hidden = false;
  setView(viewName);
}

async function loadApplicationData() {
  await loadTranslations(state.language, true);
  await Promise.allSettled([
    loadCategories(),
    loadPhrases(),
    loadSavedPhrases(),
    loadScenarios(),
    loadProgress(),
    loadRevisionQueue()
  ]);
  renderAll();
}

async function loadTranslations(language, showFallbackNotice = false) {
  const requestId = ++state.translationRequestId;
  try {
    const response = await api.getTranslations(language);
    if (requestId !== state.translationRequestId || language !== state.language) {
      return null;
    }
    state.uiStrings = response.strings || {};
    document.documentElement.lang = language;
    applyI18nToDOM(state.uiStrings);
    if (response.is_fallback && showFallbackNotice) {
      showToast(text("status_fallback_notice", "Using offline fallback translations"), "info");
    }
    return response;
  } catch (err) {
    if (requestId !== state.translationRequestId || language !== state.language) {
      return null;
    }
    console.warn("UI translation request failed:", err.message);
    state.uiStrings = {};
    return null;
  }
}

async function changeLanguage(language) {
  const nextLanguage = uiTranslations[language] ? language : "en";
  state.language = nextLanguage;
  localStorage.setItem(LANGUAGE_KEY, nextLanguage);
  $("topbar-language") && ($("topbar-language").value = nextLanguage);
  $("preferred-language") && ($("preferred-language").value = nextLanguage);
  await loadTranslations(nextLanguage, true);
  // Static UI is already localized. Refresh dynamic data in the background so
  // a slow phrase/provider request cannot delay the language switch.
  renderAll();
  Promise.allSettled([
    loadCategories(),
    loadPhrases(),
    loadSavedPhrases(),
    loadScenarios(),
    loadRevisionQueue()
  ]).then(() => {
    if (state.language === nextLanguage) {
      renderAll();
    }
  });
}

/**
 * Initialize Application
 */
async function initApp() {
  initializeLanguageSelection();
  setupAccessHandlers();
  setupEventListeners();
  $("topbar-language") && ($("topbar-language").value = state.language);

  try {
    const auth = await api.getAuth();
    if (!auth.authenticated) {
      showAuthScreen("welcome");
      return;
    }
    state.user = auth.user;
    state.language = auth.user.preferred_language || getPreferredLanguage();
    localStorage.setItem(LANGUAGE_KEY, state.language);
    showAppShell("explore");
    renderAccount();
  } catch (err) {
    console.warn("Authentication status check failed:", err.message);
    showAuthScreen("welcome");
    return;
  }

  try {
    // 1. Health check & Backend metadata
    const health = await api.getHealth();
    state.backendConnected = true;
    state.aiProviderName = health.ai_provider || "Local Offline Engine";
    updateBackendStatusBadge(true, state.aiProviderName);
  } catch (err) {
    console.warn("Backend health check failed:", err.message);
    state.backendConnected = false;
    updateBackendStatusBadge(false, "Offline / Local Mode");
  }

  await loadApplicationData();
}

function renderAccount() {
  const user = state.user;
  if (!user) {
    const upgradeBanner = $("guest-upgrade-banner");
    if (upgradeBanner) {
      upgradeBanner.hidden = true;
      upgradeBanner.style.display = "none";
    }
    if ($("topbar-account-avatar")) $("topbar-account-avatar").textContent = "G";
    if ($("topbar-account-name")) $("topbar-account-name").textContent = "Guest";
    if ($("topbar-account-badge")) $("topbar-account-badge").textContent = "Guest";
    if ($("nav-account-type-badge")) $("nav-account-type-badge").textContent = "Guest";
    $("topbar-account-btn")?.classList.remove("registered");
    return;
  }

  const isRegistered = user.account_type === "registered";
  const isGuest = user.account_type === "guest";
  const displayName = user.name || (isRegistered ? "Learner" : "Guest Learner");
  const displayEmail = isRegistered ? (user.email || "") : "guest@device.local";
  const initial = (user.name ? user.name[0].toUpperCase() : (isRegistered ? "A" : "G"));

  if ($("account-name")) $("account-name").textContent = displayName;
  if ($("account-email")) {
    $("account-email").textContent = displayEmail;
    $("account-email").style.display = displayEmail ? "" : "none";
  }
  if ($("account-kind")) {
    $("account-kind").textContent = isRegistered
      ? "Your learning progress, saved phrases, and quiz scores are synced with this account."
      : "Guest progress is saved on this device. Create an account to preserve it across devices.";
  }
  if ($("account-badge")) {
    $("account-badge").textContent = isRegistered ? "Registered Account" : "Guest Mode";
    $("account-badge").className = `account-status-badge ${isRegistered ? "registered" : "guest"}`;
  }
  const avatarLarge = $("account-avatar-large");
  if (avatarLarge) {
    avatarLarge.textContent = initial;
    avatarLarge.className = `account-avatar-large ${isRegistered ? "" : "guest"}`;
  }

  // Topbar profile pill button
  const topbarBtn = $("topbar-account-btn");
  if (topbarBtn) {
    topbarBtn.classList.toggle("registered", isRegistered);
  }
  if ($("topbar-account-avatar")) $("topbar-account-avatar").textContent = initial;
  if ($("topbar-account-name")) {
    const firstName = user.name ? user.name.split(" ")[0] : (isRegistered ? "Learner" : "Guest");
    $("topbar-account-name").textContent = firstName;
  }
  if ($("topbar-account-badge")) {
    $("topbar-account-badge").textContent = isRegistered ? "Account" : "Guest";
  }
  if ($("nav-account-type-badge")) {
    $("nav-account-type-badge").textContent = isRegistered ? "Account" : "Guest";
  }

  // Guest Upgrade Banner (Requirement: strictly visible ONLY for guest sessions)
  const upgradeBanner = $("guest-upgrade-banner");
  if (upgradeBanner) {
    upgradeBanner.hidden = !isGuest;
    upgradeBanner.style.display = isGuest ? "" : "none";
  }

  // Language selector in account
  if ($("account-language")) $("account-language").value = state.language;

  // Stats snapshot in account
  const savedCount = state.progress.saved_count !== undefined
    ? state.progress.saved_count
    : (state.savedPhrases ? state.savedPhrases.length : 0);
  const answeredCount = state.progress.answered || 0;
  const accuracyText = (state.progress.accuracy || 0) + "%";
  const revisionCount = state.progress.revision_count !== undefined
    ? state.progress.revision_count
    : (state.revisionPhrases ? state.revisionPhrases.length : 0);

  if ($("account-stat-saved")) $("account-stat-saved").textContent = String(savedCount);
  if ($("account-stat-answered")) $("account-stat-answered").textContent = String(answeredCount);
  if ($("account-stat-accuracy")) $("account-stat-accuracy").textContent = accuracyText;
  if ($("account-stat-revision")) $("account-stat-revision").textContent = String(revisionCount);
}

/**
 * Data Loading
 */
async function loadCategories() {
  const requestedLanguage = state.language;
  try {
    const data = await api.getCategories(requestedLanguage);
    if (requestedLanguage !== state.language) return;
    state.categories = data.categories || [];
  } catch (err) {
    if (requestedLanguage !== state.language) return;
    // Fallback default categories
    state.categories = [
      { id: "all", name: text("cat_all", "All phrases"), sub: text("cat_all_sub", "Comprehensive collection"), emoji: "✳", bg: "#f7e5d8" },
      { id: "transport", name: text("cat_transport", "Getting around"), sub: text("cat_transport_sub", "Buses, autos, directions"), emoji: "🚌", bg: "#e3e9dc" },
      { id: "food", name: text("cat_food", "Food & dining"), sub: text("cat_food_sub", "Cafés, darshinis, orders"), emoji: "☕", bg: "#f5e8c8" },
      { id: "shopping", name: text("cat_shopping", "Shopping & markets"), sub: text("cat_shopping_sub", "Prices, bargaining, items"), emoji: "🛍️", bg: "#e9e4f4" },
      { id: "health", name: text("cat_health", "Healthcare & clinic"), sub: text("cat_health_sub", "Pharmacy, doctor, emergency"), emoji: "🏥", bg: "#fce4e4" },
      { id: "work", name: text("cat_work", "Work & campus"), sub: text("cat_work_sub", "Greetings, meetings, office"), emoji: "💼", bg: "#e0edf4" },
      { id: "help", name: text("cat_help", "Everyday courtesy"), sub: text("cat_help_sub", "Polite requests & help"), emoji: "🤝", bg: "#f4dfd7" }
    ];
  }
}

async function loadPhrases() {
  const requestedLanguage = state.language;
  state.phraseLoadError = false;
  try {
    const data = await api.getPhrases(state.selectedCategory, state.searchQuery, requestedLanguage);
    if (requestedLanguage !== state.language) return;
    state.phrases = data.phrases || [];
  } catch (err) {
    if (requestedLanguage !== state.language) return;
    state.phraseLoadError = true;
    state.phrases = [];
    console.error("Failed to load phrases:", err);
  }
}

async function loadSavedPhrases() {
  const requestedLanguage = state.language;
  try {
    const data = await api.getPhrasebook(requestedLanguage);
    if (requestedLanguage !== state.language) return;
    state.savedPhrases = data.phrases || [];
  } catch (err) {
    console.error("Failed to load saved phrases:", err);
  }
}

async function loadScenarios() {
  const requestedLanguage = state.language;
  try {
    const data = await api.getScenarios(requestedLanguage);
    if (requestedLanguage !== state.language) return;
    state.scenarios = data.scenarios || [];
  } catch (err) {
    console.error("Failed to load scenarios:", err);
  }
}

async function loadProgress() {
  try {
    const prog = await api.getProgress();
    state.progress = { ...state.progress, ...prog };
  } catch (err) {
    console.error("Failed to load progress:", err);
  }
}

async function loadRevisionQueue() {
  const requestedLanguage = state.language;
  try {
    const rev = await api.getRevisionList(requestedLanguage);
    if (requestedLanguage !== state.language) return;
    state.revisionPhrases = rev.phrases || [];
    state.progress.revision_count = state.revisionPhrases.length;
  } catch (err) {
    console.error("Failed to load revision queue:", err);
  }
}

/**
 * Rendering Logic
 */
function renderAll() {
  renderCategories();
  renderPhrases();
  renderSavedPhrases();
  renderProgressStats();
  renderRevisionQueue();
  renderScenarioQuestion();
  renderAccount();
}

function renderCategories() {
  const container = $("category-grid");
  if (!container) return;
  container.innerHTML = state.categories.map(c => 
    createCategoryCardHTML(c, c.id === state.selectedCategory)
  ).join("");
}

function renderPhrases() {
  const container = $("phrase-grid");
  const emptyState = $("empty-state");
  const title = $("phrase-title");
  const count = $("phrase-count");
  if (!container) return;

  const savedIds = new Set(state.savedPhrases.map(p => p.id));
  const list = state.phrases;

  if (title) {
    if (state.searchQuery) {
      title.textContent = formatText("explore_search_results", `Search results for "{query}"`, { query: state.searchQuery });
    } else {
      const cat = state.categories.find(c => c.id === state.selectedCategory);
      title.textContent = cat ? cat.name : text("explore_essentials_heading", "Everyday essentials");
    }
  }

  if (count) {
    count.textContent = formatText(
      list.length === 1 ? "explore_phrase_count_one" : "explore_phrase_count_many",
      list.length === 1 ? "{count} phrase" : "{count} phrases",
      { count: list.length }
    );
  }

  if (list.length === 0) {
    container.innerHTML = "";
    if (emptyState) {
      emptyState.classList.remove("hidden");
      if (state.phraseLoadError) {
        emptyState.textContent = text("explore_search_error", "We could not load phrases right now. Please try again.");
      } else if (state.searchQuery) {
        emptyState.innerHTML = `
          <div>${escapeHTML(formatText("explore_empty", "No phrases match your search for \"{query}\".", { query: state.searchQuery }))}</div>
          <button class="button button-dark empty-ask-ai" data-ask-ai="${escapeHTML(state.searchQuery)}">
            ${escapeHTML(text("explore_ask_ai", "Ask AI Chat"))}
          </button>
        `;
      }
    }
  } else {
    if (emptyState) emptyState.classList.add("hidden");
    container.innerHTML = list.map(p => createPhraseCardHTML(p, savedIds.has(p.id), state.uiStrings)).join("");
  }
}

function renderSavedPhrases() {
  const container = $("saved-grid");
  const empty = $("saved-empty");
  const navCount = $("saved-count");
  const stripCount = $("saved-strip-count");
  if (!container) return;

  const count = state.savedPhrases.length;
  if (navCount) navCount.textContent = count;
  if (stripCount) stripCount.textContent = count;

  if (count === 0) {
    container.innerHTML = "";
    if (empty) empty.classList.remove("hidden");
  } else {
    if (empty) empty.classList.add("hidden");
    container.innerHTML = state.savedPhrases.map(p => createPhraseCardHTML(p, true, state.uiStrings)).join("");
  }
}

function renderProgressStats() {
  const p = state.progress;
  if ($("learned-count")) $("learned-count").textContent = p.answered || 0;
  if ($("streak-count")) $("streak-count").textContent = `${p.accuracy || 0}%`;
  if ($("best-score")) $("best-score").textContent = `${p.best_score || 0}%`;
  if ($("questions-answered")) $("questions-answered").textContent = p.answered || 0;
  if ($("saved-strip-count")) $("saved-strip-count").textContent = state.savedPhrases.length;
  if ($("saved-count")) $("saved-count").textContent = state.savedPhrases.length;

  const revCount = $("revision-count");
  if (revCount) revCount.textContent = state.revisionPhrases.length;
  const revStrip = $("revision-strip-count");
  if (revStrip) revStrip.textContent = state.revisionPhrases.length;
}

function renderRevisionQueue() {
  const container = $("revision-grid");
  const empty = $("revision-empty");
  if (!container) return;

  const list = state.revisionPhrases;
  if (list.length === 0) {
    container.innerHTML = "";
    if (empty) empty.classList.remove("hidden");
  } else {
    if (empty) empty.classList.add("hidden");
    container.innerHTML = list.map(p => `
      <article class="phrase-card revision-card" data-phrase-id="${escapeHTML(p.id)}">
        <div class="phrase-card-top">
          <span class="phrase-tag tag-warning">${escapeHTML(text("revision_eyebrow", "Adaptive Revision"))} • ${p.mistakes || 1}</span>
          <button class="resolve-button button" data-resolve-revision="${escapeHTML(p.id)}" title="${escapeHTML(text("revision_mastered_btn", "Mark as mastered"))}">
            ${escapeHTML(text("revision_mastered_btn", "✓ Mastered"))}
          </button>
        </div>
        <div class="phrase-kannada" lang="kn">${escapeHTML(p.kn)}</div>
        <div class="phrase-roman">${escapeHTML(p.roman)}</div>
        <div class="phrase-meaning">${escapeHTML(p.meaning)}</div>
        <div class="phrase-context">${escapeHTML(p.context)}</div>
        <div class="phrase-card-bottom">
          <button class="listen-button" data-speak="${escapeHTML(p.id)}">${escapeHTML(text("card_listen", "▶ Listen"))}</button>
          <button class="listen-button slow-listen-button" data-speak="${escapeHTML(p.id)}" data-slow-speak="true">${escapeHTML(text("card_slow_listen", "▶ Slow Listen"))}</button>
          <button class="explain-button" data-explain="${escapeHTML(p.id)}">${escapeHTML(text("revision_why_btn", "💡 Why did I miss this?"))}</button>
        </div>
      </article>
    `).join("");
  }
}

function renderScenarioQuestion() {
  if (!state.scenarios.length) return;
  const s = state.scenarios[state.currentScenarioIndex];
  if (!s) return;

  state.scenarioAnswered = false;

  if ($("speaker-name")) $("speaker-name").textContent = s.speaker;
  if ($("scenario-question")) $("scenario-question").textContent = s.question;
  if ($("scenario-context")) $("scenario-context").textContent = s.context;
  if ($("scenario-step")) {
    $("scenario-step").textContent = `${String(state.currentScenarioIndex + 1).padStart(2, "0")} / ${String(state.scenarios.length).padStart(2, "0")}`;
  }
  if ($("quiz-progress")) {
    $("quiz-progress").textContent = `${text("practice_scenario_top", "Question")} ${state.currentScenarioIndex + 1} / ${state.scenarios.length}`;
  }

  const feedback = $("answer-feedback");
  if (feedback) {
    feedback.className = "answer-feedback hidden";
    feedback.textContent = "";
  }

  const nextBtn = $("next-question");
  if (nextBtn) {
    nextBtn.disabled = true;
    nextBtn.textContent = state.currentScenarioIndex === state.scenarios.length - 1
      ? text("practice_finish_btn", "Finish practice ✓")
      : text("practice_next_btn", "Next question →");
  }

  const optionsContainer = $("answer-options");
  if (optionsContainer && s.options) {
    optionsContainer.innerHTML = s.options.map((opt, i) => `
      <button class="answer-option" data-answer="${escapeHTML(opt.id || String(i))}">
        <span class="option-letter">${String.fromCharCode(65 + i)}</span>
        <span class="option-kannada" lang="kn">${escapeHTML(opt.text)}</span>
        ${opt.roman ? `<small class="option-roman">${escapeHTML(opt.roman)}</small>` : ""}
      </button>
    `).join("");
  }
}

/**
 * Practice Scenario Interaction
 */
async function handleAnswerSelection(optionId) {
  if (state.scenarioAnswered) return;
  state.scenarioAnswered = true;

  const scenario = state.scenarios[state.currentScenarioIndex];
  if (!scenario) return;

  // Submit to backend for validation and persistent progress recording
  let result;
  try {
    result = await api.submitAnswer(scenario.id, optionId, state.language);
  } catch (err) {
    // Local fallback evaluation if network drop
    const opt = scenario.options.find(o => o.id === optionId || String(scenario.options.indexOf(o)) === optionId);
    result = {
      is_correct: opt ? Boolean(opt.correct) : false,
      why: opt ? opt.why : "",
      correct_option: scenario.options.find(o => o.correct)
    };
  }

  // Visual styling of options
  const optionButtons = document.querySelectorAll("#answer-options .answer-option");
  optionButtons.forEach(btn => {
    btn.disabled = true;
    const btnOptId = btn.dataset.answer;
    if (result.correct_option && (btnOptId === result.correct_option.id || btn.querySelector(".option-kannada")?.textContent === result.correct_option.text)) {
      btn.classList.add("correct");
    } else if (btnOptId === optionId && !result.is_correct) {
      btn.classList.add("incorrect");
    }
  });

  const feedback = $("answer-feedback");
  if (feedback) {
    feedback.classList.remove("hidden");
    if (result.is_correct) {
      state.scenarioSessionCorrect++;
      feedback.className = "answer-feedback correct-feedback";
      feedback.innerHTML = `<strong>${escapeHTML(text("feedback_correct_prefix", "✓ Correct!"))}</strong> ${escapeHTML(result.why)}`;
    } else {
      feedback.className = "answer-feedback bad-feedback";
      feedback.innerHTML = `<strong>${escapeHTML(text("feedback_incorrect_prefix", "Not quite."))}</strong> ${escapeHTML(result.why)}<br><small>${escapeHTML(text("feedback_revision_hint", "This phrase has been added to your Adaptive Revision queue for review."))}</small>`;
    }
  }

  // Refresh progress stats & revision queue from backend
  await Promise.allSettled([loadProgress(), loadRevisionQueue()]);
  renderProgressStats();

  const nextBtn = $("next-question");
  if (nextBtn) nextBtn.disabled = false;
}

function handleNextQuestion() {
  if (!state.scenarioAnswered) return;

  if (state.currentScenarioIndex < state.scenarios.length - 1) {
    state.currentScenarioIndex++;
    renderScenarioQuestion();
  } else {
    // Session completed screen
    const total = state.scenarios.length;
    const score = Math.round((state.scenarioSessionCorrect / total) * 100);

    if ($("speaker-name")) $("speaker-name").textContent = text("practice_complete_title", "Practice Round Complete!");
    if ($("scenario-question")) $("scenario-question").textContent = `${score}% (${state.scenarioSessionCorrect} / ${total})`;
    if ($("scenario-context")) {
      $("scenario-context").textContent = score === 100 
        ? text("practice_complete_excellent", "Excellent! You demonstrated solid conversational instincts for everyday life in Karnataka.")
        : text("practice_complete_progress", "Good progress! Reviewing your mistakes will help you lock in these everyday phrases.");
    }

    const optionsContainer = $("answer-options");
    if (optionsContainer) {
      optionsContainer.innerHTML = `
        <button class="answer-option action-btn" id="retry-practice-btn">
          <span class="option-letter">↻</span>
          <span>${escapeHTML(text("practice_retry_btn", "Try This Conversation Round Again"))}</span>
        </button>
        <button class="answer-option action-btn" id="view-revision-btn">
          <span class="option-letter">⚡</span>
          <span>${escapeHTML(text("practice_view_revision_btn", "Open Adaptive Revision"))} (${state.revisionPhrases.length})</span>
        </button>
        <button class="answer-option action-btn" id="back-explore-btn">
          <span class="option-letter">⌕</span>
          <span>${escapeHTML(text("practice_back_explore_btn", "Explore More Phrases"))}</span>
        </button>
      `;

      $("retry-practice-btn")?.addEventListener("click", startPracticeSession);
      $("view-revision-btn")?.addEventListener("click", () => setView("revision"));
      $("back-explore-btn")?.addEventListener("click", () => setView("explore"));
    }

    const feedback = $("answer-feedback");
    if (feedback) {
      feedback.className = "answer-feedback";
      feedback.innerHTML = `${escapeHTML(text("practice_session_saved", "Session saved. Real accuracy:"))} <strong>${score}%</strong>. ${state.revisionPhrases.length > 0 ? escapeHTML(text("feedback_revision_hint", "You have tricky phrases queued for adaptive revision.")) : escapeHTML(text("practice_no_mistakes", "No outstanding mistakes!"))}`;
    }

    if ($("scenario-step")) $("scenario-step").textContent = "DONE";
    if ($("quiz-progress")) $("quiz-progress").textContent = "Round Finished";
    const nextBtn = $("next-question");
    if (nextBtn) {
      nextBtn.disabled = true;
      nextBtn.textContent = text("practice_finished_btn", "Finished");
    }
  }
}

function startPracticeSession() {
  state.currentScenarioIndex = 0;
  state.scenarioSessionCorrect = 0;
  setView("practice");
  renderScenarioQuestion();
}

/**
 * Phrasebook Actions
 */
async function toggleSavePhrase(phraseId) {
  const isAlreadySaved = state.savedPhrases.some(p => p.id === phraseId);
  try {
    if (isAlreadySaved) {
      await api.unsavePhrase(phraseId);
      state.savedPhrases = state.savedPhrases.filter(p => p.id !== phraseId);
      showToast(text("toast_unsaved", "Phrase removed from phrasebook"));
    } else {
      await api.savePhrase(phraseId);
      const found = state.phrases.find(p => p.id === phraseId);
      if (found) state.savedPhrases.unshift({ ...found, is_saved: true });
      showToast(text("toast_saved", "Saved to your phrasebook! ♥"));
    }
    renderPhrases();
    renderSavedPhrases();
    renderProgressStats();
  } catch (err) {
    showToast(`Failed to update phrasebook: ${err.message}`);
  }
}

/**
 * Adaptive Revision Actions
 */
async function resolveRevisionPhrase(phraseId) {
  try {
    await api.resolveRevision(phraseId);
    state.revisionPhrases = state.revisionPhrases.filter(p => p.id !== phraseId);
    state.progress.revision_count = state.revisionPhrases.length;
    renderRevisionQueue();
    renderProgressStats();
    showToast(text("toast_mastered", "Phrase marked as mastered! Keep going. ✓"));
  } catch (err) {
    showToast("Error updating revision status");
  }
}

/**
 * Phrase Explanation Modal / Tooltip
 */
async function explainPhraseContext(phraseId) {
  const p = state.phrases.find(x => x.id === phraseId) || state.savedPhrases.find(x => x.id === phraseId);
  if (!p) return;

  const modal = $("explain-modal");
  const title = $("explain-modal-title");
  const body = $("explain-modal-body");
  if (!modal || !title || !body) return;

  title.textContent = `${text("modal_title", "Phrase Context & Etiquette")}: "${p.kn}" (${p.roman})`;
  body.innerHTML = `
    <div class="explain-loading">
      <div class="spinner"></div>
      <p>${escapeHTML(text("status_checking", "Analyzing phrase context and everyday nuances..."))}</p>
    </div>
  `;
  modal.classList.remove("hidden");

  try {
    const res = await api.explainPhrase(p.kn, p.meaning, state.language);
    body.innerHTML = `
      <div class="explain-content">
        <div class="explain-block">
          <strong>${escapeHTML(text("modal_meaning_label", "Meaning & Usage:"))}</strong>
          <p>${escapeHTML(res.explanation || p.context)}</p>
        </div>
        <div class="explain-block">
          <strong>${escapeHTML(text("modal_formality_label", "Formality & Politeness:"))}</strong>
          <p>${escapeHTML(res.formality || p.formality || "Everyday Polite")}</p>
        </div>
        ${res.cultural_context ? `
        <div class="explain-block">
          <strong>${escapeHTML(text("modal_cultural_label", "Cultural Context:"))}</strong>
          <p>${escapeHTML(res.cultural_context)}</p>
        </div>` : ""}
        <div class="explain-meta">
          <small>${escapeHTML(text("modal_source_label", "Source:"))} ${escapeHTML(res.provider || state.aiProviderName)} • ${res.disclaimer || text("modal_verified_phrase", "Verified everyday phrase")}</small>
        </div>
        <div class="modal-actions">
          <button class="button button-dark" id="modal-speak-btn">${escapeHTML(text("modal_listen_btn", "▶ Listen Pronunciation"))}</button>
          <button class="button" id="modal-close-inner-btn">${escapeHTML(text("modal_close", "Close"))}</button>
        </div>
      </div>
    `;

    $("modal-speak-btn")?.addEventListener("click", (event) => {
      if (event.currentTarget.classList.contains("is-speaking")) {
        stopKannadaSpeech();
        return;
      }
      speakKannada(p.speech || p.kn, p.roman, state.uiStrings, event.currentTarget);
    });
    $("modal-close-inner-btn")?.addEventListener("click", () => modal.classList.add("hidden"));
  } catch (err) {
    body.innerHTML = `
      <div class="explain-content">
        <p><strong>${escapeHTML(text("modal_standard_context", "Standard Context:"))}</strong> ${escapeHTML(p.context)}</p>
        <p><strong>${escapeHTML(text("modal_formality_label", "Formality & Politeness:"))}</strong> ${escapeHTML(p.formality || text("modal_polite_everyday", "Polite Everyday"))}</p>
        <p><strong>${escapeHTML(text("modal_english_meaning", "Meaning:"))}</strong> ${escapeHTML(p.meaning)}</p>
        <button class="button button-dark" id="modal-close-inner-btn">${escapeHTML(text("modal_close", "Close"))}</button>
      </div>
    `;
    $("modal-close-inner-btn")?.addEventListener("click", () => modal.classList.add("hidden"));
  }
}

/**
 * AI Conversation Companion Chat
 */
async function sendAIChatMessage() {
  const input = $("ai-chat-input");
  const msg = input ? input.value : "";
  if (!msg.trim()) return;

  const scenarioSelector = $("ai-context-selector");
  const context = scenarioSelector ? scenarioSelector.value : "Everyday life in Bengaluru and Karnataka";

  // Append user message
  appendAIChatBubble("user", msg);
  input.value = "";

  const sendBtn = $("ai-chat-send");
  if (sendBtn) sendBtn.disabled = true;

  try {
    const res = await api.sendAIChat(msg, context, state.aiHistory, state.language);
    appendAIChatBubble(
      "ai",
      res.reply_kn,
      res.reply_roman,
      res.reply_en,
      res.learner_tip,
      res.disclaimer,
      res.mode === "offline_fallback"
    );
    state.aiHistory.push({ role: "user", text: msg });
    state.aiHistory.push({ role: "model", text: res.reply_kn });
  } catch (err) {
    appendAIChatBubble(
      "ai",
      text("ai_error_kn", "ನಮಸ್ಕಾರ! ಸಂಪರ್ಕದಲ್ಲಿ ತೊಂದರೆ ಆಗಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಪ್ರಯತ್ನಿಸಿ."),
      text("ai_error_roman", "Namaskāra! Saṁparkadalli tondare āgide."),
      text("ai_error_meaning", "Could not reach conversation engine. Please try again."),
      text("ai_error_tip", "AI is temporarily unavailable. Please try again later.")
    );
  } finally {
    if (sendBtn) sendBtn.disabled = false;
  }
}

function appendAIChatBubble(sender, knText, roman = "", en = "", tip = "", disclaimer = "", isFallback = false) {
  const historyContainer = $("ai-chat-history");
  if (!historyContainer) return;

  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${sender}-bubble`;

  if (sender === "user") {
    bubble.innerHTML = `
      <div class="bubble-sender">${escapeHTML(text("ai_user_label", "You"))}</div>
      <div class="bubble-text">${escapeHTML(knText)}</div>
    `;
  } else {
    bubble.innerHTML = `
      <div class="bubble-sender">
        <span>${escapeHTML(text("ai_companion_label", "NammaSpeak Companion"))}</span>
        <button class="bubble-speak-btn" aria-label="${escapeHTML(text("ai_listen_aria", "Listen to reply"))}">▶</button>
      </div>
      <div class="bubble-kannada" lang="kn">${escapeHTML(knText)}</div>
      ${roman ? `<div class="bubble-roman">${escapeHTML(roman)}</div>` : ""}
      ${en ? `<div class="bubble-meaning">${escapeHTML(en)}</div>` : ""}
      ${tip ? `<div class="bubble-tip">💡 <strong>${escapeHTML(text("ai_tip_label", "Tip:"))}</strong> ${escapeHTML(tip)}</div>` : ""}
      ${isFallback ? `<div class="bubble-disclaimer"><small>${escapeHTML(text("ai_fallback_notice", "Offline fallback used — this is not a Gemini-generated answer."))}</small></div>` : ""}
      ${disclaimer ? `<div class="bubble-disclaimer"><small>${escapeHTML(disclaimer)}</small></div>` : ""}
    `;

    bubble.querySelector(".bubble-speak-btn")?.addEventListener("click", (event) => {
      if (event.currentTarget.classList.contains("is-speaking")) {
        stopKannadaSpeech();
        return;
      }
      speakKannada(knText, roman, state.uiStrings, event.currentTarget);
    });
  }

  historyContainer.appendChild(bubble);
  historyContainer.scrollTop = historyContainer.scrollHeight;
}

/**
 * View Management
 */
function setView(viewName) {
  state.currentView = viewName;
  const views = ["explore", "practice", "saved", "revision", "ai", "account"];

  views.forEach(v => {
    const el = $(`${v}-view`);
    if (el) el.classList.toggle("hidden", v !== viewName);
  });

  document.querySelectorAll(".nav-link").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.view === viewName);
  });
  $("topbar-account-btn")?.classList.toggle("active", viewName === "account");

  if (viewName === "saved") renderSavedPhrases();
  if (viewName === "revision") renderRevisionQueue();
  if (viewName === "account") renderAccount();

  window.scrollTo({ top: 0, behavior: "smooth" });
}

function updateBackendStatusBadge(isConnected, providerName) {
  const badge = $("backend-status");
  if (!badge) return;
  badge.className = `status-pill ${isConnected ? "online" : "offline"}`;
  badge.innerHTML = `<span class="status-dot"></span> ${isConnected ? `${escapeHTML(text("status_connected", "Backend Connected"))} • ${escapeHTML(providerName)}` : escapeHTML(text("status_offline", "Offline Mode"))}`;
}

/**
 * Event Listeners
 */
function setupEventListeners() {
  // Navigation
  document.addEventListener("click", async (e) => {
    const askAiButton = e.target.closest("[data-ask-ai]");
    if (askAiButton) {
      const input = $("ai-chat-input");
      setView("ai");
      if (input) {
        input.value = askAiButton.dataset.askAi || "";
        input.focus();
      }
      return;
    }

    // Nav links
    const navBtn = e.target.closest("[data-view]");
    if (navBtn) {
      setView(navBtn.dataset.view);
      return;
    }

    // Category selection
    const catBtn = e.target.closest("[data-category]");
    if (catBtn) {
      state.selectedCategory = catBtn.dataset.category;
      state.searchQuery = "";
      if ($("search-input")) $("search-input").value = "";
      renderCategories();
      await loadPhrases();
      renderPhrases();
      return;
    }

    // Audio Playback
    const speakBtn = e.target.closest("[data-speak]");
    if (speakBtn) {
      if (speakBtn.classList.contains("is-speaking")) {
        stopKannadaSpeech();
        return;
      }
      const phraseId = speakBtn.dataset.speak;
      const p = state.phrases.find(x => x.id === phraseId) || state.savedPhrases.find(x => x.id === phraseId) || state.revisionPhrases.find(x => x.id === phraseId);
      if (p) {
        speakKannada(p.speech || p.kn, p.roman, state.uiStrings, speakBtn, speakBtn.dataset.slowSpeak === "true" ? 0.8 : 1);
      }
      return;
    }

    // Copy to clipboard
    const copyBtn = e.target.closest("[data-copy]");
    if (copyBtn) {
      await copyToClipboard(copyBtn.dataset.copy, "Kannada text");
      return;
    }

    // Save/Unsave phrase
    const saveBtn = e.target.closest("[data-save]");
    if (saveBtn) {
      await toggleSavePhrase(saveBtn.dataset.save);
      return;
    }

    // Explain phrase context
    const explainBtn = e.target.closest("[data-explain]");
    if (explainBtn) {
      explainPhraseContext(explainBtn.dataset.explain);
      return;
    }

    // Resolve revision
    const resolveBtn = e.target.closest("[data-resolve-revision]");
    if (resolveBtn) {
      await resolveRevisionPhrase(resolveBtn.dataset.resolveRevision);
      return;
    }

    // Answer option clicked
    const answerBtn = e.target.closest("[data-answer]");
    if (answerBtn) {
      handleAnswerSelection(answerBtn.dataset.answer);
      return;
    }

    // Close Modal on backdrop
    const modal = $("explain-modal");
    if (modal && e.target === modal) {
      modal.classList.add("hidden");
    }
  });

  // Search input with debounce
  let searchTimeout;
  $("search-input")?.addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(async () => {
      state.searchQuery = e.target.value;
      await loadPhrases();
      renderPhrases();
    }, 250);
  });

  // Hero Quick Actions
  $("start-practice")?.addEventListener("click", startPracticeSession);
  $("hero-speak")?.addEventListener("click", (event) => {
    if (event.currentTarget.classList.contains("is-speaking")) {
   stopKannadaSpeech();
   return;
    }
    speakKannada("ನಮಸ್ಕಾರ", "Namaskāra", state.uiStrings, event.currentTarget);
  });
  $("scenario-speak")?.addEventListener("click", (event) => {
    const s = state.scenarios[state.currentScenarioIndex];
    if (s) {
      speakKannada(s.question, "Scenario dialogue", state.uiStrings, event.currentTarget);
    }
  });

  // Practice Quiz controls
  $("next-question")?.addEventListener("click", handleNextQuestion);

  // AI Chat controls
  $("ai-chat-send")?.addEventListener("click", sendAIChatMessage);
  $("ai-chat-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendAIChatMessage();
    }
  });

  // Language setting change inside Account dashboard
  $("account-language")?.addEventListener("change", async (event) => {
    await changeLanguage(event.target.value);
    try {
      const response = await api.updateLanguage(event.target.value);
      state.user = response.user || state.user;
      renderAccount();
    } catch (error) {
      showToast(`Could not save language preference: ${error.message}`, "error");
    }
  });

  // Modal close button
  $("explain-modal-close")?.addEventListener("click", () => {
    $("explain-modal")?.classList.add("hidden");
  });
}

function setupAccessHandlers() {
  // 1. Welcome Screen Actions
  $("continue-guest")?.addEventListener("click", async () => {
    try {
      const response = await api.createGuest(state.language);
      state.user = response.user;
      if (!localStorage.getItem(LANGUAGE_KEY)) {
        showAuthScreen("language");
      } else {
        showAppShell("explore");
        await loadApplicationData();
      }
    } catch (error) {
      showToast(`Could not start guest mode: ${error.message}`, "error");
    }
  });

  $("show-sign-in")?.addEventListener("click", () => {
    showAuthScreen("signin");
  });

  $("show-register")?.addEventListener("click", () => {
    showAuthScreen("register");
  });

  // 2. Navigation between Auth Screens
  $("signin-back-btn")?.addEventListener("click", () => {
    if (state.user) {
      showAppShell("account");
    } else {
      showAuthScreen("welcome");
    }
  });

  $("signin-to-register-btn")?.addEventListener("click", () => {
    showAuthScreen("register");
  });

  $("register-back-btn")?.addEventListener("click", () => {
    if (state.user) {
      showAppShell("account");
    } else {
      showAuthScreen("welcome");
    }
  });

  $("register-to-signin-btn")?.addEventListener("click", () => {
    showAuthScreen("signin");
  });

  // 3. Guest Upgrade Actions (from Account screen)
  $("account-upgrade-btn")?.addEventListener("click", () => {
    showAuthScreen("register");
  });

  $("account-signin-merge-btn")?.addEventListener("click", () => {
    showAuthScreen("signin");
  });

  // 4. Topbar Profile Button
  $("topbar-account-btn")?.addEventListener("click", () => {
    setView("account");
  });

  // 5. Sign-in Form Submission
  $("sign-in-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = $("sign-in-error");
    if (error) error.textContent = "";
    const email = $("sign-in-email")?.value.trim();
    const password = $("sign-in-password")?.value;
    if (!email || !password) {
      if (error) error.textContent = "Email and password are required";
      return;
    }
    try {
      const response = await api.login(email, password);
      state.user = response.user;
      state.language = response.user.preferred_language || getPreferredLanguage();
      localStorage.setItem(LANGUAGE_KEY, state.language);
      showAppShell("explore");
      showToast(`Welcome back, ${state.user.name}!`, "success");
      await loadApplicationData();
    } catch (err) {
      if (error) error.textContent = err.message || "Email or password is incorrect";
    }
  });

  // 6. Registration Form Submission
  $("register-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = $("register-error");
    if (error) error.textContent = "";
    const name = $("register-name")?.value.trim();
    const email = $("register-email")?.value.trim();
    const password = $("register-password")?.value;
    const language = $("register-language")?.value || state.language || getPreferredLanguage();
    if (!name || !email || !password) {
      if (error) error.textContent = "All fields are required";
      return;
    }
    if (password.length < 8) {
      if (error) error.textContent = "Password must be at least 8 characters";
      return;
    }
    try {
      const response = await api.registerAccount(name, email, password, language);
      state.user = response.user;
      state.language = response.user.preferred_language || language;
      localStorage.setItem(LANGUAGE_KEY, state.language);
      showAppShell("explore");
      showToast(`Account created! Welcome, ${state.user.name}!`, "success");
      await loadApplicationData();
    } catch (err) {
      if (error) error.textContent = err.message || "Failed to create account";
    }
  });

  // 7. Working Sign Out (Requirements 2 & 3: calls logout endpoint, clears frontend state, returns to welcome without reload)
  $("account-sign-out")?.addEventListener("click", async () => {
    try {
      await api.logout();
    } catch (err) {
      console.warn("Logout request error:", err.message);
    }
    state.user = null;
    state.savedPhrases = [];
    state.revisionPhrases = [];
    state.progress = {
      answered: 0,
      correct: 0,
      accuracy: 0,
      best_score: 0,
      saved_count: 0,
      revision_count: 0
    };
    state.aiHistory = [];
    state.phrases = [];
    state.currentScenarioIndex = 0;
    state.scenarioAnswered = false;
    state.scenarioSessionCorrect = 0;
    stopKannadaSpeech();

    if ($("sign-in-password")) $("sign-in-password").value = "";
    if ($("sign-in-error")) $("sign-in-error").textContent = "";
    if ($("register-password")) $("register-password").value = "";
    if ($("register-error")) $("register-error").textContent = "";

    if ($("saved-count")) $("saved-count").textContent = "0";
    if ($("revision-count")) $("revision-count").textContent = "0";

    showAuthScreen("welcome");
    showToast("Signed out successfully", "info");
  });
}

// Start application when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}
