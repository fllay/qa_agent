# Repo Guidance

- Use this file as repo guidance for future work.
- Always update this file with a concise summary of completed changes.
- Keep the project local-first where possible: topic data, source files, Graphify outputs, and SQLite state live under `data/` unless configured otherwise.
- Backend agent orchestration should use LangGraph.
- Graph data integration should use Graphify outputs, especially `graph.json`, with optional CLI execution through the configured Graphify command.

# Change Log

## 2026-06-18

- Flattened Cosmograph link sizing across graph scales so line width no longer depends on the earlier broad width-scaling curve: links now use fixed relation-based widths per graph-size band, large-graph per-link alpha is lower to avoid blue haze, and the global visibility/fade settings were retuned so small-graph links remain readable while big graphs keep clearer individual lines.
- Raised large-graph Cosmograph link visibility again by setting the large-graph global link opacity to `0.75`, reducing the large-graph minimum fade-out transparency so lines remain readable while zoomed out, and increasing the per-link RGBA alpha values used by directory/file containment edges.
- Compared the local graph-renderer files against the deployed `192.168.168.98:/home/user/qa_agent` checkout, confirmed the server was still on an older graph viewer/fallback-graph implementation, uploaded the newer local `chat.js`, `chat.html`, `fallback_graph.py`, related fallback-graph tests, and `AGENTS.md`, then rebuilt the `qa_agent-qa-agent` Docker service so the server now matches local hashes and serves the `20260618-graph-relations1` asset version.
- Reworked the large fallback-graph topology for the graph modal so repository previews no longer degenerate into a single repo-to-file star: fallback graphs now add real directory nodes plus `contains_dir` and `contains_file` hierarchy edges, and the Cosmograph frontend now seeds node `x/y` positions from the relation graph, reduces large-graph link weight/opacity, and increases spacing so dense repository graphs spread according to actual structure instead of collapsing into a thick circular hub.

## 2026-06-16

- Diagnosed a local runtime confusion where the QA Agent app was already running in Docker on port `8000` (`qa_agent-qa-agent-1`), so extra Uvicorn launches failed with `WinError 10048`; verified the container serves `/chat` successfully via `http://localhost:8000/chat`, while ad hoc checks against `127.0.0.1:8000` were less reliable on this Windows/Docker setup and ports `8010`/`8011` were not active listeners.

## 2026-06-15

