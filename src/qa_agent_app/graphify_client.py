import shutil
import subprocess
from pathlib import Path


class GraphifyError(RuntimeError):
    pass


class GraphifyClient:
    def __init__(self, command: str, timeout_seconds: int):
        self.command = command
        self.timeout_seconds = timeout_seconds

    def build_graph(self, topic_dir: Path, source_dir: Path) -> Path:
        if shutil.which(self.command) is None and not Path(self.command).exists():
            raise GraphifyError(
                f"Graphify command '{self.command}' was not found. Install Graphify or set GRAPHIFY_BIN."
            )

        output_dir = topic_dir / "graphify"
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [self.command, str(source_dir)]

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

        graph_path = self._find_graph_json(output_dir, source_dir)
        if graph_path is None:
            raise GraphifyError("Graphify completed but no graph.json output was found.")
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
