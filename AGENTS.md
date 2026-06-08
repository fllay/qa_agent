# Repo Guidance

- Use this file as repo guidance for future work.
- Always update this file with a concise summary of completed changes.
- Keep the project local-first where possible: topic data, source files, Graphify outputs, and SQLite state live under `data/` unless configured otherwise.
- Backend agent orchestration should use LangGraph.
- Graph data integration should use Graphify outputs, especially `graph.json`, with optional CLI execution through the configured Graphify command.

# Change Log

## 2026-06-08

- Created a FastAPI web app scaffold for a topic-managed Graph RAG Q&A agent.
- Added LangGraph backend workflow for retrieval, graph-context assembly, and answer generation.
- Added per-topic SQLite persistence and local topic workspaces under `data/topics/`.
- Added Graphify CLI integration that runs per topic and discovers `graph.json` outputs.
- Added source ingestion for GitHub repositories, local document paths, and uploaded files.
- Added a static web UI for creating topics, ingesting sources, viewing graph status, and asking questions.
- Added tests for repository services and the LangGraph workflow.
- Replaced the topic description textarea with a URL/document source list control in the create-topic UI.
- Added an upload-documents button to the create-topic source list so document filenames can be added without typing paths.
- Removed local-path wording from the create-topic source placeholder and adjusted the source controls layout to prevent cramped input/buttons.
- Rebalanced the landing hero and create-topic card layout by reducing oversized headline scaling, aligning the form higher, and improving form spacing.
- Replaced `none/openai` LLM config with `local` and `openrouter` providers, including OpenRouter main plus two reserve model settings.
- Added provider request timeouts and disabled SDK retries so local-provider fallback stays responsive when no local LLM endpoint is running.
- Added persisted LLM provider settings APIs and a web UI panel for selecting local versus OpenRouter and editing OpenRouter main/reserve models.
- Removed the LLM provider settings panel from the frontend; provider configuration remains available through `.env` and backend settings APIs.
- Removed active LLM timeout configuration and updated LLM calls to use no app-level timeout for model generation.
- Reworked the landing UI into a more balanced dashboard with compact hero spacing, workflow chips, capability cards, and a higher workspace section.
- Simplified user-facing landing copy by replacing technical Graph RAG/Graphify/LangGraph phrasing with plain-language topic, source, and question wording.
- Kept Topics refresh feedback on the button/toast only and removed the persistent status text under the section heading.
- Rebalanced the Topics header by vertically centering the heading/button and reducing the refresh button size.
- Expanded GitHub URL ingestion so cloned source code is supplemented with generated `_github` Markdown files for repo metadata, issues, pull requests, activity, workflows, discussions when token access allows it, and wiki content before Graphify builds the topic graph.
