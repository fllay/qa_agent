from qa_agent_app.models import LlmSettings, ThreadCreate, TopicCreate
from qa_agent_app.storage import TopicStore


def test_topic_lifecycle(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="Billing Docs", description="API docs"))

    assert topic.name == "Billing Docs"
    assert topic.status == "new"
    assert topic.progress_percent == 0
    assert topic.progress_label == ""
    assert store.get_topic(topic.id).description == "API docs"
    default_threads = store.list_threads(topic.id)
    assert len(default_threads) == 1
    assert default_threads[0].title == "Agent Chat"

    updated = store.update_topic(topic.id, status="indexing", progress_percent=44, progress_label="Collecting GitHub context")
    assert updated.progress_percent == 44
    assert updated.progress_label == "Collecting GitHub context"

    updated = store.update_topic(topic.id, status="ready", progress_percent=100, progress_label="Ready", graph_path="graph.json")
    assert updated.status == "ready"
    assert updated.progress_percent == 100
    assert updated.progress_label == "Ready"
    assert updated.graph_path == "graph.json"

    store.delete_topic(topic.id)
    assert store.list_topics() == []


def test_thread_lifecycle(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="Project"))
    thread = store.create_thread(topic.id, ThreadCreate(title="Install questions"))

    assert thread.topic_id == topic.id
    assert thread.title == "Install questions"
    assert any(item.id == thread.id for item in store.list_threads(topic.id))


def test_thread_messages_persist_and_rename(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="Project"))
    thread = store.create_thread(topic.id, ThreadCreate(title="New chat"))

    user_message = store.append_message(thread.id, "user", "How do I run this project?")
    agent_message = store.append_message(thread.id, "agent", "Use docker compose.")
    renamed = store.rename_thread(thread.id, "How do I run this project?")
    messages = store.list_messages(thread.id)

    assert renamed.title == "How do I run this project?"
    assert [message.id for message in messages] == [user_message.id, agent_message.id]
    assert messages[0].role == "user"
    assert messages[1].role == "agent"


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
