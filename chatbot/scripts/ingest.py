"""CLI for indexing content into Chroma.

Examples:
    # Index website pages
    python -m scripts.ingest website https://your-portfolio.com https://your-portfolio.com/about

    # Index all project docs in data/projects/
    python -m scripts.ingest projects

    # Custom projects directory
    python -m scripts.ingest projects --dir ./my-projects
"""
import argparse
from pathlib import Path

from app.rag.ingestion import ingest_projects, ingest_website


def main():
    parser = argparse.ArgumentParser(description="Ingest content into the vector store")
    sub = parser.add_subparsers(dest="cmd", required=True)

    web = sub.add_parser("website", help="Scrape and index website URLs")
    web.add_argument("urls", nargs="+", help="One or more URLs to scrape")

    proj = sub.add_parser("projects", help="Index markdown project docs")
    proj.add_argument("--dir", default="data/projects",
                      help="Directory containing project .md files")

    args = parser.parse_args()

    if args.cmd == "website":
        ingest_website(args.urls)
    elif args.cmd == "projects":
        ingest_projects(Path(args.dir))


if __name__ == "__main__":
    main()
