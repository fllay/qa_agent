import shutil
import subprocess
import json
import os
from pathlib import Path


class GraphifyError(RuntimeError):
    pass


class GraphifyClient:
    def __init__(self, command: str, timeout_seconds: int):
        self.command = command
        self.timeout_seconds = timeout_seconds

    def ensure_available(self) -> None:
        if shutil.which(self.command) is None and not Path(self.command).exists():
            raise GraphifyError(
                f"Graphify command '{self.command}' was not found. Install Graphify or set GRAPHIFY_BIN."
            )

    def build_graph(self, topic_dir: Path, source_dir: Path) -> Path:
        self.ensure_available()

        topic_dir = topic_dir.resolve()
        source_dir = source_dir.resolve()
        output_dir = topic_dir / "graphify"
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [self.command, "extract", str(source_dir), "--out", str(topic_dir), "--no-cluster"]
        effective_timeout_seconds = self._resolve_timeout_seconds(source_dir)

        result = self._run_graphify(command, output_dir, effective_timeout_seconds)
        if result.returncode != 0 and self._is_missing_semantic_api_key(result):
            result = self._run_graphify(
                [self.command, "update", str(source_dir), "--no-cluster", "--force"],
                output_dir,
                effective_timeout_seconds,
            )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
            raise GraphifyError(f"Graphify failed: {detail}")

        graph_path = self._find_graph_json(topic_dir, output_dir, source_dir)
        if graph_path is None:
            raise GraphifyError("Graphify completed but no graph.json output was found.")
        self._ensure_graph_has_nodes(graph_path)
        return graph_path

    def _run_graphify(
        self,
        command: list[str],
        cwd: Path,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                cwd=cwd,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GraphifyError(f"Graphify timed out after {timeout_seconds} seconds.") from exc

    def _resolve_timeout_seconds(self, source_dir: Path) -> int:
        timeout_seconds = max(int(self.timeout_seconds), 60)
        file_count, total_bytes = self._estimate_source_size(source_dir)

        if file_count >= 20000 or total_bytes >= 750 * 1024 * 1024:
            return max(timeout_seconds, 7200)
        if file_count >= 8000 or total_bytes >= 300 * 1024 * 1024:
            return max(timeout_seconds, 3600)
        if file_count >= 2500 or total_bytes >= 120 * 1024 * 1024:
            return max(timeout_seconds, 1800)
        return timeout_seconds

    @staticmethod
    def _estimate_source_size(source_dir: Path) -> tuple[int, int]:
        file_count = 0
        total_bytes = 0

        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [name for name in dirs if name not in {".git", ".hg", ".svn", "node_modules", ".venv", "venv"}]
            file_count += len(files)
            for name in files:
                try:
                    total_bytes += (Path(root) / name).stat().st_size
                except OSError:
                    continue
        return file_count, total_bytes

    @staticmethod
    def _is_missing_semantic_api_key(result: subprocess.CompletedProcess[str]) -> bool:
        output = f"{result.stderr}\n{result.stdout}".lower()
        return "no llm api key found" in output and "semantic extraction" in output

    @staticmethod
    def _find_graph_json(*roots: Path) -> Path | None:
        candidates: list[Path] = []
        for root in roots:
            if root.exists():
                candidates.extend(root.rglob("graph.json"))
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)

    @staticmethod
    def _ensure_graph_has_nodes(graph_path: Path) -> None:
        try:
            payload = json.loads(graph_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise GraphifyError(f"Graphify wrote an unreadable graph.json: {exc}") from exc
        nodes = payload.get("nodes", []) if isinstance(payload, dict) else []
        if not nodes:
            raise GraphifyError(
                "Graphify completed but produced an empty graph. "
                "This source may not contain analyzable code or may only contain metadata/README files."
            )
