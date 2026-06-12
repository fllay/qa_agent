import asyncio
from io import BytesIO
from pathlib import Path
import subprocess

from fastapi import UploadFile

from qa_agent_app.ingestion import IngestionService
from qa_agent_app.models import IngestRequest, TopicCreate
from qa_agent_app.storage import TopicStore
from qa_agent_app.graphify_client import GraphifyError


class DummyGraphifyClient:
    def ensure_available(self) -> None:
        return None

    def build_graph(self, topic_dir: Path, source_dir: Path) -> Path:
        graph_path = topic_dir / "graph.json"
        graph_path.write_text(f"graph built from {source_dir}", encoding="utf-8")
        return graph_path


class DummyGitHubCollector:
    def collect(self, repo_url: str, target_dir: Path, progress=None) -> None:
        (target_dir / "_github_collected.txt").write_text(repo_url, encoding="utf-8")


class EmptyGraphGraphifyClient:
    def ensure_available(self) -> None:
        return None

    def build_graph(self, topic_dir: Path, source_dir: Path) -> Path:
        raise GraphifyError(
            "Graphify completed but produced an empty graph. "
            "This source may not contain analyzable code or may only contain metadata/README files."
        )


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


def test_ingestion_ready_cleanup_removes_temporary_topic_chat_thread(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="Docs", initial_thread_title="Topic chat"))
    service = IngestionService(tmp_path / "topics", store, DummyGraphifyClient(), DummyGitHubCollector())

    local_source = tmp_path / "repo"
    local_source.mkdir()
    (local_source / "README.md").write_text("hello", encoding="utf-8")

    updated = service.ingest(topic, IngestRequest(kind="local_path", value=str(local_source)))

    assert updated.status == "ready"
    assert store.list_threads(topic.id) == []


def test_detect_archived_repo_replacement(tmp_path):
    repo_dir = tmp_path / "topics" / "topic" / "source" / "srsran-project"
    repo_dir.mkdir(parents=True)
    (repo_dir / "README.md").write_text(
        (
            "> Project transition notice: srsRAN Project is now OCUDU. "
            "As of December 2025, all development has transitioned to the new "
            "repository https://gitlab.com/ocudu/ocudu. "
            "This repository will be archived and is no longer maintained."
        ),
        encoding="utf-8",
    )
    assert IngestionService._detect_repository_replacement(repo_dir) == "https://gitlab.com/ocudu/ocudu"


def test_ingestion_follows_archived_repo_replacement_before_graph_build(tmp_path, monkeypatch):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="srsRAN"))
    service = IngestionService(tmp_path / "topics", store, DummyGraphifyClient(), DummyGitHubCollector())

    cloned_urls: list[str] = []

    def fake_clone(url: str, target: Path) -> None:
        cloned_urls.append(url)
        target.mkdir(parents=True, exist_ok=True)
        if "github.com" in url:
            (target / "README.md").write_text(
                (
                    "> Project transition notice: srsRAN Project is now OCUDU. "
                    "As of December 2025, all development has transitioned to the new "
                    "repository https://gitlab.com/ocudu/ocudu. "
                    "This repository will be archived and is no longer maintained."
                ),
                encoding="utf-8",
            )
        else:
            (target / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

    monkeypatch.setattr(IngestionService, "_clone_repo", staticmethod(fake_clone))

    updated = service.ingest(topic, IngestRequest(kind="github", value="https://github.com/srsran/srsRAN_Project"))

    assert cloned_urls == [
        "https://github.com/srsran/srsRAN_Project",
        "https://gitlab.com/ocudu/ocudu",
    ]
    assert updated.status == "ready"


def test_empty_graph_uses_fallback_graph(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="Docs"))
    service = IngestionService(tmp_path / "topics", store, EmptyGraphGraphifyClient(), DummyGitHubCollector())

    repo_dir = tmp_path / "topics" / topic.id / "source" / "repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / "README.md").write_text("# Demo Repo\n\nRepository overview", encoding="utf-8")
    (repo_dir / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

    graph_path = service._build_graph_with_diagnostics(tmp_path / "topics" / topic.id, tmp_path / "topics" / topic.id / "source")

    assert graph_path.name == "fallback-graph.json"
    assert graph_path.exists()


def test_normalize_gitlab_clone_url():
    assert IngestionService._normalize_clone_url("https://gitlab.com/ocudu/ocudu") == "https://gitlab.com/ocudu/ocudu.git"
    assert IngestionService._normalize_clone_url("https://gitlab.com/ocudu/ocudu/") == "https://gitlab.com/ocudu/ocudu.git"
    assert IngestionService._normalize_clone_url("https://gitlab.com/ocudu/ocudu.git") == "https://gitlab.com/ocudu/ocudu.git"
    assert IngestionService._normalize_clone_url("https://github.com/srsran/srsRAN_Project") == "https://github.com/srsran/srsRAN_Project"


def test_clone_repo_recovers_checkout_failure(monkeypatch, tmp_path):
    target = tmp_path / "ocudu"
    calls: list[list[str]] = []

    def fake_run_git(command: list[str]):
        calls.append(command)
        if "clone" in command:
            (target / ".git").mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(
                command,
                128,
                "",
                "warning: Clone succeeded, but checkout failed.",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(IngestionService, "_run_git_command", staticmethod(fake_run_git))
    IngestionService._clone_repo("https://gitlab.com/ocudu/ocudu", target)

    assert len(calls) == 2
    assert calls[0][:4] == ["git", "-c", "core.longpaths=true", "clone"]
    assert calls[1][:3] == ["git", "-C", str(target.resolve())]
