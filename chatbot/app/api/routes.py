
"""HTTP routes for the chatbot."""
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

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
        messages = to_lc_messages(request.history) + [
            HumanMessage(content=request.message)
        ]
        result = await agent.ainvoke({"messages": messages})
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {e!s}",
        )

    final_messages = result.get("messages", [])
    answer = final_messages[-1].content if final_messages else ""

    tool_calls = []
    for msg in final_messages:
        for tc in getattr(msg, "tool_calls", []):
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            if name:
                tool_calls.append(name)

    return ChatResponse(
        answer=answer,
        sources=[],  # see README for how to wire structured sources
        tool_calls=tool_calls,
        session_id=request.session_id,
    )