- Added a fallback-graph cleanup pass for large-repo timeout recovery by excluding generated and dependency directories such as `graphify-out`, `graphify`, `node_modules`, and virtualenv caches from local fallback graph construction, preventing Graphify cache artifacts from showing up as fake repository content in `srsran/srsRAN_Project -> ocudu` indexing results.
- Investigated the server-side graph popup failure on `192.168.168.98` and confirmed the deployed topic graph API was returning HTTP `200` with a very large Graphify payload (`63817` nodes, `195801` edges), so the browser bottleneck was client-side graph layout/render cost rather than graph loading.
- Kept full Graphify graph payloads enabled in the backend and reworked the graph viewer's large-graph render path to avoid the most expensive force-relaxation and overlap-separation passes for very large graphs, fit the initial viewport to full graph bounds, and cull off-screen nodes plus many off-screen/low-zoom edges during canvas redraws.
- Added a cache-busting `chat.js`/`chat.css` version bump for the updated full-graph viewer and redeployed the Dockerized app on `192.168.168.98`, rebuilding the `qa_agent-qa-agent` image and restarting `qa_agent-qa-agent-1` with the full graph payload path still active.
- Corrected the full-graph viewer after the first large-graph render was visually too heavy: kept the full payload, reduced large-graph node radii and opacity, rendered overview edges as faint hairlines, spread large communities with deterministic lightweight placement, and made zoom bounds preserve the full-graph overview instead of jumping into the dense center.
- Optimized the Dockerfile for faster rebuilds by installing Python dependencies and `graphifyy` before copying `src/`, enabling a BuildKit pip cache mount, importing the app through `PYTHONPATH=/app/src`, and avoiding a source-dependent `pip install .` layer on every frontend/backend edit.
- Fixed the next full-graph popup regression by removing upfront allocation of large edge render objects, keeping large-graph edges hidden until the user zooms in enough for them to matter, tightening the overview placement curve so reset/open no longer collapses into a tiny unreadable cloud, and redeploying the updated frontend to `192.168.168.98`.
- Improved large-graph interaction performance by adding a spatial index for visible-node and hover queries, drawing overview nodes as cheap point marks, skipping large-graph edge work while dragging, capping zoomed edge draws, and uploading the optimized Dockerfile plus updated graph frontend to the server.
- Optimized zoomed-out full-graph interaction by pre-rendering large graphs into a cached overview canvas layer, using that bitmap for low-zoom pan/zoom frames, hiding labels until closer zoom, and keeping full individual-node rendering for closer inspection.
- Replaced the low-zoom cached bitmap with aggregated large-graph level-of-detail points plus soft edge falloff, keeping zoomed-out interaction fast without the rectangular pale overview artifact.
- Added a second large-graph mid-zoom level-of-detail stage that keeps slight zoom-in interaction aggregated, suppresses edge and hover work until deeper zoom, and only switches to direct per-node rendering once the visible node count is materially smaller.
- Tuned the first direct-render band further by extending aggregation a bit longer, dropping most stroke work while dense direct node counts remain high, always redrawing and labeling the main repository node on top, and increasing node size across the large-graph viewer.
- Changed main-node pinning to treat all repository-family nodes as persistent main nodes, redrawing and labeling each of them on top, and eased the zoom size curve again so nodes stay larger at smaller zoom scales.
- Stabilized graph colors across zoom modes by deriving overview and mid-LOD point alpha from the underlying node opacity instead of separate family-based fade formulas, so colors no longer visibly shift when the renderer changes mode.
- Fixed the dark outline artifact by softening the default node stroke color and preventing pinned repository nodes from being outlined in both the base node pass and the overlay pass at the same time.
- Replaced the custom graph canvas renderer with a Cosmograph WebGL viewer loaded in the static frontend, mapped the existing graph payload into direct point/link color and size fields, kept repository nodes pinned in `showLabelsFor`, and preserved the existing graph modal/sidebar shell around the new viewer.
- Replaced the remote Cosmograph CDN ESM import with a locally served bundled `vendor/cosmograph-bundle.js` build pinned to `@cosmograph/cosmograph@2.3.2`, removing the runtime dependency graph that triggered `luma.gl` multiple-version warnings in the browser console.
- Rebalanced the first Cosmograph styling pass by increasing point size inputs and global point scale, reducing direct link widths and opacity, slightly increasing point sampling distance, and enlarging simulation space so node visibility stays ahead of link density in large repository graphs.
- Tuned the Cosmograph follow-up pass by making links thinner but slightly more visible, enlarging non-repository nodes further, and stopping the simulation shortly after graph rebuild so the layout settles instead of continuing to drift.
- Raised Cosmograph link visibility again by keeping links thin but moving their per-link RGBA alpha and global `linkOpacity` much closer to opaque, so graph connections remain readable instead of fading into the stage background.
- Removed the remaining relation-based link width differences in the Cosmograph graph viewer by switching to one fixed link width per graph-size band, bumped the graph asset version to `20260618-graph-relations3`, and redeployed the frontend to `192.168.168.98`.
- Changed the Cosmograph interaction model toward Obsidian-style graph behavior without forcing a dark theme: graph nodes can now be dragged, the simulation settles much earlier, repository nodes stay pinned after layout, clicking a node focuses it and selects its neighborhood while greying out unrelated nodes/links, and the graph asset version was bumped to `20260618-graph-behavior1`.
- Reworked graph topology seeding toward relation-first Obsidian-like behavior: initial positions no longer start from family-orbit buckets, but from connected components and actual adjacency, with component-centered force relaxation and tighter relation-length targets so linked nodes cluster by real graph structure instead of by node type; bumped the asset version to `20260618-graph-topology1`.
- Removed node drag from the Cosmograph graph behavior while keeping the newer relation-first topology layout, removed the temporary drag settle hooks, and bumped the graph asset version to `20260618-graph-topology2`.
- Retuned the graph viewer for clearer light-mode rendering by brightening the stage and modal surfaces, increasing link/node contrast in the Cosmograph config, darkening secondary graph text, and bumping the frontend asset version to `20260618-graph-light1`.
- Fixed graph layer ordering so important nodes render above less important ones by sorting the Cosmograph point input from low-priority nodes to high-priority repository/directory/high-degree nodes before draw, and bumped the frontend asset version to `20260618-graph-light2`.
- Removed the remaining Cosmograph node-size zoom skew by flattening the active viewer's global `pointSizeScale` to `1` while keeping `scalePointsOnZoom: false`, so node radii stay visually stable across zoom levels; bumped the frontend asset version to `20260618-graph-light3`.
- Removed the last pre-render node-size ratio in the active Cosmograph viewer by passing raw `node.radius` values straight through as direct pixel sizes instead of inflating them again by `small/medium/huge` graph-size multipliers; bumped the frontend asset version to `20260618-graph-light4`.
- Replaced the flat Cosmograph size pass with shared Obsidian-style zoom bands across all graph sizes: overview, inspection, detail, and focus now retune node scale and link weight/visibility together so zoomed-in graphs keep readable nodes without letting links dominate; bumped the frontend asset version to `20260618-graph-light6`.
- Fixed the graph modal loading stall introduced by the shared zoom-band pass: `onGraphRebuilt` no longer force-applies `setConfig`, the initial zoom band is seeded into the first Cosmograph config instead, and runtime visual retuning now waits for actual zoom changes instead of recursively rebuilding the graph; bumped the frontend asset version to `20260618-graph-light7`.
- Fixed the next Cosmograph zoom-band regression where runtime `setConfig` calls dropped the active graph data and triggered the `Points source data is not provided in points` error: the graph scene now retains the prepared `points`, `links`, and base config, and zoom-band updates reapply that full config with the new visual scales; bumped the frontend asset version to `20260618-graph-light8`.
- Retuned the light-mode node-family palette for clearer separation in both the legend and the graph itself: repository nodes now use a stronger violet-blue, directories a darker slate, config a teal accent, documents a deeper amber, and code a brighter cyan; bumped the frontend asset version to `20260618-graph-light9`.
- Increased effective node size for dense Graphify graphs so large and huge graph nodes are easier to see and click: raised the large-graph base radii/minimums in the graph model and increased the Cosmograph zoom-band point-size base for `largeGraphMode` and `hugeGraphMode`; bumped the frontend asset version to `20260618-graph-light10`.
- Doubled the dense Graphify node sizing again for large and huge graphs by doubling both the large-graph radius feed in the graph model and the large/huge Cosmograph zoom-band point-size base, leaving small and medium graph sizing alone; bumped the frontend asset version to `20260618-graph-light11`.
- Backed the dense Graphify node sizing down from the previous overcorrection by moving both the large-graph radius feed and the large/huge Cosmograph zoom-band point-size base to a middle setting between the earlier clickable pass and the later doubled pass; bumped the frontend asset version to `20260618-graph-light12`.
- Cleared the `git pull` blocker on `192.168.168.98:/home/user/qa_agent` by stashing the server's older uncommitted `chat.html`/`chat.js` frontend edits under `codex-server-pre-pull-2026-06-18`, fast-forwarding `main` from `57adbad` to `5fe1b54`, and confirming the remote worktree is clean afterward.

