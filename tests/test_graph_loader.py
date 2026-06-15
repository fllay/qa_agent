import json
from pathlib import Path

from qa_agent_app.graph_loader import (
    FALLBACK_PREVIEW_MAX_EDGES,
    FALLBACK_PREVIEW_MAX_NODES,
    GraphIndex,
    graph_preview_limits,
    load_graph_preview,
)


def test_load_graph_preview_limits_and_labels(tmp_path):
    graph_path = tmp_path / "graph.json"
    payload = {
        "nodes": [
            {"id": "repo", "label": "Repository", "type": "repository"},
            {"id": "readme", "label": "README.md", "type": "document"},
            {"id": "api", "label": "ApiService", "type": "class"},
        ],
        "edges": [
            {"source": "repo", "target": "readme", "relation": "contains"},
            {"source": "repo", "target": "api", "relation": "contains"},
        ],
    }
    graph_path.write_text(json.dumps(payload), encoding="utf-8")

    preview = load_graph_preview("demo-topic", "Demo Topic", graph_path, max_nodes=2, max_edges=1)

    assert preview.topic_id == "demo-topic"
    assert preview.topic_name == "Demo Topic"
    assert preview.graph_kind == "graphify"
    assert preview.total_nodes == 3
    assert preview.total_edges == 2
    assert preview.kind_counts == {"repository": 1, "document": 1, "class": 1}
    assert preview.sampled is True
    assert len(preview.nodes) == 2
    assert preview.nodes[0].label == "Repository"
    assert len(preview.edges) == 1


def test_load_graph_preview_accepts_graphify_links_format(tmp_path):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "directed": False,
                "multigraph": False,
                "nodes": [
                    {"id": "file::app.py", "label": "app.py", "type": "code"},
                    {"id": "func::hello", "label": "hello", "type": "code"},
                ],
                "links": [
                    {"source": "file::app.py", "target": "func::hello", "relation": "contains"},
                ],
            }
        ),
        encoding="utf-8",
    )

    preview = load_graph_preview("demo-topic", "Demo Topic", graph_path)

    assert preview.total_nodes == 2
    assert preview.total_edges == 1
    assert preview.edges[0].source == "file::app.py"


def test_load_graph_preview_balances_large_fallback_graph(tmp_path):
    graph_path = tmp_path / "fallback-graph.json"
    nodes = [{"id": "repo", "label": "Repository", "type": "repository"}]
    edges = []
    for index in range(900):
        node_id = f"code-{index}"
        nodes.append({"id": node_id, "label": f"code_{index}.cpp", "type": "code"})
        edges.append({"source": "repo", "target": node_id, "relation": "contains"})
    for index in range(220):
        node_id = f"config-{index}"
        nodes.append({"id": node_id, "label": f"cfg_{index}.yml", "type": "config"})
        edges.append({"source": "repo", "target": node_id, "relation": "contains"})
    for index in range(180):
        node_id = f"doc-{index}"
        nodes.append({"id": node_id, "label": f"doc_{index}.md", "type": "document"})
        edges.append({"source": "repo", "target": node_id, "relation": "contains"})
    graph_path.write_text(json.dumps({"nodes": nodes, "edges": edges}), encoding="utf-8")

    preview = load_graph_preview(
        "demo-topic",
        "Demo Topic",
        graph_path,
        max_nodes=FALLBACK_PREVIEW_MAX_NODES,
        max_edges=FALLBACK_PREVIEW_MAX_EDGES,
    )

    preview_counts = {}
    for node in preview.nodes:
        preview_counts[node.kind] = preview_counts.get(node.kind, 0) + 1

    assert preview.sampled is True
    assert preview.total_nodes == len(nodes)
    assert preview.total_edges == len(edges)
    assert len(preview.nodes) <= FALLBACK_PREVIEW_MAX_NODES
    assert len(preview.edges) <= FALLBACK_PREVIEW_MAX_EDGES
    assert preview.kind_counts["code"] == 900
    assert preview.kind_counts["config"] == 220
    assert preview.kind_counts["document"] == 180
    assert preview_counts["repository"] == 1
    assert preview_counts["config"] > 0
    assert preview_counts["document"] > 0


def test_graph_preview_limits_do_not_cap_fallback_graphs():
    assert graph_preview_limits(Path("fallback-graph.json")) == (None, None)


def test_graph_search_prioritizes_repo_context_for_broad_project_questions(tmp_path):
    graph_path = tmp_path / "fallback-graph.json"
    payload = {
        "nodes": [
            {
                "id": "repo::acmenet",
                "label": "acmenet",
                "type": "repository",
                "path": str(tmp_path / "source" / "acmenet"),
                "summary": "AcmeNet is a network control project designed for production deployment.",
            },
            {
                "id": "file::acmenet::README.md",
                "label": "README.md",
                "type": "document",
                "path": str(tmp_path / "source" / "acmenet" / "README.md"),
                "summary": "This project provides a radio access network solution.",
            },
            {
                "id": "file::acmenet::CMakeLists.txt",
                "label": "CMakeLists.txt",
                "type": "config",
                "path": str(tmp_path / "source" / "acmenet" / "CMakeLists.txt"),
                "summary": 'This is bad practice.") endif (${CMAKE_SOURCE_DIR} STREQUAL ${CMAKE_BINARY_DIR})',
            },
        ],
        "edges": [
            {"source": "repo::acmenet", "target": "file::acmenet::README.md", "relation": "contains"},
            {"source": "repo::acmenet", "target": "file::acmenet::CMakeLists.txt", "relation": "contains"},
        ],
    }
    graph_path.write_text(json.dumps(payload), encoding="utf-8")

    results = GraphIndex(graph_path).search("what is this project do", limit=3)

    assert [item["id"] for item in results[:2]] == ["repo::acmenet", "file::acmenet::README.md"]
    assert "file::acmenet::CMakeLists.txt" not in [item["id"] for item in results]


def test_graph_search_prioritizes_github_issues_for_issue_questions(tmp_path):
    graph_path = tmp_path / "fallback-graph.json"
    payload = {
        "nodes": [
            {
                "id": "repo::acmenet",
                "label": "acmenet",
                "type": "repository",
                "path": str(tmp_path / "source" / "acmenet"),
                "summary": "AcmeNet is a network control project.",
            },
            {
                "id": "file::acmenet::_github/issues.md",
                "label": "_github/issues.md",
                "type": "document",
                "path": str(tmp_path / "source" / "acmenet" / "_github" / "issues.md"),
                "summary": "Issue #42: Packet scheduler stalls",
            },
            {
                "id": "file::acmenet::README.md",
                "label": "README.md",
                "type": "document",
                "path": str(tmp_path / "source" / "acmenet" / "README.md"),
                "summary": "This project README mentions issue templates.",
            },
        ],
        "edges": [
            {"source": "repo::acmenet", "target": "file::acmenet::_github/issues.md", "relation": "contains"},
            {"source": "repo::acmenet", "target": "file::acmenet::README.md", "relation": "contains"},
        ],
    }
    graph_path.write_text(json.dumps(payload), encoding="utf-8")

    results = GraphIndex(graph_path).search("can i have latest issue on the project", limit=3)

    assert results[0]["id"] == "file::acmenet::_github/issues.md"
