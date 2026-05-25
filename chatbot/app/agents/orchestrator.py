"""Tool-calling agent that routes between website and project retrievers.

This is "agentic RAG": the LLM decides which tool(s) to call, can call the same
tool multiple times with refined queries, and assembles the final answer.
"""
from typing import Optional

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.rag.vectorstore import get_vectorstore
from app.schemas import ChatMessage


SYSTEM_PROMPT = """You are the assistant on Oswald's portfolio website. \
You help visitors learn about Oswald — his background, experience, and projects.

You have two retrieval tools:
- `search_about_me`     — general info: bio, career, skills, contact, anything on the website
- `search_projects`     — deep technical project documentation: architecture, design \
decisions (the How / Why / What), strategies, and the journey from POC -> MVP -> Production

Routing guidance:
- Bio / contact / skills / career-overview questions  -> `search_about_me`
- Deep technical "how did you build X", "why did you pick Y", "what was the journey" \
questions  -> `search_projects`
- If a specific project is named, pass it as `project_name` to filter
- It's fine to call both tools, or the same tool multiple times with refined queries

Answer guidelines:
- Ground every claim in retrieved content. If nothing relevant is returned, say so \
honestly — do not invent metrics, employers, dates, or technical details.
- For technical questions explain the *why*, not just the *what*. Visitors want to \
understand decisions and tradeoffs.
- Be concise but substantive. Match the visitor's technical vocabulary.
- If a question is ambiguous (e.g. "tell me about your platform") ask which one, or \
pick the most likely match and say so.
"""


def _build_tools():
    """Tools are built inside a factory so they close over fresh settings."""
    s = get_settings()

    @tool
    def search_about_me(query: str) -> str:
        """Search Oswald's portfolio website for general information about him — \
bio, work history, skills, contact info, education, anything covered by the site itself. \
Use for questions like "who are you", "what's your background", "how do I reach you"."""
        vs = get_vectorstore(s.website_collection)
        results = vs.similarity_search(query, k=s.retrieval_k)
        if not results:
            return "No relevant information found on the website for this query."
        return "\n\n---\n\n".join(
            f"[Source: {d.metadata.get('title') or d.metadata.get('source', 'website')}]\n"
            f"{d.page_content}"
            for d in results
        )

    @tool
    def search_projects(query: str, project_name: Optional[str] = None) -> str:
        """Search deep project documentation including architecture, design decisions \
(the How / Why / What), strategies, and the journey from POC to MVP to Production. \
Use for technical questions about specific projects or design rationale. \
Pass `project_name` (the filename stem, e.g. "multi_agent_rag") to filter to a \
single project."""
        vs = get_vectorstore(s.projects_collection)
        filter_ = {"project": project_name} if project_name else None
        results = vs.similarity_search(query, k=s.retrieval_k, filter=filter_)
        if not results:
            suffix = f" for project '{project_name}'" if project_name else ""
            return f"No project information found{suffix}."
        return "\n\n---\n\n".join(
            f"[Project: {d.metadata.get('project', 'unknown')} | "
            f"Section: {d.metadata.get('section', '-')} / "
            f"{d.metadata.get('subsection', '-')}]\n{d.page_content}"
            for d in results
        )

    return [search_about_me, search_projects]


def build_agent() -> AgentExecutor:
    s = get_settings()
    llm = ChatOpenAI(
        model=s.openai_model,
        temperature=0.2,
        api_key=s.openai_api_key,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    tools = _build_tools()
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        return_intermediate_steps=True,
        max_iterations=5,
        handle_parsing_errors=True,
    )


def to_lc_messages(history: list[ChatMessage]):
    """Convert API ChatMessage history -> LangChain message objects."""
    out = []
    for m in history:
        if m.role == "user":
            out.append(HumanMessage(content=m.content))
        else:
            out.append(AIMessage(content=m.content))
    return out
