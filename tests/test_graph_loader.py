import json
from pathlib import Path

from qa_agent_app.graph_loader import (
    FALLBACK_PREVIEW_MAX_EDGES,
    FALLBACK_PREVIEW_MAX_NODES,
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
