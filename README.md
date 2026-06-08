# QA Agent

A local-first web app for building topic-managed Graph RAG Q&A agents over GitHub repositories and documents.

The backend uses FastAPI and LangGraph. Graph data is produced by Graphify and loaded from each topic's `graph.json` output.

## Features

- Manage independent topics.
- Ingest GitHub source code plus repository metadata, issues, pull requests, activity, wiki, local folders/files, or uploaded documents.
- Run Graphify per topic and keep graph outputs isolated.
- Ask topic-scoped questions through a LangGraph workflow.
- Choose `local` or `openrouter` as the LLM provider for answer generation.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
copy .env.example .env
python -m uvicorn qa_agent_app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Graphify

Install Graphify separately and set `GRAPHIFY_BIN` in `.env` if the command is not `graphify`.

```env
GRAPHIFY_BIN=graphify
```

The app runs Graphify inside each topic workspace and searches for the newest `graph.json`.

## GitHub Ingestion

When you add a GitHub repository URL, the app clones source code and also writes GitHub repository data into `_github/*.md` before Graphify runs. This includes repository metadata, languages, branches, tags, releases, contributors, labels, milestones, issues with comments, pull requests with comments/reviews/changed files, workflows, discussions when token access allows it, and public wiki content when available.

Unauthenticated public repositories work, but GitHub rate limits are lower. Add `GITHUB_TOKEN` for higher limits or private repositories:

```env
GITHUB_TOKEN=github_pat_...
GITHUB_MAX_PAGES=10
GITHUB_PER_PAGE=100
```

## LLM Provider

The app supports two providers configured through `.env` or the backend settings API.

Local provider uses a local OpenAI-compatible endpoint such as Ollama, LM Studio, or vLLM. If the endpoint is not running, the app falls back to a local graph-context answer so the UI remains usable.

```env
QA_AGENT_LLM_PROVIDER=local
QA_AGENT_LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
QA_AGENT_LOCAL_LLM_API_KEY=local
QA_AGENT_LOCAL_LLM_MODEL=llama3.1:8b
```

OpenRouter provider requires one main model and two reserve models. OpenRouter receives all three through its fallback `models` array.

```env
QA_AGENT_LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MAIN_MODEL=openrouter/auto
OPENROUTER_RESERVE_MODEL_1=openai/gpt-4o-mini
OPENROUTER_RESERVE_MODEL_2=google/gemini-flash-1.5
```

LLM generation has no app-level timeout. Long generations can continue until the model provider or network closes the request.

## Tests

```powershell
pytest
```
