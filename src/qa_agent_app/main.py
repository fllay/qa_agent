from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agent import QaAgent
from .config import Settings, get_settings
from .graphify_client import GraphifyClient
from .github_collector import GitHubRepositoryCollector
from .ingestion import IngestionService
from .models import IngestRequest, IngestResult, LlmSettings, QuestionRequest, QuestionResponse, Topic, TopicCreate
from .storage import TopicStore

app = FastAPI(title="QA Agent", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_store(settings: Settings = Depends(get_settings)) -> TopicStore:
    return TopicStore(settings.database_path)


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


@app.get("/api/topics/{topic_id}", response_model=Topic)
def get_topic(topic_id: str, store: TopicStore = Depends(get_store)) -> Topic:
    try:
        return store.get_topic(topic_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Topic not found") from exc


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
        import shutil

        shutil.rmtree(topic_dir)


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
