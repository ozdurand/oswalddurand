.PHONY: help dev ingest-website ingest-projects up down logs build clean

help:
	@echo "Targets:"
	@echo "  dev                  Run chatbot locally with hot-reload (port 8000)"
	@echo "  ingest-website U=... Scrape and index URL(s): make ingest-website U='https://...'"
	@echo "  ingest-projects      Index all markdown in chatbot/data/projects/"
	@echo "  up                   Start nginx + chatbot via docker compose"
	@echo "  down                 Stop and remove containers"
	@echo "  logs                 Tail compose logs"
	@echo "  build                Rebuild chatbot image"
	@echo "  clean                Remove the local Chroma index (forces a full reindex)"

dev:
	cd chatbot && uvicorn app.main:app --reload

ingest-website:
	@test -n "$(U)" || (echo "Usage: make ingest-website U='https://your-site.com [https://...]'"; exit 1)
	cd chatbot && python -m scripts.ingest website $(U)

ingest-projects:
	cd chatbot && python -m scripts.ingest projects

up:
	docker compose -f infra/docker-compose.yml up -d --build

down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f

build:
	docker compose -f infra/docker-compose.yml build chatbot

clean:
	rm -rf chatbot/data/chroma/*
