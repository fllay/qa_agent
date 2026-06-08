from qa_agent_app.models import LlmSettings, TopicCreate
from qa_agent_app.storage import TopicStore


def test_topic_lifecycle(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="Billing Docs", description="API docs"))

    assert topic.name == "Billing Docs"
    assert topic.status == "new"
    assert store.get_topic(topic.id).description == "API docs"

    updated = store.update_topic(topic.id, status="ready", graph_path="graph.json")
    assert updated.status == "ready"
    assert updated.graph_path == "graph.json"

    store.delete_topic(topic.id)
    assert store.list_topics() == []


def test_llm_settings_persist(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    defaults = LlmSettings()
    updated = store.update_llm_settings(
        LlmSettings(
            provider="openrouter",
            openrouter_api_key="key",
            openrouter_main_model="main",
            openrouter_reserve_model_1="reserve-a",
            openrouter_reserve_model_2="reserve-b",
        )
    )

    loaded = store.get_llm_settings(defaults)

    assert updated.provider == "openrouter"
    assert loaded.provider == "openrouter"
    assert loaded.openrouter_main_model == "main"
    assert loaded.openrouter_reserve_model_1 == "reserve-a"
    assert loaded.openrouter_reserve_model_2 == "reserve-b"
