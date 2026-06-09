import shutil
import subprocess
import json
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

        try:
            result = subprocess.run(
                command,
                cwd=output_dir,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GraphifyError(f"Graphify timed out after {self.timeout_seconds} seconds.") from exc

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
            raise GraphifyError(f"Graphify failed: {detail}")

        graph_path = self._find_graph_json(topic_dir, output_dir, source_dir)
        if graph_path is None:
            raise GraphifyError("Graphify completed but no graph.json output was found.")
        self._ensure_graph_has_nodes(graph_path)
        return graph_path

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
