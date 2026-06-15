import sqlite3

from qa_agent_app.models import LlmSettings, ThreadCreate, TopicCreate
from qa_agent_app.storage import TopicStore


def test_topic_lifecycle(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="Billing Docs", description="API docs"))

    assert topic.user_id == "legacy-default"
    assert topic.name == "Billing Docs"
    assert topic.status == "new"
    assert topic.progress_percent == 0
    assert topic.progress_label == ""
    assert store.get_topic(topic.id).description == "API docs"
    default_threads = store.list_threads(topic.id)
    assert len(default_threads) == 1
    assert default_threads[0].title == "New chat"

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


def test_topic_can_set_initial_thread_title(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="Repo", initial_thread_title="Topic chat"))

    default_threads = store.list_threads(topic.id)

    assert len(default_threads) == 1
    assert default_threads[0].title == "Topic chat"


def test_thread_lifecycle(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="Project"))
    thread = store.create_thread(topic.id, ThreadCreate(title="Install questions"))

    assert thread.topic_id == topic.id
    assert thread.title == "Install questions"
    assert any(item.id == thread.id for item in store.list_threads(topic.id))


def test_delete_thread_removes_it_from_topic(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="Project"))
    thread = store.create_thread(topic.id, ThreadCreate(title="Temporary chat"))

    store.delete_thread(thread.id)

    assert all(item.id != thread.id for item in store.list_threads(topic.id))
    assert len(store.list_threads(topic.id)) == 1


def test_delete_threads_by_title_removes_matching_threads(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    topic = store.create_topic(TopicCreate(name="Project", initial_thread_title="Topic chat"))
    store.create_thread(topic.id, ThreadCreate(title="Topic chat"))
    store.create_thread(topic.id, ThreadCreate(title="Keep me"))

    deleted = store.delete_threads_by_title(topic.id, "Topic chat")

    titles = [item.title for item in store.list_threads(topic.id)]
    assert deleted == 2
    assert titles == ["Keep me"]


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


def test_clear_llm_settings_restores_defaults(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    defaults = LlmSettings(provider="local", local_model="env-model")
    store.update_llm_settings(
        LlmSettings(provider="openrouter", openrouter_main_model="main"),
        user_id="user-test",
    )

    store.clear_llm_settings(user_id="user-test")
    loaded = store.get_llm_settings(defaults, user_id="user-test")

    assert loaded.provider == "local"
    assert loaded.local_model == "env-model"
    assert loaded.openrouter_main_model == defaults.openrouter_main_model


def test_user_scoped_topics_threads_and_messages(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    alice_topic = store.create_topic(TopicCreate(name="Project"), user_id="user-alice")
    bob_topic = store.create_topic(TopicCreate(name="Project"), user_id="user-bob")
    alice_thread = store.create_thread(alice_topic.id, ThreadCreate(title="Alice thread"), user_id="user-alice")
    bob_thread = store.create_thread(bob_topic.id, ThreadCreate(title="Bob thread"), user_id="user-bob")
    store.append_message(alice_thread.id, "user", "hello from alice", user_id="user-alice")
    store.append_message(bob_thread.id, "user", "hello from bob", user_id="user-bob")

    assert [topic.id for topic in store.list_topics(user_id="user-alice")] == [alice_topic.id]
    assert [topic.id for topic in store.list_topics(user_id="user-bob")] == [bob_topic.id]
    alice_thread_ids = [thread.id for thread in store.list_threads(alice_topic.id, user_id="user-alice")]
    bob_thread_ids = [thread.id for thread in store.list_threads(bob_topic.id, user_id="user-bob")]

    assert alice_thread.id in alice_thread_ids
    assert bob_thread.id in bob_thread_ids
    assert bob_thread.id not in alice_thread_ids
    assert alice_thread.id not in bob_thread_ids
    assert [message.text for message in store.list_messages(alice_thread.id, user_id="user-alice")] == ["hello from alice"]
    assert [message.text for message in store.list_messages(bob_thread.id, user_id="user-bob")] == ["hello from bob"]

    try:
        store.get_topic(alice_topic.id, user_id="user-bob")
    except KeyError:
        pass
    else:
        raise AssertionError("expected bob to be blocked from alice topic")

    try:
        store.get_thread(alice_thread.id, user_id="user-bob")
    except KeyError:
        pass
    else:
        raise AssertionError("expected bob to be blocked from alice thread")


def test_llm_settings_are_scoped_per_user(tmp_path):
    store = TopicStore(tmp_path / "qa.sqlite")
    defaults = LlmSettings()
    store.update_llm_settings(
        LlmSettings(provider="openrouter", openrouter_main_model="alice-main"),
        user_id="user-alice",
    )
    store.update_llm_settings(
        LlmSettings(provider="local", local_model="bob-model"),
        user_id="user-bob",
    )

    alice = store.get_llm_settings(defaults, user_id="user-alice")
    bob = store.get_llm_settings(defaults, user_id="user-bob")

    assert alice.provider == "openrouter"
    assert alice.openrouter_main_model == "alice-main"
    assert bob.provider == "local"
    assert bob.local_model == "bob-model"


def test_store_migrates_legacy_database_before_creating_indexes(tmp_path):
    db_path = tmp_path / "qa.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE topics (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE chat_threads (
                id TEXT PRIMARY KEY,
                topic_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(topic_id) REFERENCES topics(id) ON DELETE CASCADE
            );
            CREATE TABLE chat_messages (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(thread_id) REFERENCES chat_threads(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            """
            INSERT INTO topics (id, name, description, status, created_at, updated_at)
            VALUES ('topic-1', 'Legacy Topic', '', 'new', '2026-06-12T00:00:00+00:00', '2026-06-12T00:00:00+00:00')
            """
        )
        conn.execute(
            """
            INSERT INTO chat_threads (id, topic_id, title, created_at, updated_at)
            VALUES ('thread-1', 'topic-1', 'Legacy Thread', '2026-06-12T00:00:00+00:00', '2026-06-12T00:00:00+00:00')
            """
        )
        conn.commit()
    finally:
        conn.close()

    store = TopicStore(db_path)
    topics = store.list_topics()
    threads = store.list_threads("topic-1")

    assert topics[0].user_id == "legacy-default"
    assert threads[0].user_id == "legacy-default"


def test_store_init_is_idempotent_after_migration(tmp_path):
    db_path = tmp_path / "qa.sqlite"

    first = TopicStore(db_path)
    topic = first.create_topic(TopicCreate(name="Demo"))

    second = TopicStore(db_path)
    topics = second.list_topics()

    assert [item.id for item in topics] == [topic.id]
