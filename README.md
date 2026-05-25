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
make dev

# Website (port 3000, any static server)
cd website && python -m http.server 3000
```

For local cross-origin development, set `ALLOWED_ORIGINS=http://localhost:3000`
in `chatbot/.env`, and `window.CHATBOT_API = "http://localhost:8000/api/v1/chat"`
in your HTML before the widget script loads.

### Option 2 — everything behind nginx via Docker

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
