# Oswald — Portfolio Monorepo

Two services in one repo, behind a single nginx reverse proxy:

- **`website/`** — static portfolio site (HTML/CSS/JS, Bootstrap, optional PHP contact form)
- **`chatbot/`** — FastAPI + LangChain + Chroma agentic RAG assistant

Plus deployment glue in **`infra/`**.

---

## Architecture

```
                          ┌──────────────────────┐
                  ┌──────►│        nginx         │◄──────┐
                  │       └──────────────────────┘       │
            /     │                                      │   /api/*
                  ▼                                      ▼
        ┌──────────────────┐                  ┌──────────────────┐
        │  Static website  │                  │   FastAPI app    │
        │  (HTML/CSS/JS)   │                  │  + LangChain     │
        │  + chatbot-widget│ ─── fetch /api/ ►│  + Chroma index  │
        └──────────────────┘                  └──────────────────┘
```

Everything is same-origin in production → **no CORS configuration needed**.

---

## Layout

```
oswald/
├── website/                        Your static portfolio site
│   ├── static/
│   │   ├── css/
│   │   ├── img/
│   │   └── js/
│   │       └── chatbot-widget.js   Chatbot integration (vanilla JS)
│   ├── partials/
│   │   └── chatbot.html            HTML snippet — include once per page
│   ├── index.html, blog.html, ...  (your existing pages)
│   ├── index.php, process_form.php (your existing PHP)
│   └── README.md
│
├── chatbot/                        FastAPI agentic RAG service
│   ├── app/{main,config,schemas,api/,agents/,rag/}.py
│   ├── scripts/ingest.py
│   ├── data/{projects/, chroma/}
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   └── README.md
│
├── infra/                          Deployment
│   ├── nginx/default.conf
│   └── docker-compose.yml
│
├── Makefile                        Convenience commands
├── README.md                       This file
└── .gitignore
```

---

## Audit: fixes applied & open items

### Fixed

| # | Issue | File | What changed |
|---|-------|------|--------------|
| 1 | **Chatbot widget never loaded** — `<?php include 'partials/chatbot.html'; ?>` is silently ignored by browsers on a `.html` file | `website/index.html` | Inlined the chatbot HTML directly before `</body>` |
| 2 | **Chatbot script used an absolute path** — `/static/js/chatbot-widget.js` breaks when not served from the domain root | `website/index.html` | Changed to the relative path `static/js/chatbot-widget.js`, consistent with every other `<script>` tag on the page |
| 3 | **Skill bar values didn't match labels** — Machine Learning bar had `aria-valuenow="90"` while the label read `80%`; MLOps bar had `aria-valuenow="80"` while the label read `85%` | `website/index.html` | Corrected both `aria-valuenow` attributes to match their visible labels (`80` and `85` respectively) |

---

### Needs attention

| # | Issue | File | Recommended fix |
|---|-------|------|-----------------|
| 1 | **No chatbot backend** — `chatbot-widget.js` POSTs to `/api/v1/chat` which doesn't exist on a purely static host. Every message returns an error. | `website/static/js/chatbot-widget.js` | Deploy the `chatbot/` FastAPI service (see _Local development_ below) and set `window.CHATBOT_API = "https://your-api-url"` in your HTML before the widget script loads |
| 2 | **Contact form requires PHP** — `mail_send.js` POSTs to `process_form.php`, which needs a PHP runtime. This fails silently on static hosts (GitHub Pages, Netlify, etc.) | `website/static/js/mail_send.js`, `website/process_form.php` | Either add a `php-fpm` container (see _Notes on PHP_ below) or migrate to `POST /api/v1/contact` on the FastAPI service |
| 3 | **Social links are placeholders** — Twitter, Facebook, Pinterest, and Instagram icons all link to `#` | `website/index.html` (~line 142–147) | Replace `href="#"` with your real profile URLs, or remove the icons you don't use |
| 4 | **LinkedIn points to the generic homepage** — link goes to `https://www.linkedin.com/` instead of your profile | `website/index.html` (~line 144) | Update to your personal LinkedIn URL (e.g. `https://www.linkedin.com/in/your-handle`) |
| 5 | **Blog source label mismatch** — one article shows "MEDIUM WEBSITE" in the meta line but the link goes to OpenAI's site | `website/index.html` (~line 634) | Change the meta label to "OpenAI" (or update the link if the article was from Medium) |

---

## Adding the chatbot to your site

In every page that should show the widget, just before `</body>`:

```html
<?php include 'partials/chatbot.html'; ?>
<script src="/static/js/chatbot-widget.js" defer></script>
```

For pure HTML pages (no PHP), inline the contents of `partials/chatbot.html`
directly, or use a build step / nginx SSI to do the include.

That's it. The widget is a floating button bottom-right; it opens a chat panel
that posts to `/api/v1/chat` (same origin via nginx).

---

## Local development

### Option 1 — run pieces separately

```bash
# Chatbot (port 8000)
cp chatbot/.env.example chatbot/.env   # set OPENAI_API_KEY
make ingest-website U="https://your-portfolio.com"
make ingest-projects
# Run the API without reload for Windows stability
cd chatbot && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Website (port 3000, any static server)
cd ../website && python -m http.server 3000
```

For local cross-origin development, set `ALLOWED_ORIGINS=http://localhost:3000`
in `chatbot/.env`, and `window.CHATBOT_API = "http://localhost:8000/api/v1/chat"`
in your HTML before the widget script loads.

> Tip: On Windows, use the stable `--host 0.0.0.0 --port 8000` command instead of `--reload` if the server is restarting unexpectedly.

### Option 2 — everything behind nginx via Docker

```bash
make up
# → http://localhost:8080      static site
# → http://localhost:8080/api  chatbot API
```

---

## CI/CD and deployment

This repository now includes:
- `CI_CD_PLAN.md` — recommended CI/CD strategy and local runtime guidance
- `.github/workflows/ci-cd.yml` — GitHub Actions workflow for validation, build, and deploy
- `requirements-dev.txt` — development dependencies for CI and testing

Use the workflow as the starting point for automated validation and production deployment.

---

## Notes on PHP (`process_form.php`)

```bash
make up
# → http://localhost:8080      static site
# → http://localhost:8080/api  chatbot API
```

---

## Notes on PHP (`process_form.php`)

Your contact form currently runs on PHP. Two paths forward:

1. **Keep it.** Add a `php-fpm` service to `infra/docker-compose.yml` and
   uncomment the PHP block in `infra/nginx/default.conf`. Two runtimes,
   slightly more surface area, zero migration effort.
2. **Migrate to FastAPI** *(recommended)*. Add `POST /api/v1/contact` to the
   chatbot service — same email-sending logic, one runtime, easier to monitor,
   easier to test. The HTML form's `action` attribute changes from
   `process_form.php` to `/api/v1/contact`.

The `.vs/` directory and `.sublime-workspace` files are editor-local and are
already in `.gitignore`.

---

## Where to extend

See `chatbot/README.md` for chatbot-side extensions: streaming responses,
structured source citations, hybrid retrieval (BM25 + dense), LangSmith
tracing, rate limiting.
