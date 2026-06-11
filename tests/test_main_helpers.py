from qa_agent_app.main import _resolve_topic_graph_path
from qa_agent_app.models import Topic, TopicCreate
from qa_agent_app.storage import TopicStore


def test_resolve_topic_graph_path_recovers_from_stale_saved_path(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="srsRAN"))

    topic_dir = tmp_path / "topics" / topic.id
    graph_dir = topic_dir / "graphify-out"
    graph_dir.mkdir(parents=True)
    graph_path = graph_dir / "graph.json"
    graph_path.write_text('{"nodes": [], "edges": []}', encoding="utf-8")

    updated = store.update_topic(topic.id, status="ready", graph_path=str(topic_dir / "missing" / "graph.json"))

    resolved = _resolve_topic_graph_path(updated, tmp_path / "topics")

    assert resolved == graph_path
