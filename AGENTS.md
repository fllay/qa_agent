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

## 2026-06-09

- Split the frontend into a black/white two-page flow: `/` home page and `/chat` agent chat page.
- Added chat thread persistence so each topic gets a default `Agent Chat` thread and can have additional subtopic threads.
- Added thread listing and creation APIs, plus chat UI controls for Agent Chat, New thread, and manual topic creation modal.
- Simplified chat controls by removing the duplicate New thread button and profile avatar, and renamed the default Agent Chat UI to QA Agent.
- Removed the top-right QA Agent header label from the chat page while keeping the central chat title.
- Fixed chat sidebar collapse behavior so it hides completely instead of squeezing text into a broken narrow column.
- Added a fixed sidebar toggle outside the sidebar so it stays visible and can reopen thread history after collapse.
- Removed the home button from the chat page header.
- Changed the chat sidebar interaction to match `agent-chat-ui`: a fixed 300px history panel slides off-canvas while the main chat area transitions its left margin.
- Adjusted sidebar toggle visibility so the close button is inside the open sidebar, while the open button appears only after collapse.
- Verified the chat sidebar toggle behavior in the browser: the reopen button is hidden while the sidebar is open, appears after collapse, and hides again after reopening.
- Realigned the chat sidebar by removing asymmetric padding, using a shared sidebar width variable, and keeping the menu button and title in the same left-aligned header row.
- Matched the inner and outer sidebar toggle positions by using a shared sidebar edge offset for both the fixed reopen button and the open-sidebar padding.
- Fixed chat topic creation to ingest GitHub URLs and uploaded documents from the modal, changed ingestion to append sources instead of replacing them, corrected the message-area layout after the first exchange, and enabled Enter-to-send with Shift+Enter for new lines.
- Added per-topic sidebar actions: Settings opens a source-upload modal for the selected topic, and Delete removes the topic and returns the chat view to QA Agent when the active topic is removed.
- Hardened topic deletion on Windows by clearing read-only attributes during recursive folder cleanup so Git-cloned pack files under `.git` do not crash the delete API.
- Changed modal topic creation and topic-source updates to show immediate progress, close the modal without waiting for Graphify to finish, mark the topic as indexing in the sidebar, and ignore repeat submits while the request is already running.
- Reduced GitHub collector fan-out for large repositories by capping detailed issue and pull-request expansion so indexing completes on repos like `srsran/srsRAN_Project` instead of stalling in long REST API loops.
- Removed `.git` directories from cloned repository and wiki sources before Graphify runs so graph building does not waste time or disk on Git object packs.
- Moved the Graphify availability check to the start of ingestion so missing `GRAPHIFY_BIN` surfaces immediately as an error instead of spending minutes cloning and collecting GitHub data first.
- Pointed `GRAPHIFY_BIN` at the installed user-site `graphify.exe` and fixed a missing `shutil` import in the GitHub collector that surfaced once live Graphify-backed ingestion actually ran.
- Updated Graphify invocation to the current CLI shape: `graphify extract <source_dir> --out <topic_dir> --no-cluster`, which produces `graphify-out/graph.json` without the obsolete bare-path call.
- Normalized Graphify input/output paths to absolute paths so the CLI works correctly when invoked from the topic-local `graphify/` working directory.
- Fixed graph output discovery to search the topic root as well, because current Graphify writes `graphify-out/graph.json` under `<topic_dir>/`, not under the temporary `graphify/` cwd.
- Added explicit empty-graph detection so archived or metadata-only repositories surface a clear error instead of looking successfully indexed with zero retrievable nodes.
- Added per-topic progress persistence (`progress_percent`, `progress_label`) and hooked ingestion stages into it so indexing topics can show a live percentage and current stage text while the chat page polls.
- Added a frontend guard so indexing topics never render `0%` in the sidebar once they have entered the in-progress state, and bumped the chat asset version string again to force browsers onto the updated bundle.
- Replaced raw long backend errors in the chat UI with shorter user-facing messages and constrained toast width/wrapping so empty-graph or config errors do not break the composer layout.
