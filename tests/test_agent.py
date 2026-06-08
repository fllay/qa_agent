import json
from datetime import datetime, timezone

from networkx import Graph
from networkx.readwrite import json_graph

from qa_agent_app.agent import QaAgent
from qa_agent_app.models import Topic


def test_agent_answers_from_graph_context(tmp_path, monkeypatch):
    def fake_generate(**kwargs):
        raise RuntimeError("local endpoint unavailable")

    monkeypatch.setattr(QaAgent, "_generate_with_openai_compatible", staticmethod(fake_generate))
    graph = Graph()
    graph.add_node("auth", label="Authentication", summary="Uses OAuth token validation", path="docs/auth.md")
    graph.add_node("api", label="API Gateway", summary="Routes requests")
    graph.add_edge("auth", "api")
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(json_graph.node_link_data(graph)), encoding="utf-8")

    topic = Topic(
        id="topic-1",
        name="Topic",
        status="ready",
        graph_path=str(graph_path),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    response = QaAgent().answer(topic, "How does authentication work?")

    assert "OAuth token validation" in response.answer
    assert response.citations[0].label == "Authentication"


def test_openrouter_requires_three_models():
    agent = QaAgent(
        "openrouter",
        openrouter_api_key="key",
        openrouter_main_model="main",
        openrouter_reserve_model_1="reserve-a",
        openrouter_reserve_model_2="",
    )

    try:
        agent._generate_with_openrouter("question", ["context"])
    except ValueError as exc:
        assert "one main model and two reserve models" in str(exc)
    else:
        raise AssertionError("Expected OpenRouter model validation to fail")


def test_openrouter_passes_fallback_models(monkeypatch):
    captured = {}

    def fake_generate(**kwargs):
        captured.update(kwargs)
        return "answer"

    monkeypatch.setattr(QaAgent, "_generate_with_openai_compatible", staticmethod(fake_generate))
    agent = QaAgent(
        "openrouter",
        openrouter_api_key="key",
        openrouter_main_model="main",
        openrouter_reserve_model_1="reserve-a",
        openrouter_reserve_model_2="reserve-b",
    )

    assert agent._generate_with_openrouter("question", ["context"]) == "answer"
    assert captured["model"] == "main"
    assert captured["extra_body"] == {"models": ["main", "reserve-a", "reserve-b"]}


def test_llm_generation_has_no_app_level_timeout(monkeypatch):
    captured = {}

    class FakeChoice:
        message = type("Message", (), {"content": "answer"})

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            return type("Response", (), {"choices": [FakeChoice()]})

    class FakeClient:
        chat = type("Chat", (), {"completions": FakeCompletions})

        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("openai.OpenAI", FakeClient)

    answer = QaAgent._generate_with_openai_compatible(
        question="question",
        context_items=["context"],
        base_url="http://localhost/v1",
        api_key="key",
        model="model",
    )

    assert answer == "answer"
    assert captured["timeout"] is None
