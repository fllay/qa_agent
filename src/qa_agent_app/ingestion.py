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
        source_dir = self._ensure_source_dir(topic_dir)

        self._set_progress(topic.id, 5, "Preparing source", graph_path=None, last_error=None)
        try:
            self.graphify.ensure_available()
            self._set_progress(topic.id, 12, "Checking Graphify")
            if request.kind == "github":
                self._set_progress(topic.id, 22, "Cloning repository")
                repo_dir = self._unique_path(source_dir, self._slug_name(Path(request.value).stem or "github-repo"))
                self._clone_repo(request.value, repo_dir)
                self._set_progress(topic.id, 30, "Collecting GitHub context")
                self.github_collector.collect(
                    request.value,
                    repo_dir,
                    progress=lambda index, total, label: self._set_progress(
                        topic.id,
                        30 + int((index / total) * 45),
                        label,
                    ),
                )
            elif request.kind == "local_path":
                self._set_progress(topic.id, 35, "Copying local source")
                source_path = Path(request.value)
                target_dir = self._unique_path(source_dir, source_path.stem or source_path.name or "local-source")
                self._copy_local_path(source_path, target_dir)
            else:
                raise ValueError("Upload ingestion must use the upload endpoint.")
            self._set_progress(topic.id, 82, "Building graph")
            graph_path = self.graphify.build_graph(topic_dir, source_dir)
            self._set_progress(topic.id, 96, "Finalizing graph")
            return self.store.update_topic(
                topic.id,
                status="ready",
                progress_percent=100,
                progress_label="Ready",
                graph_path=str(graph_path),
                last_error=None,
            )
        except Exception as exc:
            self.store.update_topic(
                topic.id,
                status="error",
                progress_percent=0,
                progress_label="Failed",
                graph_path=None,
                last_error=str(exc),
            )
            raise

    async def ingest_uploads(self, topic: Topic, files: list[UploadFile]) -> Topic:
        topic_dir = self.topic_dir(topic.id)
        source_dir = self._ensure_source_dir(topic_dir)
        self._set_progress(topic.id, 5, "Preparing upload", graph_path=None, last_error=None)

        try:
            self.graphify.ensure_available()
            total_files = max(len(files), 1)
            for index, upload in enumerate(files, start=1):
                safe_name = Path(upload.filename or "document").name
                target = self._unique_path(source_dir, safe_name)
                with target.open("wb") as output:
                    while chunk := await upload.read(1024 * 1024):
                        output.write(chunk)
                self._set_progress(topic.id, 15 + int((index / total_files) * 55), f"Uploaded {safe_name}")
            self._set_progress(topic.id, 82, "Building graph")
            graph_path = self.graphify.build_graph(topic_dir, source_dir)
            self._set_progress(topic.id, 96, "Finalizing graph")
            return self.store.update_topic(
                topic.id,
                status="ready",
                progress_percent=100,
                progress_label="Ready",
                graph_path=str(graph_path),
                last_error=None,
            )
        except Exception as exc:
            self.store.update_topic(
                topic.id,
                status="error",
                progress_percent=0,
                progress_label="Failed",
                graph_path=None,
                last_error=str(exc),
            )
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
        git_dir = target / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir, ignore_errors=True)

    @staticmethod
    def _copy_local_path(source: Path, target: Path) -> None:
        if not source.exists():
            raise FileNotFoundError(source)
        target.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            for child in source.iterdir():
                destination = target / child.name
                if child.is_dir():
                    shutil.copytree(child, destination, ignore=shutil.ignore_patterns(".git", "__pycache__"))
                else:
                    shutil.copy2(child, destination)
        else:
            shutil.copy2(source, target / source.name)

    @staticmethod
    def _ensure_source_dir(topic_dir: Path) -> Path:
        source_dir = topic_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        return source_dir

    @staticmethod
    def _slug_name(value: str) -> str:
        clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
        return "-".join(part for part in clean.split("-") if part) or "source"

    @classmethod
    def _unique_path(cls, parent: Path, name: str) -> Path:
        candidate = parent / name
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        counter = 2
        while True:
            next_candidate = parent / f"{stem}-{counter}{suffix}"
            if not next_candidate.exists():
                return next_candidate
            counter += 1

    def _set_progress(
        self,
        topic_id: str,
        percent: int,
        label: str,
        *,
        graph_path: str | None = None,
        last_error: str | None = None,
    ) -> Topic:
        return self.store.update_topic(
            topic_id,
            status="indexing",
            progress_percent=max(0, min(99, percent)),
            progress_label=label,
            graph_path=graph_path,
            last_error=last_error,
        )
