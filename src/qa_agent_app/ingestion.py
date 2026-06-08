import shutil
import subprocess
from pathlib import Path

from fastapi import UploadFile

from .graphify_client import GraphifyClient
from .github_collector import GitHubRepositoryCollector
from .models import IngestRequest, Topic
from .storage import TopicStore


class IngestionService:
    def __init__(
        self,
        topics_dir: Path,
        store: TopicStore,
        graphify: GraphifyClient,
        github_collector: GitHubRepositoryCollector | None = None,
    ):
        self.topics_dir = topics_dir
        self.store = store
        self.graphify = graphify
        self.github_collector = github_collector or GitHubRepositoryCollector()

    def topic_dir(self, topic_id: str) -> Path:
        return self.topics_dir / topic_id

    def ingest(self, topic: Topic, request: IngestRequest) -> Topic:
        topic_dir = self.topic_dir(topic.id)
        source_dir = topic_dir / "source"
        if source_dir.exists():
            shutil.rmtree(source_dir)
        source_dir.mkdir(parents=True, exist_ok=True)

        self.store.update_topic(topic.id, status="indexing", graph_path=None, last_error=None)
        try:
            if request.kind == "github":
                self._clone_repo(request.value, source_dir)
                self.github_collector.collect(request.value, source_dir)
            elif request.kind == "local_path":
                self._copy_local_path(Path(request.value), source_dir)
            else:
                raise ValueError("Upload ingestion must use the upload endpoint.")
            graph_path = self.graphify.build_graph(topic_dir, source_dir)
            return self.store.update_topic(
                topic.id,
                status="ready",
                graph_path=str(graph_path),
                last_error=None,
            )
        except Exception as exc:
            self.store.update_topic(topic.id, status="error", graph_path=None, last_error=str(exc))
            raise

    async def ingest_uploads(self, topic: Topic, files: list[UploadFile]) -> Topic:
        topic_dir = self.topic_dir(topic.id)
        source_dir = topic_dir / "source"
        if source_dir.exists():
            shutil.rmtree(source_dir)
        source_dir.mkdir(parents=True, exist_ok=True)
        self.store.update_topic(topic.id, status="indexing", graph_path=None, last_error=None)

        try:
            for upload in files:
                safe_name = Path(upload.filename or "document").name
                target = source_dir / safe_name
                with target.open("wb") as output:
                    while chunk := await upload.read(1024 * 1024):
                        output.write(chunk)
            graph_path = self.graphify.build_graph(topic_dir, source_dir)
            return self.store.update_topic(
                topic.id,
                status="ready",
                graph_path=str(graph_path),
                last_error=None,
            )
        except Exception as exc:
            self.store.update_topic(topic.id, status="error", graph_path=None, last_error=str(exc))
            raise

    @staticmethod
    def _clone_repo(url: str, target: Path) -> None:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(target)],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"git clone failed: {detail}")

    @staticmethod
    def _copy_local_path(source: Path, target: Path) -> None:
        if not source.exists():
            raise FileNotFoundError(source)
        if source.is_dir():
            for child in source.iterdir():
                destination = target / child.name
                if child.is_dir():
                    shutil.copytree(child, destination, ignore=shutil.ignore_patterns(".git", "__pycache__"))
                else:
                    shutil.copy2(child, destination)
        else:
            shutil.copy2(source, target / source.name)