## 2026-06-16

- Restyled the Cosmograph graph modal toward an Obsidian-like graph view by switching the stage, modal chrome, and sidebar cards to a dark slate surface, moving node families to a cooler muted palette, and retuning link colors plus ring highlights so the graph reads like a dark knowledge-map instead of a bright white diagram.
- Reduced node size specifically for smaller Cosmograph graphs by making point radii and global point scaling depend on graph size, then backed out the forced dark modal/stage theme so the graph keeps the lighter QA Agent surface while preserving the newer renderer and small-graph sizing fix.
- Rebalanced the Cosmograph size ratios again so small graphs render with noticeably tighter node radii, while medium/large graphs keep readable nodes but taper link widths and link opacity down as total node count climbs, preventing dense large graphs from being dominated by heavy lines.
- Diagnosed the latest Docker complaint as a startup bottleneck rather than a Dockerfile compile failure: the image built cleanly, but `docker-entrypoint.sh` was recursively `chown`ing the entire bind-mounted `data/` tree on every start, which is expensive with the current `~65k` filesystem entries; changed the entrypoint to perform the recursive ownership repair once by default using a marker file, with `QA_AGENT_FORCE_RECURSIVE_CHOWN=1` available for an explicit full re-run.
- Increased Graphify timeout handling for large ingests by raising the base default from `900` to `1800` seconds in app and Docker defaults, and made `GraphifyClient` scale its effective timeout up to `3600` or `7200` seconds automatically for large source trees based on file-count and on-disk-size thresholds, so big repositories are less likely to fail on the initial graph build.
- Hardened ingestion for large repositories such as `srsran/srsRAN_Project -> ocudu` by treating Graphify timeouts like empty-graph outcomes: the app now falls back to the local repository graph builder instead of leaving the topic in a hard error state, and regression coverage was added for the timeout-to-fallback path.

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

