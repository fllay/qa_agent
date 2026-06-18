import shutil
import subprocess
import re
import json
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from fastapi import UploadFile

from .fallback_graph import build_fallback_graph
from .graphify_client import GraphifyClient, GraphifyError
from .github_collector import GitHubRepositoryCollector
from .models import IngestRequest, Topic, TopicSource
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

    def list_sources(self, topic: Topic) -> list[TopicSource]:
        topic_dir = self.topic_dir(topic.id)
        source_dir = self._ensure_source_dir(topic_dir)
        manifest = self._load_manifest(topic_dir)
        if not manifest:
            manifest = self._bootstrap_manifest(topic, topic_dir, source_dir)
        results: list[TopicSource] = []
        valid_entries: list[dict] = []

        for entry in manifest:
            source_path = source_dir / entry["path"]
            if source_path.exists():
                valid_entries.append(entry)
                results.append(
                    TopicSource(
                        id=entry["id"],
                        kind=entry["kind"],
                        label=entry["label"],
                        value=entry["value"],
                    )
                )

        if len(valid_entries) != len(manifest):
            self._save_manifest(topic_dir, valid_entries)
        return results

    def remove_source(self, topic: Topic, source_id: str) -> Topic:
        topic_dir = self.topic_dir(topic.id)
        source_dir = self._ensure_source_dir(topic_dir)
        manifest = self._load_manifest(topic_dir)
        remaining = []
        target = None
        for entry in manifest:
            if entry["id"] == source_id:
                target = entry
            else:
                remaining.append(entry)
        if target is None:
            raise KeyError(source_id)

        source_path = source_dir / target["path"]
        if source_path.exists():
            if source_path.is_dir():
                shutil.rmtree(source_path, ignore_errors=True)
            else:
                source_path.unlink(missing_ok=True)
        self._save_manifest(topic_dir, remaining)
        self.store.update_topic_description(
            topic.id,
            "\n".join(entry["value"] for entry in remaining if entry["kind"] != "upload"),
            user_id=topic.user_id,
        )

        if any(source_dir.iterdir()):
            graph_path = self._build_graph_with_diagnostics(topic_dir, source_dir)
            return self.store.update_topic(
                topic.id,
                user_id=topic.user_id,
                status="ready",
                progress_percent=100,
                progress_label="Ready",
                graph_path=str(graph_path),
                last_error=None,
            )
        return self.store.update_topic(
            topic.id,
            user_id=topic.user_id,
            status="new",
            progress_percent=0,
            progress_label="",
            graph_path=None,
            last_error=None,
        )

    def ingest(self, topic: Topic, request: IngestRequest) -> Topic:
        topic_dir = self.topic_dir(topic.id)
        source_dir = self._ensure_source_dir(topic_dir)

        self._set_progress(topic.id, topic.user_id, 5, "Preparing source", graph_path=None, last_error=None)
        try:
            self.graphify.ensure_available()
            self._set_progress(topic.id, topic.user_id, 12, "Checking Graphify")
            if request.kind == "github":
                self._set_progress(topic.id, topic.user_id, 22, "Cloning repository")
                repo_dir = self._unique_path(source_dir, self._slug_name(Path(request.value).stem or "github-repo"))
                self._clone_repo(request.value, repo_dir)
                self._register_source(topic_dir, "github", request.value, request.value, repo_dir.relative_to(source_dir).as_posix())
                self._set_progress(topic.id, topic.user_id, 30, "Collecting GitHub context")
                self.github_collector.collect(
                    request.value,
                    repo_dir,
                    progress=lambda index, total, label: self._set_progress(
                        topic.id,
                        topic.user_id,
                        30 + int((index / total) * 45),
                        label,
                    ),
                )
                replacement_url = self._detect_repository_replacement(repo_dir)
                if replacement_url:
                    self._set_progress(topic.id, topic.user_id, 76, "Following active repository")
                    replacement_dir = self._unique_path(
                        source_dir,
                        self._slug_name(Path(replacement_url).stem or "active-repo"),
                    )
                    self._clone_repo(replacement_url, replacement_dir)
                    self._register_source(
                        topic_dir,
                        "github",
                        replacement_url,
                        replacement_url,
                        replacement_dir.relative_to(source_dir).as_posix(),
                    )
            elif request.kind == "local_path":
                self._set_progress(topic.id, topic.user_id, 35, "Copying local source")
                source_path = Path(request.value)
                target_dir = self._unique_path(source_dir, source_path.stem or source_path.name or "local-source")
                self._copy_local_path(source_path, target_dir)
                self._register_source(
                    topic_dir,
                    "local_path",
                    source_path.name,
                    request.value,
                    target_dir.relative_to(source_dir).as_posix(),
                )
            else:
                raise ValueError("Upload ingestion must use the upload endpoint.")
            self._sync_topic_description(topic.id, topic_dir, topic.user_id)
            self._set_progress(topic.id, topic.user_id, 82, "Building graph")
            graph_path = self._build_graph_with_diagnostics(topic_dir, source_dir)
            self._set_progress(topic.id, topic.user_id, 96, "Finalizing graph", graph_path=str(graph_path))
            updated = self.store.update_topic(
                topic.id,
                user_id=topic.user_id,
                status="ready",
                progress_percent=100,
                progress_label="Ready",
                graph_path=str(graph_path),
                last_error=None,
            )
            self.store.delete_threads_by_title(topic.id, "Topic chat", user_id=topic.user_id)
            return updated
        except Exception as exc:
            self.store.update_topic(
                topic.id,
                user_id=topic.user_id,
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
        self._set_progress(topic.id, topic.user_id, 5, "Preparing upload", graph_path=None, last_error=None)

        try:
            self.graphify.ensure_available()
            total_files = max(len(files), 1)
            for index, upload in enumerate(files, start=1):
                safe_name = Path(upload.filename or "document").name
                target = self._unique_path(source_dir, safe_name)
                with target.open("wb") as output:
                    while chunk := await upload.read(1024 * 1024):
                        output.write(chunk)
                self._register_source(
                    topic_dir,
                    "upload",
                    safe_name,
                    safe_name,
                    target.relative_to(source_dir).as_posix(),
                )
                self._set_progress(topic.id, topic.user_id, 15 + int((index / total_files) * 55), f"Uploaded {safe_name}")
            self._sync_topic_description(topic.id, topic_dir, topic.user_id)
            self._set_progress(topic.id, topic.user_id, 82, "Building graph")
            graph_path = self._build_graph_with_diagnostics(topic_dir, source_dir)
            self._set_progress(topic.id, topic.user_id, 96, "Finalizing graph", graph_path=str(graph_path))
            updated = self.store.update_topic(
                topic.id,
                user_id=topic.user_id,
                status="ready",
                progress_percent=100,
                progress_label="Ready",
                graph_path=str(graph_path),
                last_error=None,
            )
            self.store.delete_threads_by_title(topic.id, "Topic chat", user_id=topic.user_id)
            return updated
        except Exception as exc:
            self.store.update_topic(
                topic.id,
                user_id=topic.user_id,
                status="error",
                progress_percent=0,
                progress_label="Failed",
                graph_path=None,
                last_error=str(exc),
            )
            raise

    @staticmethod
    def _clone_repo(url: str, target: Path) -> None:
        normalized_url = IngestionService._normalize_clone_url(url)
        target = target.resolve()
        result = IngestionService._run_git_command(
            ["git", "-c", "core.longpaths=true", "clone", "--depth", "1", normalized_url, str(target)]
        )
        if result.returncode != 0 and "Clone succeeded, but checkout failed." in (result.stderr or "") and (target / ".git").exists():
            recovery = IngestionService._run_git_command(
                ["git", "-C", str(target), "-c", "core.longpaths=true", "checkout", "-f", "HEAD"]
            )
            if recovery.returncode == 0:
                result = recovery
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"git clone failed: {detail}")
        git_dir = target / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir, ignore_errors=True)

    @staticmethod
    def _run_git_command(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    def _normalize_clone_url(url: str) -> str:
        parsed = urlsplit(url.strip())
        if parsed.scheme in {"http", "https"} and "gitlab.com" in parsed.netloc.lower():
            path = parsed.path.rstrip("/")
            if path and not path.endswith(".git"):
                path = f"{path}.git"
            return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))
        return url

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
        user_id: str,
        percent: int,
        label: str,
        *,
        graph_path: str | None = None,
        last_error: str | None = None,
    ) -> Topic:
        return self.store.update_topic(
            topic_id,
            user_id=user_id,
            status="indexing",
            progress_percent=max(0, min(99, percent)),
            progress_label=label,
            graph_path=graph_path,
            last_error=last_error,
        )

    def _build_graph_with_diagnostics(self, topic_dir: Path, source_dir: Path) -> Path:
        try:
            return self.graphify.build_graph(topic_dir, source_dir)
        except GraphifyError as exc:
            error_text = str(exc)
            if (
                "Graphify completed but produced an empty graph" in error_text
                or "Graphify timed out after" in error_text
            ):
                return build_fallback_graph(topic_dir, source_dir)
            diagnosis = self._diagnose_empty_graph_source(source_dir, error_text)
            if diagnosis:
                raise RuntimeError(diagnosis) from exc
            raise

    @classmethod
    def _diagnose_empty_graph_source(cls, source_dir: Path, error_text: str) -> str | None:
        if "Graphify completed but produced an empty graph" not in error_text:
            return None

        repo_hint = cls._diagnose_archived_repository(source_dir)
        if repo_hint:
            return repo_hint
        return None

    @staticmethod
    def _manifest_path(topic_dir: Path) -> Path:
        return topic_dir / "sources.json"

    def _load_manifest(self, topic_dir: Path) -> list[dict]:
        path = self._manifest_path(topic_dir)
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def _save_manifest(self, topic_dir: Path, entries: list[dict]) -> None:
        self._manifest_path(topic_dir).write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def _manifest_entry(self, kind: str, label: str, value: str, relative_path: str) -> dict:
        return {
            "id": uuid.uuid4().hex[:12],
            "kind": kind,
            "label": label,
            "value": value,
            "path": relative_path,
        }

    def _bootstrap_manifest(self, topic: Topic, topic_dir: Path, source_dir: Path) -> list[dict]:
        entries: list[dict] = []
        remaining: dict[str, Path] = {child.name: child for child in source_dir.iterdir()} if source_dir.exists() else {}
        description_values = [line.strip() for line in topic.description.splitlines() if line.strip()]
        replacement_urls = []
        for child in remaining.values():
            if child.is_dir():
                replacement_url = self._detect_repository_replacement(child)
                if replacement_url:
                    replacement_urls.append(replacement_url)

        for value in description_values:
            matched = self._match_existing_source_path(value, remaining)
            if matched is None:
                continue
            entries.append(self._manifest_entry("github", value, value, matched.name))
            remaining.pop(matched.name, None)

        for replacement_url in replacement_urls:
            matched = self._match_existing_source_path(replacement_url, remaining)
            if matched is None:
                continue
            entries.append(self._manifest_entry("github", replacement_url, replacement_url, matched.name))
            remaining.pop(matched.name, None)

        for child in remaining.values():
            if child.is_dir():
                replacement_url = self._detect_repository_replacement(child)
                if replacement_url:
                    entries.append(self._manifest_entry("github", replacement_url, replacement_url, child.name))
                else:
                    entries.append(self._manifest_entry("local_path", child.name, child.name, child.name))
            else:
                entries.append(self._manifest_entry("upload", child.name, child.name, child.name))

        if entries:
            self._save_manifest(topic_dir, entries)
        return entries

    def _match_existing_source_path(self, value: str, remaining: dict[str, Path]) -> Path | None:
        parsed = urlsplit(value)
        candidates = []
        if parsed.path:
            path_name = Path(parsed.path)
            candidates.append(self._slug_name(path_name.stem or path_name.name))
        candidates.append(self._slug_name(value))

        for child in remaining.values():
            child_slug = self._slug_name(child.name)
            for candidate in candidates:
                if candidate and (child_slug == candidate or candidate in child_slug or child_slug in candidate):
                    return child
        return None

    def _register_source(self, topic_dir: Path, kind: str, label: str, value: str, relative_path: str) -> None:
        manifest = self._load_manifest(topic_dir)
        manifest.append(self._manifest_entry(kind, label, value, relative_path))
        self._save_manifest(topic_dir, manifest)

    def _sync_topic_description(self, topic_id: str, topic_dir: Path, user_id: str) -> None:
        manifest = self._load_manifest(topic_dir)
        description = "\n".join(entry["value"] for entry in manifest if entry["kind"] != "upload")
        self.store.update_topic_description(topic_id, description, user_id=user_id)

    @classmethod
    def _diagnose_archived_repository(cls, source_dir: Path) -> str | None:
        for repo_dir in [path for path in source_dir.iterdir() if path.is_dir()]:
            replacement_url = cls._detect_repository_replacement(repo_dir)
            if replacement_url:
                return f"This GitHub repo is archived. Use the active repository instead: {replacement_url}"
        for path in cls._replacement_inspection_files(source_dir):
            text = cls._read_text_if_possible(path)
            if not text or not cls._looks_like_archived_transition(text):
                continue
            return "This GitHub repo is archived and does not include the active codebase."
        return None

    @classmethod
    def _detect_repository_replacement(cls, repo_dir: Path) -> str | None:
        for path in cls._replacement_inspection_files(repo_dir):
            text = cls._read_text_if_possible(path)
            if not text or not cls._looks_like_archived_transition(text):
                continue
            replacement_url = cls._extract_replacement_url(text)
            if replacement_url:
                return replacement_url
        return None

    @staticmethod
    def _replacement_inspection_files(root: Path) -> list[Path]:
        return [
            *root.glob("README*"),
            *root.glob("_github/repository.md"),
            *root.glob("_github/discussions.md"),
        ]

    @staticmethod
    def _read_text_if_possible(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None

    @staticmethod
    def _looks_like_archived_transition(text: str) -> bool:
        lowered = text.lower()
        markers = [
            "project transition notice",
            "development has transitioned",
            "this repository will be archived",
            "no longer maintained",
            "- archived: true",
            "default branch: archive",
        ]
        return any(marker in lowered for marker in markers)

    @staticmethod
    def _extract_replacement_url(text: str) -> str | None:
        for match in re.finditer(r"https?://[^\s)>\]]+", text, flags=re.IGNORECASE):
            url = match.group(0).rstrip(".,")
            if "gitlab.com" in url.lower():
                return url
        return None
