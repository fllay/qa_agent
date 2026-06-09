import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

from qa_agent_app.ingestion import IngestionService
from qa_agent_app.models import IngestRequest, TopicCreate
from qa_agent_app.storage import TopicStore


class DummyGraphifyClient:
    def ensure_available(self) -> None:
        return None

    def build_graph(self, topic_dir: Path, source_dir: Path) -> Path:
        graph_path = topic_dir / "graph.json"
        graph_path.write_text(f"graph built from {source_dir}", encoding="utf-8")
        return graph_path


class DummyGitHubCollector:
    def collect(self, repo_url: str, target_dir: Path) -> None:
        (target_dir / "_github_collected.txt").write_text(repo_url, encoding="utf-8")


def test_ingestion_appends_sources(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="Docs"))
    service = IngestionService(tmp_path / "topics", store, DummyGraphifyClient(), DummyGitHubCollector())

    local_source = tmp_path / "billing-api"
    local_source.mkdir()
    (local_source / "README.md").write_text("hello", encoding="utf-8")

    updated = service.ingest(topic, IngestRequest(kind="local_path", value=str(local_source)))
    upload = UploadFile(filename="notes.txt", file=BytesIO(b"extra"))
    updated = asyncio.run(service.ingest_uploads(updated, [upload]))

    source_dir = tmp_path / "topics" / topic.id / "source"
    assert (source_dir / "billing-api" / "README.md").exists()
    assert (source_dir / "notes.txt").exists()
    assert updated.status == "ready"
    assert (tmp_path / "topics" / topic.id / "graph.json").exists()