## 2026-06-10

- Added archived-repository diagnosis on empty Graphify outputs so migrated GitHub repos no longer fall back to the generic "not analyzable code" error.
- Detects transition notices and replacement GitLab URLs from cloned repo content, returning a concise actionable message such as the `srsran/srsRAN_Project` handoff to `https://gitlab.com/ocudu/ocudu`.
- Added a regression test for archived-repo empty-graph handling and verified the helper directly against the locally cloned `srsRAN_Project` snapshot under `data/topics/`.
- Changed GitHub ingestion to follow archived-repo replacement URLs automatically, so `srsran/srsRAN_Project` now clones the active OCUDU GitLab repository before graph building.
- Added a local fallback graph builder that synthesizes `fallback-graph.json` from repository README/config/code snapshots whenever Graphify returns an empty graph, allowing topics to reach `ready` instead of failing.
- Tuned retrieval to prioritize repository-level summary nodes for broad prompts like "summarize this repository" and verified a live ingest plus QA round-trip against `https://github.com/srsran/srsRAN_Project`.
- Fixed GitLab replacement cloning under the `C:\Program Files (x86)\Git\qa_agent` workspace by normalizing handoff URLs to canonical `.git` form and cloning to an absolute target path, avoiding the redirect-triggered `could not lock config file ... .git/config` failure.
- Hardened repository cloning further by forcing `core.longpaths=true` on clone and retrying with a forced `git checkout -f HEAD` when Git reports `Clone succeeded, but checkout failed`, so recoverable Windows checkout problems do not fail topic ingestion immediately.
- Replaced the no-local-LLM answer fallback from a raw graph-context dump with a readable repository summary that highlights the active codebase, archived handoff repo, and a few relevant files, while keeping a generic fallback for non-repository graph nodes.
- Shortened the broad no-local-LLM repository summary further and preserved chat message line breaks with `white-space: pre-wrap`, so prompts like `describe this project` render as a compact three-paragraph answer instead of one dense wrapped block.
- Extended the broad repository fallback to include the extracted project-purpose sentence from indexed README context, so prompts like `what this project do` explain that OCUDU is a 5G CU/DU RAN solution with a full L1/L2/L3 stack instead of only saying it is the active codebase.
- Removed OCUDU-specific fallback extraction logic and replaced it with generic descriptive-sentence extraction from repository context, with regression coverage showing the same path works for unrelated repos such as a sample `AcmeFlow` workflow platform.
- Reworked the chat-session frontend to behave more like `agent-chat-ui`: each thread now keeps its own local session transcript and draft, the composer auto-resizes and disables while requests are in flight, assistant replies expose inline copy/refresh actions, and the transcript uses a sticky bottom chat layout with loading and scroll-to-bottom behavior.
- Removed the regressed top chat-page title from the session layout so the empty state no longer shows a duplicate `Agent Chat` heading above the main content.
- Widened the chat sidebar again and changed topics into folder-style groups that expand to show their saved threads, with a per-topic `New chat` action for creating additional chats inside the same topic.
- Added SQLite-backed thread message persistence plus `/api/threads/{thread_id}/messages` load/send APIs, so topic chats now reload with saved history instead of relying on browser-only session state.
- Replaced the always-visible topic action pills with a hover/focus topic-row shell and an overflow popup menu that contains `New chat`, `Settings`, and `Delete`, matching the reference-style sidebar interaction more closely.
- Added topic source listing/removal support in the settings modal, backed by a per-topic source manifest and delete API so current sources are visible and removable with an `x` control.
- Added removable queued-source pills in the create-topic modal so URLs and uploaded files can be removed before submitting the topic.
- Added manifest backfill for pre-existing topics so the settings modal can reconstruct current sources from old topic descriptions and on-disk source folders, including archived-repo handoffs such as `srsRAN_Project -> https://gitlab.com/ocudu/ocudu`.
- Normalized new-chat renaming to use the first user message as the saved thread title with collapsed whitespace.
- Moved topic readiness/error/indexing status from the thread cards into the topic header itself so status is shown once per topic instead of repeating on every thread row.
- Restored assistant-message refresh as a persisted backend action and changed assistant message controls to compact icon buttons for copy and refresh in the chat transcript.
- Tightened chat bubble sizing by preventing transcript row stretch, sizing message cards to content width, and trimming trailing assistant-message whitespace before render so bubbles do not show excess empty space.
- Moved assistant copy/refresh controls outside the chat bubble so the action row sits below the assistant card instead of consuming space inside the message body.
- Matched the reference transcript interaction more closely by hiding assistant action rows by default and revealing them only on assistant-message hover or focus-within.
- Removed the visible fill from assistant copy/refresh action buttons so the outside action row has no white background chip behind the icons.
- Removed the remaining copy/refresh button chrome and tightened the icon spacing so the outside action row reads as two plain inline icons instead of pill buttons.
- Added a hover-only background treatment for assistant copy/refresh icons so the controls stay plain by default and only show a white chip while hovered.
- Added a `Show graph` action to the topic overflow menu, backed by `/api/topics/{topic_id}/graph`, and a popup graph viewer that previews the saved Graphify or fallback graph with node/edge counts plus a lightweight SVG graph layout and node list.
- Added a regression test for graph preview loading and re-ran `node --check` on `chat.js`, `pytest` for `tests/test_graph_loader.py` and `tests/test_storage.py`, plus `python -m compileall src/qa_agent_app`.
- Fixed topic graph loading for older `ready` topics whose saved `graph_path` is stale or missing by rediscovering the latest on-disk `graph.json` or `fallback-graph.json` under the topic folder before returning the graph preview.
- Verified the graph endpoint live against the existing local `srsRAN` topic `srsran-6c2149b3`, which now returns HTTP 200 with a sampled preview from `data/topics/srsran-6c2149b3/fallback-graph.json` (`250` nodes, `248` edges), and added a regression test for the stale-path recovery helper.
- Reworked the graph popup layout into a taller graph-canvas plus scrollable inspector sidebar, and changed the graph preview from a monochrome radial plot to a clustered community-style SVG with vivid non-theme colors by node family, colored intra-community edges, neutral cross-community edges, and a community legend.
- Bumped the chat asset version after the graph-view UI refresh and re-ran `node --check` on `chat.js` plus `pytest tests/test_main_helpers.py -q`.
- Tightened the graph popup again by centering the modal better, widening the inspector sidebar, reducing noisy graph labels, shrinking node sizes, tightening community placement, and bumping the chat asset version again so the cleaned-up graph viewer replaces cached assets.
- Flattened the graph viewer further by replacing the remaining circular cluster anchor layout with wider horizontal community slots around the repository center, reducing label density again, shrinking the viewer height, and bumping the chat asset version to refresh the cleaner graph popup.
- Added post-layout graph normalization so the rendered communities are centered inside the canvas instead of sitting too high, and added label collision filtering so only non-overlapping high-priority node labels remain visible in the graph popup.
- Reduced graph-viewer height again so the inspector can show more node cards without clipping, added a light force-relaxation pass so community nodes spread more naturally instead of staying ring-stiff, and added node hover tooltips that show the full node name, family, and link count without permanently cluttering the graph.
- Changed the graph popup back to a fixed viewer where only the right inspector panel scrolls, and replaced the community highlight ellipses with bounds computed from the actual relaxed node positions so each community bubble wraps its own nodes more faithfully.
- Tightened the fixed graph viewer layout so the right inspector panel owns the scroll region more reliably, cut label noise further by limiting labels per community, and replaced dense non-repository ring placement with a softer sunflower distribution so large communities render less stiff and less cluttered.
- Removed the graph sidebar helper/guidance paragraph, switched the graph preview API back to full-node/full-edge responses by default instead of the old sampled cap, rendered the full node list in the right inspector, and bumped the graph viewer asset version again after re-running `node --check` and `pytest tests/test_graph_loader.py -q`.
- Replaced the remaining slot-based community positioning with a looser weighted-orbit layout plus jittered node seeding and longer force relaxation so the graph itself feels less templated and more like an organic graph-database view rather than a stiff fixed diagram.
- Cleaned the static graph view further by removing most permanent node labels in favor of repository-only labels plus hover tooltips, and made the graph panel zoomable/pannable with wheel zoom, drag-to-pan, and on-canvas zoom/reset controls.
- Matched the rendered SVG height to the graph stage so the graph canvas fills the full panel instead of leaving unused vertical space inside the viewer.
- Reduced graph noise further by removing the in-canvas community titles, lightening edge strokes, shrinking document-heavy nodes, and increasing dominant-cluster spread so full-node graph views read cleaner before zooming in.
- Increased dense-cluster separation further by raising document-family spread, same-family repulsion, and document seed radius while lowering document gravity, so large document-heavy graphs expand outward more instead of collapsing into a central overlap.

