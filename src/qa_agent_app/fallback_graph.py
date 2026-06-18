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

IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".graphify",
    "graphify",
    "graphify-out",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
}


def build_fallback_graph(topic_dir: Path, source_dir: Path) -> Path:
    topic_dir.mkdir(parents=True, exist_ok=True)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_node_ids: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()

    repo_dirs = [path for path in source_dir.iterdir() if path.is_dir() and not _is_ignored_path(path)]
    for repo_dir in sorted(repo_dirs):
        repo_node_id = f"repo::{repo_dir.name}"
        repo_summary = _repo_summary(repo_dir)
        _append_node(
            nodes,
            seen_node_ids,
            {
                "id": repo_node_id,
                "label": repo_dir.name,
                "type": "repository",
                "path": str(repo_dir),
                "summary": repo_summary,
                "text": f"Repository {repo_dir.name}. {repo_summary}",
            },
        )

        for file_path in _select_files(repo_dir):
            rel_path = file_path.relative_to(repo_dir)
            parent_node_id = _ensure_directory_chain(repo_dir, rel_path, nodes, edges, seen_node_ids, seen_edges)
            node_id = f"file::{repo_dir.name}::{rel_path.as_posix()}"
            snippet = _read_snippet(file_path)
            _append_node(
                nodes,
                seen_node_ids,
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
                },
            )
            _append_edge(edges, seen_edges, parent_node_id, node_id, "contains_file")

    graph_path = topic_dir / "fallback-graph.json"
    graph_path.write_text(json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False), encoding="utf-8")
    return graph_path


def _select_files(repo_dir: Path) -> list[Path]:
    candidates: list[tuple[int, Path]] = []
    for path in repo_dir.rglob("*"):
        if not path.is_file():
            continue
        if _is_ignored_path(path):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS and path.name.lower() not in HIGH_SIGNAL_NAMES:
            continue
        priority = _priority(path, repo_dir)
        candidates.append((priority, path))

    candidates.sort(key=lambda item: (item[0], len(item[1].parts), item[1].as_posix().lower()))
    return [path for _, path in candidates]


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
        if _is_ignored_path(path) or not path.is_file():
            continue
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
    if path.name.lower() in {"cmakelists.txt"} or path.suffix.lower() == ".cmake":
        return "config"
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt", ".rst"}:
        return "document"
    if suffix in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"}:
        return "config"
    return "code"


def _ensure_directory_chain(
    repo_dir: Path,
    rel_path: Path,
    nodes: list[dict],
    edges: list[dict],
    seen_node_ids: set[str],
    seen_edges: set[tuple[str, str, str]],
) -> str:
    repo_node_id = f"repo::{repo_dir.name}"
    parent_node_id = repo_node_id
    current_parts: list[str] = []

    for part in rel_path.parent.parts:
        if part in {"", "."}:
            continue
        current_parts.append(part)
        dir_rel = "/".join(current_parts)
        dir_node_id = f"dir::{repo_dir.name}::{dir_rel}"
        _append_node(
            nodes,
            seen_node_ids,
            {
                "id": dir_node_id,
                "label": dir_rel,
                "type": "directory",
                "path": str(repo_dir / Path(*current_parts)),
                "summary": f"{repo_dir.name} directory {dir_rel}",
                "text": f"Repository {repo_dir.name}. Directory {dir_rel}. Contains related files and subdirectories.",
            },
        )
        _append_edge(edges, seen_edges, parent_node_id, dir_node_id, "contains_dir")
        parent_node_id = dir_node_id

    return parent_node_id


def _append_node(nodes: list[dict], seen_node_ids: set[str], payload: dict) -> None:
    node_id = str(payload["id"])
    if node_id in seen_node_ids:
        return
    seen_node_ids.add(node_id)
    nodes.append(payload)


def _append_edge(
    edges: list[dict],
    seen_edges: set[tuple[str, str, str]],
    source: str,
    target: str,
    relation: str,
) -> None:
    key = (source, target, relation)
    if key in seen_edges:
        return
    seen_edges.add(key)
    edges.append({"source": source, "target": target, "relation": relation})


def _is_ignored_path(path: Path) -> bool:
    return any(part in IGNORED_DIR_NAMES for part in path.parts)
