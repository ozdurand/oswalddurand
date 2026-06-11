# Guardrails Hardening Reminder

This document summarizes the prompt-injection and hallucination hardening work to do later.

## Summary

Add multi-layered guardrails for the chatbot:

- Input sanitization for user messages.
- Prompt rendering with a neutral wrapper.
- Schema-level validation to reject suspicious messages.
- Ingestion URL validation / private IP blocking.
- Document sanitization before adding to vectorstore.
- Provenance enforcement for Chroma documents.
- Output verification and safe refusal for unverifiable factual claims.
- Basic per-IP rate limiting and safe API error handling.

## Files touched

- `chatbot/app/utils/sanitizer.py`
- `chatbot/app/prompts/renderer.py`
- `chatbot/app/api/routes.py`
- `chatbot/app/schemas.py`
- `chatbot/app/agents/orchestrator.py`
- `chatbot/app/rag/ingestion.py`
- `chatbot/app/rag/vectorstore.py`
- `chatbot/tests/test_sanitizer.py`
- `chatbot/tests/test_orchestrator.py`

## Suggested commit history

1. `feat(sanitizer): add input sanitizer (detection, sanitization, truncation)`
2. `feat(prompts): add prompt renderer and integrate in API`
3. `fix(schemas): validate ChatRequest.message for injection patterns` 
4. `feat(rag): add URL safety checks and sanitize docs before indexing`
5. `feat(vectorstore): ensure provenance metadata and safe writer`
6. `feat(agents): add output verification and refusal policy`
7. `feat(api): add per-IP rate limiting and safer error handling`

## Notes

- The current implementation was tested locally and the test suite passed.
- This reminder is for later follow-up; do not proceed with branch creation or PR now.
- Future improvements: Redis-backed rate limiting, richer retrieval-based fact-checking, and Chroma access controls/encryption.
