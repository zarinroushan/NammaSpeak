/**
 * NammaSpeak UI Utilities, Localization DOM Updater, and Component Renderers
 */

import { api } from "./api.js";

export function escapeHTML(str) {
  if (str === null || str === undefined) return "";
  return String(str).replace(/[&<>"']/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[c]));
}

let toastTimer = null;
export function showToast(message, type = "info") {
  let toast = document.getElementById("toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    document.body.appendChild(toast);
  }

  toast.textContent = message;
  toast.className = `toast show ${type}`;

  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.classList.remove("show");
  }, 2800);
}

/**
 * Safe DOM Localization Updater
 * Updates elements matching data-i18n attributes using safe DOM property assignment.
 * Never destroys existing event listeners or overwrites script tags.
 */
export function applyI18nToDOM(strings) {
  if (!strings || typeof strings !== "object") return;

  // Text content updates
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.dataset.i18n;
    if (key && strings[key] !== undefined) {
      el.textContent = strings[key];
    }
  });

  // Placeholder updates
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    const key = el.dataset.i18nPlaceholder;
    if (key && strings[key] !== undefined) {
      el.placeholder = strings[key];
    }
  });

  // Title attribute updates
  document.querySelectorAll("[data-i18n-title]").forEach(el => {
    const key = el.dataset.i18nTitle;
    if (key && strings[key] !== undefined) {
      el.title = strings[key];
    }
  });

  // ARIA label updates
  document.querySelectorAll("[data-i18n-aria-label]").forEach(el => {
    const key = el.dataset.i18nAriaLabel;
    if (key && strings[key] !== undefined) {
      el.setAttribute("aria-label", strings[key]);
    }
  });
}

/**
 * Pronunciation Service backed by the server-side ElevenLabs integration.
 */
let activeSpeech = null;

function speechText(strings, key, fallback) {
  return (strings && strings[key]) || fallback;
}

function resetSpeechButton(button) {
  if (!button) return;
  button.disabled = false;
  if (button.dataset.speechOriginalText !== undefined) {
    button.textContent = button.dataset.speechOriginalText;
    delete button.dataset.speechOriginalText;
  }
  button.classList.remove("is-speaking");
}

export function stopKannadaSpeech() {
  if (activeSpeech) {
    activeSpeech.cancelled = true;
    activeSpeech.controller?.abort();
    activeSpeech.audio?.pause();
    if (activeSpeech.url) URL.revokeObjectURL(activeSpeech.url);
    resetSpeechButton(activeSpeech.button);
    activeSpeech = null;
  }
}

export async function speakKannada(text, romanFallback = "", strings = {}, button = null, playbackRate = 1) {
  stopKannadaSpeech();
  if (button) {
    button.disabled = true;
    button.dataset.speechOriginalText = button.textContent;
    button.textContent = speechText(strings, "speech_loading", "Loading audio…");
    button.classList.add("is-speaking");
  }

  const current = { button, controller: new AbortController(), cancelled: false, audio: null, url: null };
  activeSpeech = current;
  try {
    const blob = await api.getKannadaSpeech(text, current.controller.signal);
    if (current.cancelled) return;
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.playbackRate = playbackRate;
    if ("preservesPitch" in audio) audio.preservesPitch = true;
    if ("mozPreservesPitch" in audio) audio.mozPreservesPitch = true;
    if ("webkitPreservesPitch" in audio) audio.webkitPreservesPitch = true;
    current.url = url;
    current.audio = audio;
    audio.onended = () => {
      URL.revokeObjectURL(url);
      resetSpeechButton(button);
      if (activeSpeech === current) activeSpeech = null;
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      showToast(speechText(strings, "speech_error", "Audio playback is unavailable."));
      resetSpeechButton(button);
      if (activeSpeech === current) activeSpeech = null;
    };
    await audio.play();
    if (button) {
      button.disabled = false;
      button.textContent = speechText(strings, "speech_stop", "■ Stop");
    }
  } catch (error) {
    if (current.cancelled) return;
    const message = speechText(strings, "speech_error", "Audio playback is unavailable.");
    console.warn("ElevenLabs pronunciation request failed:", error?.code || error?.status || "unknown");
    showToast(message);
    resetSpeechButton(button);
    if (activeSpeech === current) activeSpeech = null;
  }
}

