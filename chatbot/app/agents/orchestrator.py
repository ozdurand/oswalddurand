"""Tool-calling agent that routes between website and project retrievers.

This is "agentic RAG": the LLM decides which tool(s) to call, can call the same
tool multiple times with refined queries, and assembles the final answer.
"""

import re
from functools import lru_cache
from typing import Any, Optional, Tuple

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.prompts import build_system_prompt
from app.rag.vectorstore import get_vectorstore
from app.schemas import ChatMessage
from app.utils.sanitizer import detect_prompt_injection


def _record_sources(
    docs: list[Any], query: str, tool_name: str, stored: list[dict[str, Any]]
) -> None:
    seen = {
        (
            item["metadata"].get("source"),
            item["metadata"].get("section"),
            item["metadata"].get("subsection"),
            item["metadata"].get("tool"),
        )
        for item in stored
    }
    for doc in docs:
        key = (
            doc.metadata.get("source"),
            doc.metadata.get("section"),
            doc.metadata.get("subsection"),
            tool_name,
        )
        if key in seen:
            continue
        seen.add(key)
        stored.append(
            {
                "content": doc.page_content,
                "metadata": {
                    **doc.metadata,
                    "retrieval_query": query,
                    "tool": tool_name,
                },
                "score": _lexical_score(doc, query),
            }
        )


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def _lexical_score(doc, query: str) -> float:
    tokens = _token_set(query)
    if not tokens:
        return 0.0
    content = " ".join(
        [
            doc.page_content,
            doc.metadata.get("title", ""),
            doc.metadata.get("project", ""),
            doc.metadata.get("section", ""),
            doc.metadata.get("subsection", ""),
        ]
    )
    return len(tokens & _token_set(content)) / len(tokens)


def _format_source_line(doc) -> str:
    flags = []
    if doc.metadata.get("has_table"):
        flags.append("table")
    if doc.metadata.get("has_formula"):
        flags.append("formula")
    if doc.metadata.get("has_image"):
        flags.append("image")
    extra = f" | {', '.join(flags)}" if flags else ""
    title = doc.metadata.get("title") or doc.metadata.get(
        "source", doc.metadata.get("project", "website")
    )
    return f"[Source: {title} | {doc.metadata.get('domain', doc.metadata.get('project', 'unknown'))}{extra}]"


def _retrieve(vs, query: str, k: int = 4, filter_: Optional[dict] = None):
    raw = vs.similarity_search_with_score(query, k=min(20, k * 4), filter=filter_)
    scored = []
    for rank, (doc, score) in enumerate(raw, start=1):
        dense_score = 1.0 / rank
        lexical_score = _lexical_score(doc, query)
        combined = dense_score + 0.4 * lexical_score
        scored.append((combined, rank, doc))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [doc for _, _, doc in scored[:k]]


def _build_tools():
    """Tools are built inside a factory so they close over fresh settings."""
    s = get_settings()
    sources: list[dict[str, Any]] = []

    def _record_sources_local(docs: list[Any], query: str, tool_name: str) -> None:
        _record_sources(docs, query, tool_name, sources)

    @tool
    async def search_about_me(query: str) -> str:
        """Search Oswald's portfolio website for general information about him — \
bio, work history, skills, contact info, education, anything covered by the site itself. \
Use for questions like "who are you", "what's your background", "how do I reach you"."""
        vs = get_vectorstore(s.website_collection)
        results = _retrieve(vs, query, k=s.retrieval_k)
        if not results:
            return "No relevant information found on the website for this query."
        _record_sources_local(results, query, "search_about_me")
        return "\n\n---\n\n".join(
            f"{_format_source_line(d)}\n{d.page_content}" for d in results
        )

    @tool
    async def search_projects(query: str, project_name: Optional[str] = None) -> str:
        """Search deep project documentation including architecture, design decisions \
(the How / Why / What), strategies, and the journey from POC to MVP to Production. \
Use for technical questions about specific projects or design rationale. \
Pass `project_name` (the filename stem, e.g. "multi_agent_rag") to filter to a \
single project."""
        vs = get_vectorstore(s.projects_collection)
        filter_ = {"project": project_name} if project_name else None
        results = _retrieve(vs, query, k=s.retrieval_k, filter_=filter_)
        if not results:
            suffix = f" for project '{project_name}'" if project_name else ""
            return f"No project information found{suffix}."

        def _format_project_header(doc):
            flags = []
            if doc.metadata.get("has_table"):
                flags.append("has_table")
            if doc.metadata.get("has_formula"):
                flags.append("has_formula")
            if doc.metadata.get("has_image"):
                flags.append("has_image")
            flag_str = f" | {', '.join(flags)}" if flags else ""
            return (
                f"[Project: {doc.metadata.get('project', 'unknown')} | "
                f"Section: {doc.metadata.get('section', '-')} / "
                f"{doc.metadata.get('subsection', '-')}{flag_str}]"
            )

        _record_sources_local(results, query, "search_projects")
        return "\n\n---\n\n".join(
            f"{_format_project_header(d)}\n{d.page_content}" for d in results
        )

    tools = [search_about_me, search_projects]
    return tools, sources


@lru_cache
def _get_llm():
    s = get_settings()
    return ChatOpenAI(
        model=s.openai_model,
        temperature=0.2,
        api_key=s.openai_api_key,
    )


def build_agent():
    tools, sources = _build_tools()
    agent = create_agent(
        model=_get_llm(), tools=tools, system_prompt=build_system_prompt()
    )
    setattr(agent, "_sources", sources)
    setattr(agent, "clear_sources", sources.clear)
    setattr(agent, "get_sources", lambda: list(sources))
    return agent


def to_lc_messages(history: list[ChatMessage]):
    """Convert API ChatMessage history -> LangChain message objects."""
    out = []
    for m in history:
        if m.role == "user":
            out.append(HumanMessage(content=m.content))
        else:
            out.append(AIMessage(content=m.content))
    return out


REFUSAL_TEMPLATE = (
    "I can't answer that confidently based on the portfolio documentation. "
    "Please rephrase or provide more context, or check the source documentation."
)


def _contains_factual_claims(text: str) -> bool:
    """Heuristic: detect likely factual claims (numbers, years, emails, urls)."""
    if not text:
        return False
    # emails
    if re.search(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b", text):
        return True
    # years like 1990-2099
    if re.search(r"\b(19|20)\d{2}\b", text):
        return True
    # numbers with units or digits
    if re.search(r"\b\d{2,}(?:\s?(ms|s|min|h|hrs|%|p95|p99))?\b", text):
        return True
    # urls
    if re.search(r"https?://", text):
        return True
    return False


def verify_answer(answer: str, sources: list[dict]) -> Tuple[str, bool]:
    """Return (possibly_replaced_answer, was_refused).

    - If the answer looks like it makes factual claims but there are no sources,
      return a safe refusal message.
    - If the answer itself contains prompt-injection style instructions, refuse.
    - Otherwise return the original answer.
    """
    if not answer:
        return answer, False

    # If the model output includes prompt-injection attempts, refuse.
    if detect_prompt_injection(answer):
        return REFUSAL_TEMPLATE, True

    # If there are no sources and the answer appears factual, refuse to avoid hallucination.
    if not sources and _contains_factual_claims(answer):
        return REFUSAL_TEMPLATE, True

    # Otherwise pass through
    return answer, False
