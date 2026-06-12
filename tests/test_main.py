import shutil
import stat

from fastapi.testclient import TestClient

from qa_agent_app.config import get_settings
from qa_agent_app.main import USER_COOKIE_NAME, _handle_remove_readonly, app


def test_remove_readonly_handler_allows_rmtree(tmp_path):
    topic_dir = tmp_path / "topic"
    nested = topic_dir / ".git" / "objects" / "pack"
    nested.mkdir(parents=True)
    target = nested / "pack.idx"
    target.write_text("pack", encoding="utf-8")
    target.chmod(stat.S_IREAD)

    shutil.rmtree(topic_dir, onexc=_handle_remove_readonly)

    assert not topic_dir.exists()


def test_cookie_is_issued_and_scopes_topics_per_client(tmp_path):
    data_dir = tmp_path / "data"

    def override_settings():
        from qa_agent_app.config import Settings

        settings = Settings.model_construct(
            data_dir=data_dir,
            database_path=data_dir / "qa.sqlite",
            graphify_bin="graphify",
            graphify_timeout_seconds=900,
            github_token=None,
            github_max_pages=10,
            github_per_page=100,
            llm_provider="local",
            local_llm_base_url="http://127.0.0.1:11434/v1",
            local_llm_api_key="local",
            local_llm_model="llama3.1:8b",
            openrouter_api_key=None,
            openrouter_base_url="https://openrouter.ai/api/v1",
            openrouter_main_model="openrouter/auto",
            openrouter_reserve_model_1="openai/gpt-4o-mini",
            openrouter_reserve_model_2="google/gemini-flash-1.5",
        )
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.topics_dir.mkdir(parents=True, exist_ok=True)
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        return settings

    app.dependency_overrides[get_settings] = override_settings
    try:
        with TestClient(app) as alice_client, TestClient(app) as bob_client:
            alice_page = alice_client.get("/chat")
            bob_page = bob_client.get("/chat")

            assert USER_COOKIE_NAME in alice_page.cookies
            assert USER_COOKIE_NAME in bob_page.cookies
            assert alice_page.cookies[USER_COOKIE_NAME] != bob_page.cookies[USER_COOKIE_NAME]

            created = alice_client.post("/api/topics", json={"name": "Alice Docs"})
            assert created.status_code == 200

            alice_topics = alice_client.get("/api/topics")
            bob_topics = bob_client.get("/api/topics")

            assert [item["name"] for item in alice_topics.json()] == ["Alice Docs"]
            assert bob_topics.json() == []
    finally:
        app.dependency_overrides.clear()
