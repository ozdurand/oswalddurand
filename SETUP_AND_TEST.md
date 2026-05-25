# Portfolio Chatbot — Setup & Test Guide

## Overview

This monorepo contains a static portfolio website and a FastAPI agentic RAG chatbot backend. This guide walks through setting up, populating the knowledge base, running, and testing the full stack locally.

---

## Prerequisites

- Python (Anaconda3 recommended — installed at `C:\Users\<you>\anaconda3\python.exe`)
- An OpenAI API key (used for GPT-4o-mini + text-embedding-3-small)

---

## Step 1 — Create the `.env` file

Copy the example and fill in your key:

```
chatbot/.env
```

```
OPENAI_API_KEY=sk-<your-key-here>
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
CHROMA_PERSIST_DIR=./data/chroma
WEBSITE_COLLECTION=website_content
PROJECTS_COLLECTION=projects
RETRIEVAL_K=4
ALLOWED_ORIGINS=http://localhost:8001,http://localhost:8000
```

---

## Step 2 — Install Python dependencies

```bash
cd chatbot
pip install -r requirements.txt
```

Key packages: `fastapi`, `uvicorn`, `langchain`, `langchain-openai`, `chromadb`, `beautifulsoup4`, `httpx`.

---

## Step 3 — Create project markdown files

Add `.md` files to `chatbot/data/projects/` using the schema in `_template.md`. Each file becomes a searchable knowledge source for the `search_projects` RAG tool.

**Required sections per file:**

```markdown
# Project Name
> One-sentence positioning.

## Overview
## Why
## What
## How — Architecture
## How — Tech Stack
## Journey: POC
## Journey: MVP
## Journey: Production
## Key Decisions & Tradeoffs
## Outcomes
```

**Example files created:**
- `chatbot/data/projects/citibank_mlops_platform.md`
- `chatbot/data/projects/home_depot_semantic_search.md`
- `chatbot/data/projects/jnj_multi_agent_biomedical_platform.md`

---

## Step 4 — Ingest project documents into Chroma

```bash
cd chatbot
python -m scripts.ingest projects
```

Expected output:
```
[projects] citibank_mlops_platform -> N header-sections
[projects] home_depot_semantic_search -> N header-sections
[projects] jnj_multi_agent_biomedical_platform -> N header-sections
[ingest] indexed N project chunks
```

The vector store is saved to `chatbot/data/chroma/`.

---

## Step 5 — Serve the website locally and ingest it

Open a terminal and start a simple HTTP server for the static website:

```bash
# Terminal 1
python -m http.server 8001 --directory website
```

Then ingest the website pages so the `search_about_me` tool has content:

```bash
# Terminal 2
cd chatbot
python -m scripts.ingest website http://localhost:8001/ http://localhost:8001/blog.html http://localhost:8001/single-blog.html
```

Expected output:
```
[scrape] http://localhost:8001/ -> 4918 chars
[scrape] http://localhost:8001/blog.html -> 645 chars
[scrape] http://localhost:8001/single-blog.html -> 1729 chars
[ingest] indexed 12 website chunks from 3 URL(s)
```

---

## Step 6 — Fix: Update `orchestrator.py` for LangChain 1.x

> **Why this was needed:** LangChain 1.3.1 removed `AgentExecutor` and `create_tool_calling_agent`. The new API uses `create_agent` which returns a `CompiledStateGraph`.

**`chatbot/app/agents/orchestrator.py`** — change the imports and `build_agent()`:

```python
# OLD (LangChain 0.x)
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# NEW (LangChain 1.x)
from langchain.agents import create_agent
```

```python
# OLD
def build_agent() -> AgentExecutor:
    ...
    prompt = ChatPromptTemplate.from_messages([...])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, ...)

# NEW
def build_agent():
    ...
    return create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)
```

**`chatbot/app/api/routes.py`** — change the invocation to use the message-based interface:

```python
# OLD
result = await agent.ainvoke({
    "input": request.message,
    "chat_history": to_lc_messages(request.history),
})
answer = result["output"]
tool_calls = [action.tool for action, _ in result.get("intermediate_steps", [])]

# NEW
from langchain_core.messages import HumanMessage

messages = to_lc_messages(request.history) + [HumanMessage(content=request.message)]
result = await agent.ainvoke({"messages": messages})
final_messages = result.get("messages", [])
answer = final_messages[-1].content if final_messages else ""
tool_calls = []
for msg in final_messages:
    for tc in getattr(msg, "tool_calls", []):
        name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
        if name:
            tool_calls.append(name)
```

---

## Step 7 — Start the FastAPI server

```bash
cd chatbot
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Expected startup output:
```
INFO: Started server process [...]
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8000
```

---

## Step 8 — Test the health endpoint

```bash
curl http://localhost:8000/api/v1/health
# Expected: {"status":"ok"}
```

---

## Step 9 — Test the chat API

**About-me query** (triggers `search_about_me` tool):

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Who is Oswald and what is his background?\",\"history\":[]}"
```

**Project query** (triggers `search_projects` tool):

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Tell me about the JNJ multi-agent biomedical platform\",\"history\":[]}"
```

**Multi-turn conversation** (pass history array):

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"What was the POC phase like?\",\"history\":[{\"role\":\"user\",\"content\":\"What projects has Oswald worked on?\"},{\"role\":\"assistant\",\"content\":\"Oswald has worked on the JNJ platform, Citibank MLOps, and Home Depot Semantic Search.\"}]}"
```

---

## Step 10 — Fix: Add API override for the browser widget

> **Why this was needed:** The widget's `window.CHATBOT_API` must be the **full URL** including the path. Setting it to just the base URL (`http://localhost:8000`) caused the widget to POST to the root `/` endpoint, which is GET-only → 405 error → "Sorry, something went wrong."

Add the following to `website/index.html` before `</body>`:

```html
<!-- LOCAL DEV ONLY: remove before deploying -->
<script>window.CHATBOT_API = "http://localhost:8000/api/v1/chat";</script>
<script src="static/js/chatbot-widget.js" defer></script>
```

---

## Step 11 — Test the widget in the browser

1. Open `http://localhost:8001` in your browser
2. Click the **dark floating button in the bottom-right corner**
3. Type a question and press Send

**Suggested test questions:**
| Question | Tool triggered |
|----------|---------------|
| "What is Oswald's background and skills?" | `search_about_me` |
| "Tell me about the Home Depot semantic search project" | `search_projects` |
| "What tech stack was used at Citibank?" | `search_projects` |
| "How do I contact Oswald?" | `search_about_me` |

---

## Running Services Summary

| Service | Command | URL |
|---------|---------|-----|
| Portfolio website | `python -m http.server 8001 --directory website` | http://localhost:8001 |
| Chatbot API | `cd chatbot && python -m uvicorn app.main:app --port 8000` | http://localhost:8000 |
| Swagger/OpenAPI docs | *(API must be running)* | http://localhost:8000/docs |

---

## Before Deploying

- [ ] Replace placeholder project `.md` files in `chatbot/data/projects/` with real content, then re-run `python -m scripts.ingest projects`
- [ ] Remove the `window.CHATBOT_API` override from `website/index.html`
- [ ] Set `ALLOWED_ORIGINS` in `.env` to your deployed domain (e.g., `https://your-portfolio.com`)
- [ ] Run `make ingest-website U=https://your-portfolio.com` to index the live site
- [ ] Use `make up` (Docker Compose) to run the full Nginx + chatbot stack on port 8080