## 2026-06-11

- Expanded the Show graph layout canvas, increased graph node spacing/repulsion, added a final collision-separation pass, and bumped the chat asset version so dense graph nodes spread farther apart instead of collapsing together.
- Added a graph hub clearance pass and staggered repository labels so non-repository nodes are pushed out of the center instead of overlapping the central repository nodes.
- Strengthened the graph hub clearance by applying it after final canvas normalization and using a larger central exclusion radius, so center nodes are forced away from the repository hub in the rendered coordinates.
- Reworked the Show graph view toward a Graphify-like semantic map by removing large community ellipse overlays and rigid ring behavior while keeping a light canvas style.
- Fixed fallback graph file selection for code-heavy repositories by reserving most sampled nodes for source files, classifying `CMakeLists.txt` as config instead of document, and rebuilding the existing `srsran-6c2149b3` fallback graph so OCUDU code nodes appear in Show graph.
- Increased the fallback graph sampling cap from `240` to `400` files per repository and rebuilt the active `srsran-10a77f53` fallback graph so Show graph can include more document and config nodes without dropping code coverage.
- Removed the fallback graph file cap entirely and rebuilt the active `srsran-10a77f53` fallback graph; the remaining low document count is now due to fallback type classification (`32` OCUDU document files plus `8` `srsran-project` document files), not sampling limits.
- Reduced Show graph loading/render lag by sampling large fallback graphs for preview while preserving full total counts by type in the sidebar, limiting the rendered top-node list, and making node visuals shrink as zoom increases instead of ballooning.
- Switched Show graph back to full-node/full-edge fallback rendering, replaced the heavy SVG graph draw path with a canvas renderer, removed stacked window drag listeners, and made the large-graph layout use adaptive iterations plus spatial-bucket repulsion/collision passes so 5k+ node graphs load and pan more smoothly.
- Softened the Show graph zoom-size falloff so nodes and labels stay larger while zooming in, instead of shrinking too aggressively in dense graph areas.
- Increased the base Show graph node radii across repository, code, config, and document families so the graph reads larger overall even before zooming.
- Reduced the Show graph zoom step multipliers for both toolbar buttons and mouse wheel input so zooming in or out changes scale more gradually.
- Restored Show graph hover popup positioning to the mouse cursor while keeping the newer dense-graph hover hit-testing improvements.
- Tightened Show graph hover detection in dense areas by choosing the nearest node under the cursor instead of the first overlapping hit target, reducing wrong-node tooltips.
- Expanded the Show graph hover popup width cap and allowed long labels to wrap, then reverted the later cursor-centering tweak so positioning stays on the simpler mouse-offset behavior.
- Changed new topic creation so the initial per-topic thread is stored and shown as `New chat` instead of `Agent Chat`, and updated the storage regression test plus frontend thread selection logic to match.

