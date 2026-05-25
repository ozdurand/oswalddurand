"""HTTP routes for the chatbot."""
from functools import lru_cache

from fastapi import APIRouter, HTTPException

from app.agents.orchestrator import build_agent, to_lc_messages
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/v1", tags=["chat"])


@lru_cache
def _agent():
    """Single shared AgentExecutor — built once, reused across requests."""
    return build_agent()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    agent = _agent()
    try:
        result = await agent.ainvoke({
            "input": request.message,
            "chat_history": to_lc_messages(request.history),
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e!s}")

    # Surface which tools the agent invoked — useful for debugging / UI hints.
    tool_calls = [
        action.tool for action, _ in result.get("intermediate_steps", [])
    ]

    return ChatResponse(
        answer=result["output"],
        sources=[],   # see README for how to wire structured sources
        tool_calls=tool_calls,
        session_id=request.session_id,
    )
