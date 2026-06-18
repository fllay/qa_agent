import json
from collections import Counter

from qa_agent_app.fallback_graph import build_fallback_graph


def test_fallback_graph_balances_code_heavy_repository(tmp_path):
    source_dir = tmp_path / "source"
    repo_dir = source_dir / "ocudu"
    repo_dir.mkdir(parents=True)
    (repo_dir / "README.md").write_text("# OCUDU\n", encoding="utf-8")
    (repo_dir / "CMakeLists.txt").write_text("project(ocudu)\n", encoding="utf-8")

    docs_dir = repo_dir / "docs"
    docs_dir.mkdir()
    for index in range(80):
        (docs_dir / f"guide_{index}.md").write_text("Guide\n", encoding="utf-8")

    lib_dir = repo_dir / "lib"
    lib_dir.mkdir()
    for index in range(260):
        (lib_dir / f"unit_{index}.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

    graph_path = build_fallback_graph(tmp_path / "topic", source_dir)
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    counts = Counter(node["type"] for node in payload["nodes"])

    assert counts["code"] > counts["document"]
    assert counts["code"] >= 170
    assert any(node["label"] == "CMakeLists.txt" and node["type"] == "config" for node in payload["nodes"])


def test_fallback_graph_ignores_generated_and_dependency_directories(tmp_path):
    source_dir = tmp_path / "source"
    repo_dir = source_dir / "ocudu"
    repo_dir.mkdir(parents=True)
    (repo_dir / "README.md").write_text("# OCUDU\n", encoding="utf-8")
    (repo_dir / "real.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

    graphify_cache_dir = repo_dir / "graphify-out" / "cache"
    graphify_cache_dir.mkdir(parents=True)
    (graphify_cache_dir / "artifact.cpp").write_text("generated\n", encoding="utf-8")

    node_modules_dir = repo_dir / "node_modules" / "pkg"
    node_modules_dir.mkdir(parents=True)
    (node_modules_dir / "index.js").write_text("module.exports = {};\n", encoding="utf-8")

    graph_path = build_fallback_graph(tmp_path / "topic", source_dir)
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    labels = {node["label"] for node in payload["nodes"]}
    repo_labels = {node["label"] for node in payload["nodes"] if node["type"] == "repository"}

    assert "ocudu" in repo_labels
    assert "real.cpp" in labels
    assert "graphify-out/cache/artifact.cpp" not in labels
    assert "node_modules/pkg/index.js" not in labels
