import pytest
import subprocess

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


def test_graphify_retries_code_only_when_semantic_key_missing(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    topic_dir = tmp_path / "topic"
    source_dir.mkdir()
    topic_dir.mkdir()
    graph_dir = source_dir / "graphify-out"
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1] == "extract":
            return subprocess.CompletedProcess(
                command,
                2,
                stdout="",
                stderr="error: no LLM API key found (2 doc/paper/image file(s) need semantic extraction)",
            )
        graph_dir.mkdir()
        (graph_dir / "graph.json").write_text('{"nodes": [{"id": "a"}], "edges": []}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("qa_agent_app.graphify_client.shutil.which", lambda command: command)
    monkeypatch.setattr("qa_agent_app.graphify_client.subprocess.run", fake_run)

    graph_path = GraphifyClient("graphify", 10).build_graph(topic_dir, source_dir)

    assert graph_path == graph_dir / "graph.json"
    assert calls == [
        ["graphify", "extract", str(source_dir.resolve()), "--out", str(topic_dir.resolve()), "--no-cluster"],
        ["graphify", "update", str(source_dir.resolve()), "--no-cluster", "--force"],
    ]
