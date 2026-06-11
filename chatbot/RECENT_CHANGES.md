# Recent RAG Improvements and Chat Citation Support

This document summarizes the recent engineering changes made to improve ingestion, chunking, embeddings, retrieval, source metadata, and frontend citation display.

## Summary

The portfolio chatbot now supports:

- richer parsing of structured and semi-structured content in HTML and Markdown
- stronger embeddings via `text-embedding-3-large`
- hybrid dense + lexical retrieval ranking
- chunk metadata for tables, formulas, and images
- request-scoped source capture for citations
- structured `sources` in the chat API response
- frontend display of retrieval citations inside the chat UI

## Files changed

- `chatbot/app/config.py`
- `chatbot/app/rag/ingestion.py`
- `chatbot/app/agents/orchestrator.py`
- `chatbot/app/api/routes.py`
- `website/static/js/chatbot-widget.js`
- `website/partials/chatbot.html`

## Detailed changes

### 1. Embedding model upgrade

- Updated `chatbot/app/config.py`:
  - changed the default embedding model from `text-embedding-3-small` to `text-embedding-3-large`

This improves embedding quality for a mixed corpus containing tables, formulas, and narrative project content.

### 2. Structured document ingestion

- Updated `chatbot/app/rag/ingestion.py` to parse content more intelligently.
- HTML scraping now preserves data from:
  - `<table>` elements, converting them into readable `Table:` text rows
  - `<figure>` captions
  - `<math>` blocks as explicit `Formula:` text
  - `<img>` elements by extracting `alt`, `src`, and `title`
- Markdown ingestion now normalizes:
  - inline math and fenced math blocks into `Formula:` text
  - image references into caption-like text
- Added chunk metadata flags:
  - `has_table`
  - `has_formula`
  - `has_image`

These changes preserve structure during chunking so retrieval can better match queries about tables, formulas, and images.

### 3. Hybrid retrieval flow

- Updated `chatbot/app/agents/orchestrator.py` to combine dense similarity and lexical scoring.
- The retrieval helper now:
  - fetches a broader candidate set from Chroma
  - computes a lightweight lexical overlap score
  - combines dense and lexical scores for ranking

This improves recall for project-focused, keyword-rich queries while still benefiting from semantic matching.

### 4. Request-scoped source capture

- Added citation capture in `chatbot/app/agents/orchestrator.py`:
  - request-scoped `contextvars` store retrieval sources per chat request
  - `search_about_me` and `search_projects` both record the chunks they return
  - duplicate chunks are deduplicated per request
- Captured metadata includes:
  - source path or URL
  - project name
  - section/subsection values
  - table/formula/image flags
  - retrieval query
  - tool name

### 5. API response wiring

- Updated `chatbot/app/api/routes.py` to:
  - clear the citation buffer at the start of each request
  - return `sources` in `ChatResponse`
  - preserve existing tool call tracking

This means the frontend now receives structured provenance alongside the assistant answer.

### 6. Frontend citation display

- Updated `website/static/js/chatbot-widget.js`:
  - added `renderSources()` to render source metadata under assistant responses
  - appends citations to the answer bubble when `data.sources` exist
- Updated `website/partials/chatbot.html`:
  - added styling for citation bubbles (`.cb-sources`)

The chat UI now shows retrieval sources for users, improving transparency and grounding.

## How it works

1. A user submits a query through the chat widget.
2. The backend agent routes the query to `search_about_me` or `search_projects`.
3. Each tool performs hybrid retrieval and returns the top chunks.
4. The agent records those chunks as structured citations.
5. The `/api/v1/chat` endpoint returns `answer` plus `sources`.
6. The frontend displays the assistant answer and the source metadata.

## Testing and validation

- Verified the updated Python modules compile without syntax errors.
- Verified the updated modules import correctly.
- The frontend now renders source metadata when the API returns `data.sources`.

## Next improvements

- Add click-through links for website URLs or project docs in source metadata.
- Store source content snippets or excerpts for richer citation display.
- Add a cross-encoder reranker for more precise project retrieval.
- Add explicit filtering by structured chunk metadata (e.g. search only tables or formulas).
