import json
from pathlib import Path


TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".rst",
    ".py",
    ".pyi",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".sh",
    ".bash",
    ".ps1",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".java",
    ".go",
    ".rs",
    ".sql",
    ".xml",
    ".proto",
    ".cmake",
}

HIGH_SIGNAL_NAMES = {
    "readme",
    "cmakelists.txt",
    "package.json",
    "pyproject.toml",
    "cargo.toml",
    "go.mod",
    "requirements.txt",
    "dockerfile",
    "compose.yml",
    "docker-compose.yml",
}


def build_fallback_graph(topic_dir: Path, source_dir: Path) -> Path:
    topic_dir.mkdir(parents=True, exist_ok=True)
    nodes: list[dict] = []
    edges: list[dict] = []

    repo_dirs = [path for path in source_dir.iterdir() if path.is_dir()]
    for repo_dir in sorted(repo_dirs):
        repo_node_id = f"repo::{repo_dir.name}"
        repo_summary = _repo_summary(repo_dir)
        nodes.append(
            {
                "id": repo_node_id,
                "label": repo_dir.name,
                "type": "repository",
                "path": str(repo_dir),
                "summary": repo_summary,
                "text": f"Repository {repo_dir.name}. {repo_summary}",
            }
        )

        for file_path in _select_files(repo_dir):
            rel_path = file_path.relative_to(repo_dir)
            node_id = f"file::{repo_dir.name}::{rel_path.as_posix()}"
            snippet = _read_snippet(file_path)
            nodes.append(
                {
                    "id": node_id,
                    "label": rel_path.as_posix(),
                    "type": _file_type(file_path),
                    "path": str(file_path),
                    "summary": f"{repo_dir.name} file {rel_path.as_posix()}",
                    "text": (
                        f"Repository {repo_dir.name}. File {rel_path.as_posix()}. "
                        f"Content snippet: {snippet}"
                    ),
                }
            )
            edges.append({"source": repo_node_id, "target": node_id, "relation": "contains"})

    graph_path = topic_dir / "fallback-graph.json"
    graph_path.write_text(json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False), encoding="utf-8")
    return graph_path


def _select_files(repo_dir: Path, limit: int = 240) -> list[Path]:
    candidates: list[tuple[int, Path]] = []
    for path in repo_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".git") for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS and path.name.lower() not in HIGH_SIGNAL_NAMES:
            continue
        priority = _priority(path, repo_dir)
        candidates.append((priority, path))
    candidates.sort(key=lambda item: (item[0], len(item[1].parts), item[1].as_posix().lower()))
    return [path for _, path in candidates[:limit]]


def _priority(path: Path, repo_dir: Path) -> int:
    name = path.name.lower()
    rel = path.relative_to(repo_dir).as_posix().lower()
    if name in HIGH_SIGNAL_NAMES or rel.startswith("readme"):
        return 0
    if rel.startswith("configs/") or rel.startswith("docs/") or rel.startswith("apps/") or rel.startswith("lib/"):
        return 1
    if rel.startswith("_github/"):
        return 2
    return 3


def _repo_summary(repo_dir: Path) -> str:
    file_count = 0
    signal_files: list[str] = []
    readme_text = ""
    for path in repo_dir.rglob("*"):
        if path.is_file():
            file_count += 1
            if len(signal_files) < 8 and (path.name.lower() in HIGH_SIGNAL_NAMES or path.suffix.lower() in {".md", ".cpp", ".h", ".py"}):
                signal_files.append(path.relative_to(repo_dir).as_posix())
    for candidate in [*repo_dir.glob("README*"), repo_dir / "_github" / "repository.md"]:
        if candidate.exists():
            readme_text = _read_snippet(candidate, max_chars=900)
            if readme_text:
                break
    signals = ", ".join(signal_files[:6]) or "No highlighted files."
    return f"Repository snapshot with {file_count} files. Key files: {signals}. {readme_text}"


def _read_snippet(path: Path, max_chars: int = 1200) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    normalized = " ".join(text.split())
    return normalized[:max_chars]


def _file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt", ".rst"}:
        return "document"
    if suffix in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"}:
        return "config"
    return "code"
