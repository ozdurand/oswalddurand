"""FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import _agent, router
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the agent + Chroma clients on startup so the first request isn't slow.
    _agent()
    yield


app = FastAPI(
    title="Portfolio Chatbot",
    description="Agentic RAG assistant for Oswald's portfolio site.",
    version="0.1.0",
    lifespan=lifespan,
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {"name": "Portfolio Chatbot API", "docs": "/docs"}
