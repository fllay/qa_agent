from qa_agent_app.config import Settings
from qa_agent_app.main import _resolve_topic_graph_path, effective_llm_settings
from qa_agent_app.models import LlmSettings, Topic, TopicCreate
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


def test_persisted_llm_settings_override_env_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QA_AGENT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENROUTER_MAIN_MODEL", raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "QA_AGENT_LLM_PROVIDER=openrouter",
                "OPENROUTER_MAIN_MODEL=env-main",
                "OPENROUTER_RESERVE_MODEL_1=env-reserve-a",
                "OPENROUTER_RESERVE_MODEL_2=env-reserve-b",
            ]
        ),
        encoding="utf-8",
    )
    store = TopicStore(tmp_path / "qa.sqlite")
    store.update_llm_settings(
        LlmSettings(
            provider="local",
            openrouter_main_model="persisted-main",
            openrouter_reserve_model_1="persisted-reserve-a",
            openrouter_reserve_model_2="persisted-reserve-b",
        ),
        user_id="user-test",
    )

    llm = effective_llm_settings(Settings(), store, "user-test")

    assert llm.provider == "local"
    assert llm.openrouter_main_model == "persisted-main"
    assert llm.openrouter_reserve_model_1 == "persisted-reserve-a"
    assert llm.openrouter_reserve_model_2 == "persisted-reserve-b"
