# Portfolio Chatbot

Agentic RAG chatbot for a personal portfolio site. A single tool-calling agent
routes between two retrievers:

- **`search_about_me`** — scraped portfolio website (bio, contact, skills)
- **`search_projects`** — deep project docs (architecture, How / Why / What,
  POC → MVP → Production), optionally filtered by project name

Built on FastAPI + LangChain + Chroma + OpenAI.

---

## Architecture

```
┌───────────┐   POST /api/v1/chat   ┌─────────────────┐
│  Browser  │ ────────────────────▶ │  FastAPI route  │
└───────────┘                       └────────┬────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │  AgentExecutor  │  (LangChain tool-calling)
                                    │   (GPT-4o-mini) │
                                    └────────┬────────┘
                                             │  picks tool(s) + queries
                              ┌──────────────┴──────────────┐
                              ▼                             ▼
                  ┌────────────────────┐         ┌────────────────────┐
                  │ search_about_me    │         │ search_projects    │
                  │ Chroma: website    │         │ Chroma: projects   │
                  └────────────────────┘         └────────────────────┘
```

Two named collections live in the same persistent Chroma directory.

---

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: set OPENAI_API_KEY, ALLOWED_ORIGINS, etc.
```

---

## Add your content

### 1) Write project docs
Drop markdown files into `data/projects/`. Use `_template.md` as the schema — every
project doc should answer **Why / What / How / Journey / Decisions / Outcomes**.
Filename stem becomes the `project` metadata key, e.g. `multi_agent_rag.md`
→ `project="multi_agent_rag"`. The agent can filter to a specific project.

### 2) Index everything

```bash
# Website pages
python -m scripts.ingest website https://your-portfolio.com https://your-portfolio.com/about

# Project docs
python -m scripts.ingest projects
```

Re-run any time you add or update content. Each call appends; if you want a clean
rebuild, delete `data/chroma/` first.

---

## Run

```bash
uvicorn app.main:app --reload
```

- Health:  `GET  /api/v1/health`
- Chat:    `POST /api/v1/chat`
- OpenAPI: `GET  /docs`

### Request

```json
{
  "message": "What were the key architecture decisions on your multi-agent RAG platform?",
  "history": [
    {"role": "user", "content": "Hi, who are you?"},
    {"role": "assistant", "content": "I'm Oswald's portfolio assistant..."}
  ]
}
```

### Response

```json
{
  "answer": "...",
  "tool_calls": ["search_projects"],
  "sources": [],
  "session_id": null,
  "timestamp": "2026-05-22T..."
}
```

---

## Frontend integration

Set `ALLOWED_ORIGINS` in `.env` to your portfolio site's origin(s).

```js
const resp = await fetch("https://your-api/api/v1/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message, history }),
});
const { answer, tool_calls } = await resp.json();
```

---

## Where to extend

- **Structured source citations.** `sources` is wired through the response schema
  but the tools currently return flattened strings (best for LLM consumption). To
  populate it, capture the `Document` objects inside the tool functions via a
  request-scoped context (e.g. `contextvars.ContextVar`) and emit them into the
  route handler.
- **Streaming.** Swap the `ainvoke` call for `astream_events` and wrap the route
  in `StreamingResponse` (SSE) for token-level streaming.
- **Hybrid retrieval.** For the projects collection, layer BM25 over Chroma's
  dense retrieval — project docs are keyword-rich (tech names, vendors) and a
  hybrid ensemble materially improves recall. `langchain.retrievers.EnsembleRetriever`
  + `BM25Retriever` is the standard pattern.
- **Rate limiting + auth.** Add `slowapi` middleware and an API key header before
  exposing publicly.
- **Observability.** LangSmith integration is one env var (`LANGSMITH_TRACING=true`,
  `LANGSMITH_API_KEY=...`) and gives you per-tool-call traces for free.

---

## Notes

- `langchain_community.vectorstores.Chroma` is used to stay within your stated
  dependency set. The current recommended import is `langchain_chroma.Chroma`
  (add `langchain-chroma` to requirements) — behaviour is identical.
- Chroma calls are sync; for very high concurrency wrap them in
  `await asyncio.to_thread(...)` inside the tool functions.
