"""Vector store + embeddings factories.

Two named collections live in the same persistent Chroma directory:
- website_content : pages scraped from the portfolio site
- projects        : deep project documentation (How / Why / What, POC->MVP->Prod)
"""
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

from app.config import get_settings


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
