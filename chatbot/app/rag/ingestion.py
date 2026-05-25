"""Ingestion: scrape the portfolio site and load project markdown into Chroma."""
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.config import get_settings
from app.rag.vectorstore import get_vectorstore


# --------------------------------------------------------------------------- #
# Website
# --------------------------------------------------------------------------- #
def scrape_website(urls: list[str], timeout: int = 30) -> list[Document]:
    """Fetch each URL and extract clean visible text.

    Strips <script>, <style>, <nav>, <header>, <footer>. If your site is a
    SPA where content is rendered client-side, swap httpx for Playwright.
    """
    docs: list[Document] = []
    with httpx.Client(timeout=timeout, follow_redirects=True,
                      headers={"User-Agent": "PortfolioBot/1.0"}) as client:
        for url in urls:
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except Exception as e:
                print(f"[scrape] {url} failed: {e}")
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
            if not text:
                print(f"[scrape] {url} produced no text — skipping")
                continue

            title = soup.title.string.strip() if soup.title and soup.title.string else url
            docs.append(Document(
                page_content=text,
                metadata={
                    "source": url,
                    "title": title,
                    "domain": urlparse(url).netloc,
                    "type": "website",
                },
            ))
            print(f"[scrape] {url} -> {len(text)} chars")
    return docs


# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #
def load_projects(projects_dir: Path) -> list[Document]:
    """Load all .md files in projects_dir, splitting on H1/H2 headers.

    File stem becomes the `project` metadata key, which the agent can use
    to filter retrieval to a specific project on request.
    """
    headers_to_split_on = [("#", "section"), ("##", "subsection")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)

    docs: list[Document] = []
    if not projects_dir.exists():
        print(f"[projects] directory {projects_dir} does not exist")
        return docs

    for path in sorted(projects_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            continue
        project_name = path.stem

        chunks = md_splitter.split_text(text)
        for chunk in chunks:
            chunk.metadata.update({
                "source": str(path),
                "project": project_name,
                "type": "project",
            })
            docs.append(chunk)
        print(f"[projects] {project_name} -> {len(chunks)} header-sections")
    return docs


# --------------------------------------------------------------------------- #
# Chunking + indexing
# --------------------------------------------------------------------------- #
def chunk_documents(
    docs: list[Document],
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[Document]:
    """Second-pass chunking — header sections can still be huge."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(docs)


def ingest_website(urls: list[str]) -> int:
    docs = scrape_website(urls)
    if not docs:
        print("[ingest] no website docs to index")
        return 0
    chunks = chunk_documents(docs)
    vs = get_vectorstore(get_settings().website_collection)
    vs.add_documents(chunks)
    print(f"[ingest] indexed {len(chunks)} website chunks from {len(urls)} URL(s)")
    return len(chunks)


def ingest_projects(projects_dir: Path) -> int:
    docs = load_projects(projects_dir)
    if not docs:
        print("[ingest] no project docs to index")
        return 0
    chunks = chunk_documents(docs)
    vs = get_vectorstore(get_settings().projects_collection)
    vs.add_documents(chunks)
    print(f"[ingest] indexed {len(chunks)} project chunks")
    return len(chunks)
