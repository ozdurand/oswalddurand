/**
 * Portfolio chatbot widget — vanilla JS, zero dependencies.
 *
 * Usage:
 *   1. Include partials/chatbot.html once near </body> of every page
 *   2. <script src="/static/js/chatbot-widget.js" defer></script>
 *
 * Optional config (set before this script loads):
 *   window.CHATBOT_API = "https://your-api.com/api/v1/chat"
 *   (defaults to "/api/v1/chat" — same origin via nginx)
 */
(function () {
  "use strict";

  const API_URL = window.CHATBOT_API || (() => {
    const localHost = /^(localhost|127\.0\.0\.1)$/i.test(window.location.hostname);
    if (localHost && window.location.port && window.location.port !== "8000") {
      return `http://${window.location.hostname}:8000/api/v1/chat`;
    }
    return "/api/v1/chat";
  })();
  const STORAGE_KEY = "portfolio_chat_history";
  const MAX_HISTORY = 20;

  const $ = (sel, root = document) => root.querySelector(sel);

  const root = $("#chatbot-root");
  if (!root) return; // partial not on this page

  const launcher = $("#chatbot-launcher", root);
  const panel = $("#chatbot-panel", root);
  const closeBtn = $("#chatbot-close", root);
  const messagesEl = $("#chatbot-messages", root);
  const form = $("#chatbot-form", root);
  const input = $("#chatbot-input", root);

  // --------------------------- state ---------------------------
  let history = loadHistory();

  function loadHistory() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch { return []; }
  }
  function saveHistory() {
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(history.slice(-MAX_HISTORY))
      );
    } catch { /* quota or disabled */ }
  }

  // --------------------------- render --------------------------
  function renderMessage(role, content) {
    const div = document.createElement("div");
    div.className = `cb-msg cb-${role}`;
    div.textContent = content;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function renderTyping() {
    const div = document.createElement("div");
    div.className = "cb-msg cb-assistant";
    div.innerHTML =
      '<span class="cb-typing"><span></span><span></span><span></span></span>';
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  // Replay prior session messages
  history.forEach((m) => renderMessage(m.role, m.content));
  if (history.length === 0) {
    renderMessage(
      "assistant",
      "Hi — I'm Oswald's assistant. Ask me about his background or any of his projects."
    );
  }

  // --------------------------- behavior ------------------------
  function togglePanel(open) {
    panel.classList.toggle("cb-open", open);
    if (open) setTimeout(() => input.focus(), 50);
  }

  launcher.addEventListener("click", () =>
    togglePanel(!panel.classList.contains("cb-open"))
  );
  closeBtn.addEventListener("click", () => togglePanel(false));

  // Esc closes the panel
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && panel.classList.contains("cb-open")) {
      togglePanel(false);
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    input.value = "";

    history.push({ role: "user", content: message });
    saveHistory();
    renderMessage("user", message);

    const pending = renderTyping();
    try {
      const resp = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          history: history.slice(0, -1), // exclude the just-pushed user msg
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      pending.textContent = data.answer;
      history.push({ role: "assistant", content: data.answer });
      saveHistory();
    } catch (err) {
      pending.textContent =
        "Sorry — something went wrong. Please try again in a moment.";
      console.error("[chatbot]", err);
    }
  });
})();