## 2026-06-12

- Hardened SQLite cookie-session migrations further by tolerating duplicate `user_id` column adds on re-init, added idempotent re-open coverage, and live-verified `/chat`, `/api/topics`, and `/api/threads` return HTTP 200 against the current app database.
- Fixed cookie-scoped session rollout startup on older SQLite files by migrating legacy `topics`/`chat_threads` columns before creating `user_id` indexes, and added regression coverage for opening the chat page against pre-cookie databases.
- Added cookie-based user session recognition (`qa_agent_user`) and scoped topics, threads, messages, and saved LLM settings to that cookie so different browsers get isolated QA Agent workspaces against the same app database.
- Fixed the pending assistant loading bubble in chat by rendering it through the normal `message-shell` wrapper and forcing the loader dots to stay in a horizontal inline-flex row instead of stacking vertically.
- Fixed chat bubble sizing so user messages use the same shell-level max width as assistant messages, avoiding the overly narrow `fit-content` wrapping that made short user prompts break into stacked lines too early.
- Added the same hover/focus toolbar treatment to user chat bubbles, with `copy` and `edit` actions; edit restores the selected user message text into the composer for modification and resend.
- Changed user-message edit into an inline editor rendered in the same transcript position as the original user bubble, with `Cancel` and `Use text` actions so edits happen in place before optionally moving the result into the composer.
- Reworked chat edit/refresh into per-turn local version branches: editing a user turn or refreshing its assistant answer now adds a selectable version for that whole user/assistant pair, with previous/next controls and a shared version count shown in the message toolbars.
- Rendered assistant chat replies as formatted Markdown instead of raw escaped text, with client-side support for headings, emphasis, lists, code blocks, links, and simple pipe tables plus matching rich-text bubble styles.
- Polished assistant rich-text rendering by turning literal `<br>` tags into real line breaks, improving table presentation with a rounded container and less cramped columns, and bumping the chat asset versions so the browser refreshes the updated Markdown styles.
- Fixed broad graph-RAG project questions so repository/README context is prioritized over noisy config/code snippets while still passing the cleaned context through the configured LLM; deterministic repository summaries remain only as the local-provider fallback.
- Changed effective LLM settings resolution so explicit `.env` or environment variables take precedence over older SQLite-persisted LLM settings, preventing stale `local` provider rows from overriding OpenRouter config.
- Improved issue-oriented graph-RAG questions by normalizing simple plurals, boosting indexed `_github/issues.md` context, and making the local fallback extract the latest indexed GitHub issue instead of returning a broad project summary.
- Changed QA Agent chat topic creation so prompts containing source URLs now auto-detect and attach those sources, create the topic immediately, and start indexing without requiring a separate manual source step.
- Added an agent topic-draft backend path that uses the configured LLM to suggest a concise topic name from the prompt and detected sources, with deterministic URL-based fallback naming when no model is available.
- Added regression tests for source extraction, URL cleanup, and fallback topic naming, and bumped the chat asset version so browsers load the updated create-topic flow.
- Changed agent-created topics so the initial selected thread is titled `Topic chat` instead of `New chat`, while manual topic creation and extra threads still keep the `New chat` label.
- Fixed QA Agent composer state after agent-created topic handoff so the `Sending...` button does not stay stuck on the QA Agent session after the UI switches into the new topic thread.
- Added thread deletion support and changed agent-created temporary `Topic chat` threads to be removed automatically after indexing completes successfully.
- Moved temporary `Topic chat` cleanup into the backend ingestion success path as well, so the thread is deleted reliably when indexing finishes even if the frontend misses the client-side cleanup step.
- Added a top-right gear settings popup on the chat page for switching between `local` and `openrouter` and editing the same model fields used in `.env`.
- Changed LLM settings precedence so `.env` provides the default provider/model values, while values saved from the settings popup override those defaults for future chat requests, including user-supplied OpenRouter API keys.
- Added regression coverage for the new LLM settings precedence and bumped the chat asset version so browsers load the new settings UI.
- Added a real `Default (.env)` provider option in the settings popup, wired to backend default LLM settings, and moved the modal close button to the popup's top-right corner.
- Restyled the LLM settings popup theme, provider dropdown, and close button so the modal matches the app instead of the browser-default form controls.
- Rebalanced the LLM settings popup close `x` icon and changed the modal plus inner settings panels to a plain white background, then bumped the chat asset version again so the updated styling replaces cached CSS.
- Replaced the font-rendered LLM settings close `x` with a drawn cross icon in CSS so the close button stays visually centered across browsers.
- Applied a small rightward optical offset to the drawn LLM settings close icon so the `x` no longer reads slightly left of center inside the circle.
- Standardized all modal close buttons to the same top-right circular `x` control across create-topic, topic-settings, model-settings, and graph dialogs, and bumped the chat asset version so cached UI picks up the shared close-button pattern.
- Changed `Default (.env)` in model settings to be a true read-only default state: selecting it now clears the saved user override instead of persisting over the default, and the settings fields become disabled while that option is active.
- Increased the vertical gap between the home-page action buttons and the instruction cards below them so the CTA row does not feel crowded against the three setup steps.
- Added explicit top margin on the home-page instruction-card section itself, because button-only spacing was visually swallowed by the hero layout and did not create enough separation on screen.
- Increased the home-page instruction-card top margin again so the action buttons sit farther above the three setup cards.
- Replaced the home-page instruction-card top margin with real top padding so adjacent section margin-collapsing does not swallow the intended gap under the action buttons.
- Increased the spacing inside the home-page instruction cards between each step title and its descriptive text.
- Moved the extra home-page CTA-to-cards spacing onto the button row itself by increasing the action-row bottom margin, so the visible gap between the two buttons and the instruction cards is controlled directly.
- Reworked the home-page hero spacing at the section level by adding a consistent hero grid gap and bottom padding, so the button row and instruction cards have reliable separation without depending on child margins.
- Added a cache-busting query to the home-page stylesheet link and moved hero-to-cards spacing into a shared `home-flow` wrapper gap, so landing-page spacing updates apply reliably and are controlled at the section level.
- Compressed the home-page layout overall by reducing shell padding, hero top space, heading scale, section gap, and card padding so the landing content fits a typical desktop viewport without scrolling.
- Tightened the landing page further for desktop `100%` zoom by reducing hero and card sizing again, and made the desktop shell use the viewport height so the home page fits without a vertical scrollbar on large screens.
- Changed the desktop home page to a viewport-driven two-row flow with a shorter-height fallback, so the hero and the three instruction cards fit at `100%` zoom without relying on fixed vertical gaps.
- Reverted the viewport-driven desktop home-page fit attempt and restored the prior landing-page spacing after the forced no-scroll layout proved too aggressive.
- Relaxed the home-page compression slightly by enlarging the hero headline, descriptive copy, and cards again while keeping the lighter spacing model.
- Added Docker support with a Python slim `Dockerfile`, Docker Compose service, `.dockerignore`, persistent `/app/data` mapping, packaged static assets, and README instructions for containerized startup.
- Updated stale agent test fixtures to include the required `Topic.user_id` field so the existing suite passes with the current topic model.
- Added adaptive Graphify binary resolution via `GRAPHIFY_BIN=auto`, including PATH lookup, Windows user-site fallback, updated env examples, docs, and regression tests.
- Updated the Docker build to install the Graphify CLI from the `graphifyy` package with a build-time version argument.
- Made Docker Graphify installation the default verified path by checking `graphify --version` during image build and clarifying that plain `docker compose up --build` includes Graphify.
- Added a Docker entrypoint that prepares mounted `/app/data` permissions as root and then drops to `appuser`, fixing server deployments where topic creation failed with `PermissionError` on `/app/data/topics`.
- Added automatic Graphify no-key fallback from full semantic `extract` to code-only `update --no-cluster --force`, plus Docker Compose passthrough for common Graphify LLM provider API keys.
- Fixed graph preview loading for Graphify `links`-based `node_link` JSON under the newer NetworkX runtime by explicitly selecting the edge key when loading saved graphs.
