from qa_agent_app.agent import QaAgent


def test_draft_topic_extracts_source_and_uses_repo_name_fallback():
    agent = QaAgent("local", local_base_url="http://127.0.0.1:9/v1")

    name, sources = agent.draft_topic("create a topic about https://github.com/srsran/srsran_project")

    assert sources == ["https://github.com/srsran/srsran_project"]
    assert name == "Srsran Project"


def test_draft_topic_deduplicates_sources_and_strips_trailing_punctuation():
    agent = QaAgent("local", local_base_url="http://127.0.0.1:9/v1")

    name, sources = agent.draft_topic(
        "please create a topic for https://github.com/acme/acmeflow, then use https://github.com/acme/acmeflow."
    )

    assert sources == ["https://github.com/acme/acmeflow"]
    assert name == "Acmeflow"
