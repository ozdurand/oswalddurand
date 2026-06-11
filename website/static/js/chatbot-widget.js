/**
 * Portfolio chatbot widget — vanilla JS, zero dependencies.
 *
 * Matches the FLOATING-WIDGET markup (launcher bubble + collapsible panel):
 *   #chatbot-root, #chatbot-launcher, #chatbot-panel, #chatbot-close,
 *   #chatbot-messages, #chatbot-form, #chatbot-input
 *
 * Usage:
 *   1. Include the widget markup once near </body>
 *   2. <script src="static/js/chatbot-widget.js" defer></script>
 *
 * Optional config (set before this script loads):
 *   window.CHATBOT_API = "https://your-api.com/api/v1/chat"
 *   (defaults to "/api/v1/chat" — same origin)
 */
(function () {
  "use strict";

  const API_URL = window.CHATBOT_API || (() => {
    if (window.location.protocol === "file:") {
      return "http://127.0.0.1:8000/api/v1/chat";
    }
    const localHost = /^(localhost|127\.0\.0\.1)$/i.test(window.location.hostname);
    if (localHost && window.location.port && window.location.port !== "8000") {
      return `http://${window.location.hostname}:8000/api/v1/chat`;
    }
    return "/api/v1/chat";
  })();
  const STORAGE_KEY = "portfolio_chat_history";
  const MAX_HISTORY = 20;

  const $ = (sel, root = document) => root.querySelector(sel);

  if (window.marked && typeof window.marked.setOptions === "function") {
    marked.setOptions({
      gfm: true,
      headerIds: false,
      mangle: false,
    });
  }
  if (window.mermaid && typeof window.mermaid.initialize === "function") {
    mermaid.initialize({ startOnLoad: false, theme: "default" });
  }

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
  function renderMessage(role, content, messagesEl, sources = []) {
    const div = document.createElement("div");
    div.className = `cb-msg cb-${role}`;

    if (
      role === "assistant" &&
      window.marked &&
      typeof window.marked.parse === "function"
    ) {
      div.innerHTML = marked.parse(content);
      const mermaidBlocks = div.querySelectorAll("code.language-mermaid");
      mermaidBlocks.forEach((code) => {
        const mermaidDiv = document.createElement("div");
        mermaidDiv.className = "mermaid";
        mermaidDiv.textContent = code.textContent;
        const pre = code.closest("pre");
        if (pre) pre.replaceWith(mermaidDiv);
      });
      if (window.mermaid && typeof window.mermaid.init === "function") {
        window.mermaid.init(undefined, div.querySelectorAll(".mermaid"));
      }
    } else {
      div.textContent = content;
    }

    if (sources.length) {
      renderSources(sources, div);
    }
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function renderSources(sources, messageEl) {
    const wrapper = document.createElement("div");
    wrapper.className = "cb-sources";
    wrapper.innerHTML = `<strong>Sources</strong><ul>${sources
      .map((source) => {
        const meta = source.metadata || {};
        const title = meta.title || meta.source || meta.project || "Unknown source";
        const project = meta.project ? `Project: ${meta.project}` : null;
        const section = meta.section || meta.subsection ? `Section: ${meta.section || "-"}${meta.subsection ? ` / ${meta.subsection}` : ""}` : null;
        const flags = [meta.has_table && "table", meta.has_formula && "formula", meta.has_image && "image"]
          .filter(Boolean)
          .join(", ");
        const tag = flags ? ` (${flags})` : "";
        const label = [title, project, section].filter(Boolean).join(" · ");
        return `<li>${label}${tag}</li>`;
      })
      .join("")}</ul>`;
    messageEl.appendChild(wrapper);
  }

  function renderTyping(messagesEl) {
    const div = document.createElement("div");
    div.className = "cb-msg cb-assistant";
    div.innerHTML =
      '<span class="cb-typing"><span></span><span></span><span></span></span>';
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function wireForm(form, input, messagesEl) {
    history.forEach((m) => renderMessage(m.role, m.content, messagesEl));
    if (history.length === 0) {
      renderMessage(
        "assistant",
        "Hi — I'm Oswald's assistant. Ask me about his background or any of his projects.",
        messagesEl
      );
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const message = input.value.trim();
      if (!message) return;
      input.value = "";

      history.push({ role: "user", content: message });
      saveHistory();
      renderMessage("user", message, messagesEl);

      const pending = renderTyping(messagesEl);
      try {
        const resp = await fetch(API_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            history: history.slice(0, -1),
          }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        const assistantMsg = renderMessage("assistant", data.answer, messagesEl, data.sources);
        pending.replaceWith(assistantMsg);
        history.push({ role: "assistant", content: data.answer });
        saveHistory();
      } catch (err) {
        pending.textContent =
          "Sorry — something went wrong. Please try again in a moment.";
        console.error("[chatbot]", err);
      }
    });
  }

  // --------------------------- layout detection ----------------
  const root = $("#chatbot-root");

  if (root) {
    // Floating widget mode (index.html) — launcher opens chatbot.html as a popup
    const launcher = $("#chatbot-launcher", root);
    if (!launcher) return;

    launcher.addEventListener("click", () => {
      window.open(
        "/partials/chatbot.html",
        "chatbot",
        "width=1000,height=700,resizable=yes,scrollbars=no"
      );
    });
  } else {
    // Full-page mode (chatbot.html)
    const messagesEl = $("#chatbot-messages");
    const form = $("#chatbot-form");
    const input = $("#chatbot-input");

    if (!messagesEl || !form || !input) return;

    wireForm(form, input, messagesEl);
  }
})();