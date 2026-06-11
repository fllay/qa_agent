import os
import shutil
import stat
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agent import QaAgent
from .config import Settings, get_settings
from .graph_loader import graph_preview_limits, load_graph_preview
from .graphify_client import GraphifyClient
from .github_collector import GitHubRepositoryCollector
from .ingestion import IngestionService
from .models import (
    ChatMessage,
    ChatThread,
    IngestRequest,
    IngestResult,
    LlmSettings,
    QuestionRequest,
    QuestionResponse,
    ThreadMessageCreate,
    ThreadMessageResponse,
    ThreadCreate,
    Topic,
    TopicCreate,
    TopicGraphResponse,
    TopicSource,
)
from .storage import TopicStore

app = FastAPI(title="QA Agent", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _resolve_topic_graph_path(topic: Topic, topics_dir: Path) -> Path | None:
    topic_dir = topics_dir / topic.id
    candidates: list[Path] = []

    if topic.graph_path:
        saved = Path(topic.graph_path)
        if not saved.is_absolute():
            saved = (topic_dir / saved).resolve()
        candidates.append(saved)

    if topic_dir.exists():
        candidates.extend(topic_dir.rglob("graph.json"))
        fallback = topic_dir / "fallback-graph.json"
        if fallback.exists():
            candidates.append(fallback)

    existing = [path for path in candidates if path.exists() and path.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def get_store(settings: Settings = Depends(get_settings)) -> TopicStore:
    return TopicStore(settings.database_path)


def _handle_remove_readonly(func, path, excinfo) -> None:
    # Git-created pack files can be read-only on Windows; clear the bit and retry.
    if isinstance(excinfo, BaseException):
        error = excinfo
    else:
        error = excinfo[1]
    if not isinstance(error, PermissionError):
        raise error
    os.chmod(path, stat.S_IWRITE)
    func(path)


def get_ingestion(
    settings: Settings = Depends(get_settings),
    store: TopicStore = Depends(get_store),
) -> IngestionService:
    graphify = GraphifyClient(settings.graphify_bin, settings.graphify_timeout_seconds)
    github_collector = GitHubRepositoryCollector(
        token=settings.github_token,
        max_pages=settings.github_max_pages,
        per_page=settings.github_per_page,
    )
    return IngestionService(settings.topics_dir, store, graphify, github_collector)


def default_llm_settings(settings: Settings) -> LlmSettings:
    provider = settings.llm_provider.lower()
    if provider not in {"local", "openrouter"}:
        provider = "local"
    return LlmSettings(
        provider=provider,
        local_base_url=settings.local_llm_base_url,
        local_api_key=settings.local_llm_api_key,
        local_model=settings.local_llm_model,
        openrouter_api_key=settings.openrouter_api_key or "",
        openrouter_base_url=settings.openrouter_base_url,
        openrouter_main_model=settings.openrouter_main_model,
        openrouter_reserve_model_1=settings.openrouter_reserve_model_1,
        openrouter_reserve_model_2=settings.openrouter_reserve_model_2,
    )


def get_agent(
    settings: Settings = Depends(get_settings),
    store: TopicStore = Depends(get_store),
) -> QaAgent:
    llm = store.get_llm_settings(default_llm_settings(settings))
    return QaAgent(
        llm.provider,
        local_base_url=llm.local_base_url,
        local_api_key=llm.local_api_key,
        local_model=llm.local_model,
        openrouter_api_key=llm.openrouter_api_key,
        openrouter_base_url=llm.openrouter_base_url,
        openrouter_main_model=llm.openrouter_main_model,
        openrouter_reserve_model_1=llm.openrouter_reserve_model_1,
        openrouter_reserve_model_2=llm.openrouter_reserve_model_2,
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/chat")
def chat() -> FileResponse:
    return FileResponse(STATIC_DIR / "chat.html")


@app.get("/api/topics", response_model=list[Topic])
def list_topics(store: TopicStore = Depends(get_store)) -> list[Topic]:
    return store.list_topics()


@app.get("/api/llm-settings", response_model=LlmSettings)
def get_llm_settings(
    settings: Settings = Depends(get_settings),
    store: TopicStore = Depends(get_store),
) -> LlmSettings:
    return store.get_llm_settings(default_llm_settings(settings))


@app.put("/api/llm-settings", response_model=LlmSettings)
def update_llm_settings(payload: LlmSettings, store: TopicStore = Depends(get_store)) -> LlmSettings:
    return store.update_llm_settings(payload)


@app.post("/api/topics", response_model=Topic)
def create_topic(payload: TopicCreate, store: TopicStore = Depends(get_store)) -> Topic:
    return store.create_topic(payload)


@app.get("/api/threads", response_model=list[ChatThread])
def list_threads(topic_id: str | None = None, store: TopicStore = Depends(get_store)) -> list[ChatThread]:
    return store.list_threads(topic_id)


@app.get("/api/threads/{thread_id}/messages", response_model=list[ChatMessage])
def list_thread_messages(thread_id: str, store: TopicStore = Depends(get_store)) -> list[ChatMessage]:
    try:
        return store.list_messages(thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Thread not found") from exc


@app.post("/api/topics/{topic_id}/threads", response_model=ChatThread)
def create_thread(topic_id: str, payload: ThreadCreate, store: TopicStore = Depends(get_store)) -> ChatThread:
    try:
        return store.create_thread(topic_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Topic not found") from exc


@app.post("/api/threads/{thread_id}/messages", response_model=ThreadMessageResponse)
def create_thread_message(
    thread_id: str,
    payload: ThreadMessageCreate,
    store: TopicStore = Depends(get_store),
    agent: QaAgent = Depends(get_agent),
) -> ThreadMessageResponse:
    try:
        thread = store.get_thread(thread_id)
        topic = store.get_topic(thread.topic_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Thread not found") from exc

    user_message = store.append_message(thread_id, "user", payload.text)
    if thread.title.strip().lower() == "new chat":
        trimmed_title = " ".join(payload.text.strip().split())
        store.rename_thread(thread_id, trimmed_title[:80] or "New chat")

    try:
        response = agent.answer(topic, payload.text, payload.max_context_items)
    except Exception as exc:
        assistant_message = store.append_message(thread_id, "agent", str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    assistant_message = store.append_message(thread_id, "agent", response.answer)
    return ThreadMessageResponse(
        thread_id=thread_id,
        topic_id=thread.topic_id,
        user_message=user_message,
        assistant_message=assistant_message,
        citations=response.citations,
        context_items=response.context_items,
    )


@app.post("/api/threads/{thread_id}/messages/{message_id}/refresh", response_model=ChatMessage)
def refresh_thread_message(
    thread_id: str,
    message_id: str,
    payload: ThreadMessageCreate,
    store: TopicStore = Depends(get_store),
    agent: QaAgent = Depends(get_agent),
) -> ChatMessage:
    try:
        thread = store.get_thread(thread_id)
        topic = store.get_topic(thread.topic_id)
        messages = store.list_messages(thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Thread not found") from exc

    target_index = next((index for index, item in enumerate(messages) if item.id == message_id), None)
    if target_index is None:
        raise HTTPException(status_code=404, detail="Message not found")

    target_message = messages[target_index]
    if target_message.role != "agent":
        raise HTTPException(status_code=400, detail="Only assistant messages can be refreshed")

    prior_user = next((item for item in reversed(messages[:target_index]) if item.role == "user"), None)
    if prior_user is None:
        raise HTTPException(status_code=400, detail="No user message found for refresh")

    try:
        response = agent.answer(topic, prior_user.text, payload.max_context_items)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return store.update_message_text(message_id, response.answer)


@app.get("/api/topics/{topic_id}", response_model=Topic)
def get_topic(topic_id: str, store: TopicStore = Depends(get_store)) -> Topic:
    try:
        return store.get_topic(topic_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Topic not found") from exc


@app.get("/api/topics/{topic_id}/sources", response_model=list[TopicSource])
def list_topic_sources(
    topic_id: str,
    store: TopicStore = Depends(get_store),
    ingestion: IngestionService = Depends(get_ingestion),
) -> list[TopicSource]:
    try:
        topic = store.get_topic(topic_id)
        return ingestion.list_sources(topic)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Topic not found") from exc


@app.get("/api/topics/{topic_id}/graph", response_model=TopicGraphResponse)
def get_topic_graph(
    topic_id: str,
    settings: Settings = Depends(get_settings),
    store: TopicStore = Depends(get_store),
) -> TopicGraphResponse:
    try:
        topic = store.get_topic(topic_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Topic not found") from exc

    graph_path = _resolve_topic_graph_path(topic, settings.topics_dir)
    if graph_path is None:
        raise HTTPException(status_code=404, detail="Saved graph file was not found for this topic.")

    try:
        max_nodes, max_edges = graph_preview_limits(graph_path)
        return load_graph_preview(topic.id, topic.name, graph_path, max_nodes=max_nodes, max_edges=max_edges)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not load the saved graph: {exc}") from exc


@app.delete("/api/topics/{topic_id}/sources/{source_id}", response_model=Topic)
def delete_topic_source(
    topic_id: str,
    source_id: str,
    store: TopicStore = Depends(get_store),
    ingestion: IngestionService = Depends(get_ingestion),
) -> Topic:
    try:
        topic = store.get_topic(topic_id)
        return ingestion.remove_source(topic, source_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Source not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/topics/{topic_id}", status_code=204)
def delete_topic(
    topic_id: str,
    store: TopicStore = Depends(get_store),
    ingestion: IngestionService = Depends(get_ingestion),
) -> None:
    try:
        store.get_topic(topic_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Topic not found") from exc
    store.delete_topic(topic_id)
    topic_dir = ingestion.topic_dir(topic_id)
    if topic_dir.exists():
        shutil.rmtree(topic_dir, onexc=_handle_remove_readonly)


@app.post("/api/topics/{topic_id}/ingest", response_model=IngestResult)
def ingest_topic(
    topic_id: str,
    payload: IngestRequest,
    store: TopicStore = Depends(get_store),
    ingestion: IngestionService = Depends(get_ingestion),
) -> IngestResult:
    try:
        topic = store.get_topic(topic_id)
        updated = ingestion.ingest(topic, payload)
        return IngestResult(topic=updated, message="Ingestion complete.")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Topic not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/topics/{topic_id}/upload", response_model=IngestResult)
async def upload_topic_files(
    topic_id: str,
    files: list[UploadFile] = File(...),
    store: TopicStore = Depends(get_store),
    ingestion: IngestionService = Depends(get_ingestion),
) -> IngestResult:
    try:
        topic = store.get_topic(topic_id)
        updated = await ingestion.ingest_uploads(topic, files)
        return IngestResult(topic=updated, message="Upload ingestion complete.")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Topic not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/topics/{topic_id}/ask", response_model=QuestionResponse)
def ask_question(
    topic_id: str,
    payload: QuestionRequest,
    store: TopicStore = Depends(get_store),
    agent: QaAgent = Depends(get_agent),
) -> QuestionResponse:
    try:
        topic = store.get_topic(topic_id)
        return agent.answer(topic, payload.question, payload.max_context_items)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Topic not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
