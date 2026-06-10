# CI/CD Plan — Oswald Portfolio Chatbot

## Overview

This repository contains:

- `chatbot/` — FastAPI agentic-RAG API, ingestion pipeline, guardrails
  (`app/utils/sanitizer.py`, `app/prompts/`), test suite (`tests/`), and the deployment `Dockerfile`
- `website/` — static frontend with the chatbot widget
- `infra/docker-compose.yml` — runtime for the `chatbot` API + `web` (nginx) reverse proxy
- `Makefile` — local dev, ingest, and compose convenience targets
- `requirements-dev.txt` + `chatbot/pyproject.toml` — dev tooling (ruff, black, pytest) and its config
- `.pre-commit-config.yaml` — local pre-commit hooks mirroring the CI lint job
- `.github/workflows/ci-cd.yml` — the single GitHub Actions pipeline (below)

The pipeline lints, tests, validates the Compose manifest on every push/PR, then builds and
deploys on pushes to `main`.

## Goals

- Lint + test every push and pull request before anything is built
- Build the chatbot image cleanly from `chatbot/Dockerfile` and publish it to GHCR
- Deploy `main` to a host over SSH via Docker Compose
- Preserve runtime data, especially `chatbot/data/chroma`
- Keep secrets (`OPENAI_API_KEY`, SSH key) out of source control

## Pipeline — `.github/workflows/ci-cd.yml`

A single workflow with five jobs. Each downstream job `needs:` the previous one, so a failure
stops the pipeline before deploy. Python is pinned to **3.12** everywhere to match the
`python:3.12-slim` base image in `chatbot/Dockerfile`.

```
lint ──┬── test ───────────┐
       └── validate-compose ┴── build ── deploy
```

### 1. `lint` (every push + PR)
- `pip install -r requirements-dev.txt`
- `ruff check chatbot` — lint + import ordering (ruff replaces flake8 + isort)
- `black --check chatbot` — formatting
- Config (line length 88, target py312) lives in `chatbot/pyproject.toml`, so local pre-commit,
  ad-hoc runs, and CI all behave identically.

### 2. `test` (every push + PR, `needs: lint`)
- Runs with `working-directory: chatbot` so `import app...` and `tests/` resolve correctly.
- Sets `OPENAI_API_KEY: sk-ci-test-not-real`. **Why:** `app/config.py` validates
  `OPENAI_API_KEY` at import time, and `tests/test_api_routes.py` imports `app.main`. Tests mock
  all network/LLM calls, so any non-placeholder value lets the suite import and run.
- `pip install -r requirements.txt && pip install -r ../requirements-dev.txt`
- `pytest -v --cov=app --cov-report=term-missing` (pytest runs the existing `unittest.TestCase`
  classes). 13 tests currently pass.

### 3. `validate-compose` (every push + PR, `needs: lint`)
- `cp chatbot/.env.example chatbot/.env` first. **Why:** the Compose manifest references
  `env_file: ../chatbot/.env`, which is git-ignored; without it `docker compose config` fails.
- `docker compose -f infra/docker-compose.yml config`

### 4. `build` (push to `main` only, `needs: [test, validate-compose]`)
- `docker/login-action@v3` → GHCR (`ghcr.io`), user `${{ github.actor }}`,
  password `${{ secrets.GITHUB_TOKEN }}` (auto-provided; needs `packages: write`, set at workflow level).
- `docker/build-push-action@v5` with `context: chatbot`, `file: chatbot/Dockerfile`,
  `push: true`, tagging both `:latest` and `:${{ github.sha }}` under
  `ghcr.io/${{ github.repository_owner }}/oz-portfolio-chatbot`.

### 5. `deploy` (push to `main` only, `needs: build`)
- `appleboy/ssh-action@v1.0.3` using `SSH_HOST` / `SSH_USER` / `SSH_KEY` secrets.
- Remote script: `cd ${{ secrets.DEPLOY_PATH }}/infra && docker compose pull && docker compose up -d`.
- `docker compose pull` works because the `chatbot` service now carries an `image:` tag pointing
  at the GHCR image (in `infra/docker-compose.yml`).

## Required GitHub secrets

| Secret | Purpose |
| --- | --- |
| `SSH_HOST` | Deployment host address |
| `SSH_USER` | SSH user on the host |
| `SSH_KEY` | Private key for that user |
| `DEPLOY_PATH` | Absolute path to the checked-out repo on the host (compose runs from `$DEPLOY_PATH/infra`) |

`GITHUB_TOKEN` is provided automatically by Actions for the GHCR push — no manual secret needed.
(The old `REGISTRY` / `IMAGE_NAME` secrets are no longer used.)

## Deployment runbook (SSH host + Docker Compose)

**Registry:** GitHub Container Registry — `ghcr.io/ozdurand/oz-portfolio-chatbot`.

### Host prerequisites (one time)
1. Install Docker Engine + the Compose plugin.
2. Clone the repo to `DEPLOY_PATH` (e.g. `/opt/oswalddurand`).
3. Create the **real** `chatbot/.env` on the host (never committed) with a production
   `OPENAI_API_KEY` and any overrides — model names, `ALLOWED_ORIGINS` (your public site origin),
   `RETRIEVAL_K`, etc. Use `chatbot/.env.example` as the template.
4. If the image is private, `docker login ghcr.io` once with a PAT that has `read:packages`.
5. The `chatbot/data/chroma` host directory is bind-mounted (see compose) and persists the vector
   index across image updates — do not delete it on deploy.

### First deploy / populating the index
After the first `docker compose up -d`, the Chroma index is empty. Run ingestion on the host:
```bash
make ingest-projects                      # index chatbot/data/projects/
make ingest-website U='https://your-site' # scrape + index the live site
```
(Or `docker compose exec chatbot python -m scripts.ingest projects` inside the container.)

### Update flow (automatic on merge to `main`)
1. Merge to `main` → CI runs lint → test → validate-compose → build (push image) → deploy.
2. The deploy job SSHes in and runs `docker compose pull && docker compose up -d`, which pulls the
   new `:latest` image and recreates the `chatbot` container. The persisted Chroma volume is reused.

### Frontend
`website/` is static and served by the `web` (nginx) service from the same compose stack
(`infra/nginx/default.conf` reverse-proxies `/api` to the chatbot). If you prefer, host the static
site separately on a CDN / GitHub Pages and point its widget at the chatbot API origin.

## Local development & start/stop

Day-to-day local commands live in the `Makefile`:

| Command | Action |
| --- | --- |
| `make dev` | Run the API locally with hot-reload on port 8000 |
| `make ingest-projects` | Index `chatbot/data/projects/` |
| `make ingest-website U='https://...'` | Scrape + index URL(s) |
| `make up` / `make down` | Start / stop the full nginx + chatbot compose stack |
| `make logs` | Tail compose logs |

`START_STOP.md` documents the manual two-terminal flow (static site on port 8001, API on port 8000)
and the PowerShell stop-by-port snippets for Windows.

### Local lint / test (match CI before pushing)
From the repo root:
```bash
pip install -r requirements-dev.txt
ruff check chatbot
black --check chatbot
```
From `chatbot/` (PowerShell sets the dummy key inline):
```powershell
$env:OPENAI_API_KEY = 'sk-ci-test-not-real'
pytest -v --cov=app
```
Install the pre-commit hooks once with `pre-commit install` to run ruff + black on every commit.
