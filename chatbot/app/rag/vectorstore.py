"""Vector store + embeddings factories.

Two named collections live in the same persistent Chroma directory:
- website_content : pages scraped from the portfolio site
- projects        : deep project documentation (How / Why / What, POC->MVP->Prod)
"""

from datetime import datetime

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app.config import get_settings


def _ensure_provenance(doc: Document) -> None:
    meta = doc.metadata or {}
    if "source" not in meta:
        meta["source"] = "unknown"
    meta.setdefault("ingested_at", datetime.utcnow().isoformat() + "Z")
    doc.metadata = meta


def add_documents_safe(vs: Chroma, docs: list[Document]) -> None:
    """Sanitize and ensure provenance for documents before adding to Chroma."""
    for d in docs:
        try:
            _ensure_provenance(d)
        except Exception:
            # best-effort; don't fail the whole batch
            pass
    vs.add_documents(docs)


def get_embeddings() -> OpenAIEmbeddings:
    s = get_settings()
    return OpenAIEmbeddings(
        model=s.openai_embedding_model,
        api_key=s.openai_api_key,
    )


def get_vectorstore(collection_name: str) -> Chroma:
    s = get_settings()
    return Chroma(
        collection_name=collection_name,
        persist_directory=s.chroma_persist_dir,
        embedding_function=get_embeddings(),
    )
