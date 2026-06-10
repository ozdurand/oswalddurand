"""HTTP routes for the chatbot."""

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import HumanMessage

from app.agents.orchestrator import build_agent, to_lc_messages, verify_answer
from app.prompts.renderer import render_user_message_for_model
from app.schemas import ChatMessage, ChatRequest, ChatResponse
from app.utils.sanitizer import safe_truncate, sanitize_user_message

router = APIRouter(prefix="/api/v1", tags=["chat"])

# Simple in-memory rate limiting: {ip: (window_start_ts, count)}
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_COUNT = 60  # requests per window
_rate_store: dict[str, tuple[float, int]] = {}


def _rate_limited(ip: str) -> bool:
    import time

    now = time.time()
    window_start, count = _rate_store.get(ip, (0.0, 0))
    if now - window_start > _RATE_LIMIT_WINDOW:
        _rate_store[ip] = (now, 1)
        return False
    if count >= _RATE_LIMIT_COUNT:
        return True
    _rate_store[ip] = (window_start, count + 1)
    return False


def _agent():
    """Build a fresh AgentExecutor per request.

    This prevents LangChain internal agent state from leaking across
    independent chat requests and keeps retrieval behavior consistent.
    """
    return build_agent()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    agent = _agent()
    agent.clear_sources()
    try:
        # Rate limit by client IP
        client_ip = http_request.client.host if http_request.client else "unknown"
        if _rate_limited(client_ip):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        # Sanitize history and the incoming user message to reduce prompt-injection risk.
        sanitized_history: list[ChatMessage] = []
        for m in request.history:
            content = safe_truncate(sanitize_user_message(m.content))
            sanitized_history.append(ChatMessage(role=m.role, content=content))

        sanitized_message = safe_truncate(sanitize_user_message(request.message))
        rendered = render_user_message_for_model(sanitized_message)

        messages = to_lc_messages(sanitized_history) + [HumanMessage(content=rendered)]
        result = await agent.ainvoke({"messages": messages})
    except HTTPException:
        raise
    except Exception as e:
        # Avoid leaking internal details to clients; log server-side and return a generic error
        print(f"[chat] internal error: {e!r}")
        raise HTTPException(status_code=500, detail="Internal server error")

    final_messages = result.get("messages", [])
    answer = final_messages[-1].content if final_messages else ""

    # Verify the model output and replace with a refusal if unverifiable
    try:
        verified, refused = verify_answer(answer, agent.get_sources())
        if refused:
            answer = verified
    except Exception as e:
        print(f"[chat] verifier error: {e!r}")

    tool_calls = []
    for msg in final_messages:
        for tc in getattr(msg, "tool_calls", []):
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            if name:
                tool_calls.append(name)

    return ChatResponse(
        answer=answer,
        sources=agent.get_sources(),
        tool_calls=tool_calls,
        session_id=request.session_id,
    )