export async function copyToClipboard(text, label = "Phrase") {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      showToast(`${label} copied to clipboard! ✓`);
      return true;
    }
    const tempInput = document.createElement("textarea");
    tempInput.value = text;
    document.body.appendChild(tempInput);
    tempInput.select();
    document.execCommand("copy");
    document.body.removeChild(tempInput);
    showToast(`${label} copied to clipboard! ✓`);
    return true;
  } catch (err) {
    console.warn("Clipboard copy failed:", err);
    showToast("Could not copy automatically. Please copy manually.");
    return false;
  }
}

export function createCategoryCardHTML(category, isSelected = false) {
  return `
    <button class="category-card ${isSelected ? "selected" : ""}" 
            data-category="${escapeHTML(category.id)}" 
            style="--cat-bg:${escapeHTML(category.bg || "#f8e7d9")}"
            aria-label="Filter by ${escapeHTML(category.name)}">
      <span class="category-arrow" aria-hidden="true">↗</span>
      <span class="category-emoji">${escapeHTML(category.emoji || "✳")}</span>
      <strong>${escapeHTML(category.name)}</strong>
      <small>${escapeHTML(category.sub || "")}</small>
    </button>
  `;
}

export function createPhraseCardHTML(phrase, isSaved = false, strings = {}) {
  const formalityBadge = phrase.formality ? `<span class="phrase-formality">${escapeHTML(phrase.formality)}</span>` : "";
  const learnContextText = escapeHTML(strings.card_learn_context || "💡 Learn Context");
  const listenText = escapeHTML(strings.card_listen || "▶ Listen");
  const slowListenText = escapeHTML(strings.card_slow_listen || "▶ Slow Listen");
  const copyTitle = escapeHTML(strings.card_copy_title || "Copy Kannada text");
  const saveTitle = escapeHTML(strings.card_save_title || "Save to phrasebook");
  const unsaveTitle = escapeHTML(strings.card_unsave_title || "Remove from phrasebook");

  return `
    <article class="phrase-card" data-phrase-id="${escapeHTML(phrase.id)}">
      <div class="phrase-card-top">
        <span class="phrase-tag">${escapeHTML(phrase.tag || "KANNADA")}</span>
        <div class="phrase-actions">
          <button class="icon-button copy-button" data-copy="${escapeHTML(phrase.kn)}" title="${copyTitle}" aria-label="${copyTitle}">
            📋
          </button>
          <button class="icon-button ${isSaved ? "saved" : ""}" data-save="${escapeHTML(phrase.id)}" title="${isSaved ? unsaveTitle : saveTitle}" aria-label="${isSaved ? unsaveTitle : saveTitle}">
            ${isSaved ? "♥" : "♡"}
          </button>
        </div>
      </div>
      <div class="phrase-kannada" lang="kn">${escapeHTML(phrase.kn)}</div>
      <div class="phrase-roman">${escapeHTML(phrase.roman)}</div>
      <div class="phrase-meaning">${escapeHTML(phrase.meaning)}</div>
      <div class="phrase-context">${escapeHTML(phrase.context)}</div>
      ${formalityBadge}
      <div class="phrase-card-bottom">
        <button class="explain-button" data-explain="${escapeHTML(phrase.id)}" title="${learnContextText}">
          ${learnContextText}
        </button>
        <button class="listen-button" data-speak="${escapeHTML(phrase.id)}" aria-label="${listenText} ${escapeHTML(phrase.roman)}">
          ${listenText}
        </button>
        <button class="listen-button slow-listen-button" data-speak="${escapeHTML(phrase.id)}" data-slow-speak="true" aria-label="${slowListenText} ${escapeHTML(phrase.roman)}">
          ${slowListenText}
        </button>
      </div>
    </article>
  `;
}
