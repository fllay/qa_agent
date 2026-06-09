import pytest

from qa_agent_app.graphify_client import GraphifyClient, GraphifyError


def test_graphify_missing_command_fails_fast(tmp_path):
    client = GraphifyClient("__missing_graphify_binary__", 10)

    with pytest.raises(GraphifyError) as exc:
        client.ensure_available()

    assert "was not found" in str(exc.value)


def test_graphify_empty_graph_fails(tmp_path):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text('{"nodes": [], "edges": []}', encoding="utf-8")

    with pytest.raises(GraphifyError) as exc:
        GraphifyClient._ensure_graph_has_nodes(graph_path)

    assert "empty graph" in str(exc.value)
