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

    assert "Relevant graph context found:" in response.answer
    assert "OAuth token validation" in response.answer
    assert response.citations[0].label == "Authentication"


def test_local_fallback_summarizes_repository_nodes():
    context_items = [
        (
            "repo::srsran-project | srsran-project | repository | data\\topics\\topic\\source\\srsran-project | "
            "Repository snapshot with 14 files. Key files: README.md, _github/discussions.md. "
            "> Project transition notice: srsRAN Project is now [OCUDU](https://ocudu.org). "
            "This repository will be archived and is no longer maintained. | related: README.md"
        ),
        (
            "repo::ocudu | ocudu | repository | data\\topics\\topic\\source\\ocudu | "
            "Repository snapshot with 5702 files. Key files: CMakeLists.txt, README.md, apps/CMakeLists.txt. "
            "OCUDU is a permissively-licensed, open-source 5G CU/DU project designed for commercial deployment. "
            "It is a complete radio access network (RAN) solution compliant with 3GPP and O-RAN Alliance specifications and includes the full L1/2/3 stack. "
            "| related: CMakeLists.txt, README.md"
        ),
        (
            "file::ocudu::README.md | README.md | document | data\\topics\\topic\\source\\ocudu\\README.md | "
            "ocudu file README.md | Repository ocudu. File README.md. "
            "Content snippet: OCUDU is a permissively-licensed, open-source 5G CU/DU project designed for commercial deployment."
        ),
    ]

    answer = QaAgent._generate_local_context_answer("describe this project", context_items)

    assert "5g cu/du project" in answer.lower()
    assert "radio access network" in answer.lower()
    assert "redirects users to https://ocudu.org" in answer
    assert "Local LLM endpoint" not in answer


def test_local_fallback_extracts_generic_repo_purpose():
    context_items = [
        (
            "repo::acmeflow | AcmeFlow | repository | data\\topics\\topic\\source\\acmeflow | "
            "Repository snapshot with 240 files. Key files: README.md, docs/architecture.md, package.json. "
            "AcmeFlow is a workflow orchestration platform for data pipelines. "
            "It provides scheduling, retries, worker coordination, and API-triggered runs for production jobs. "
            "| related: README.md, package.json"
        )
    ]

    answer = QaAgent._generate_local_context_answer("what does this project do", context_items)

    assert "workflow orchestration platform" in answer.lower()
    assert "scheduling, retries, worker coordination" in answer.lower()


def test_local_fallback_cleans_badge_heavy_repo_summary():
    context_items = [
        (
            "repo::ocudu | ocudu | repository | data\\topics\\topic\\source\\ocudu | "
            "Repository snapshot with 5702 files. Key files: CMakeLists.txt, README.md. "
            "# The OCUDU Project [![Pipeline](https://gitlab.com/ocudu/ocudu/-/pipelines?scope=branches)] "
            "[![Documentation](https://docs.ocudu.org)] [![License](https://spdx.org/licenses/BSD-3-Clause-Open-MPI.html)] "
            "OCUDU is a permissively-licensed, open-source 5G CU/DU project designed for commercial deployment. "
            "It is a complete radio access network (RAN) solution compliant with 3GPP and O-RAN Alliance specifications and includes the full L1/2/3 stack. "
            "| related: CMakeLists.txt, README.md"
        )
    ]

    answer = QaAgent._generate_local_context_answer("what this project do", context_items)

    assert "# The OCUDU Project" not in answer
    assert "https://gitlab.com/ocudu/ocudu/-/pipelines" not in answer
    assert "5g cu/du project" in answer.lower()
    assert "full l1/2/3 stack" in answer.lower()


def test_broad_repo_question_passes_clean_context_to_llm(tmp_path, monkeypatch):
    captured = {}

    def fake_generate(**kwargs):
        captured.update(kwargs)
        return "LLM processed the graph context."

    monkeypatch.setattr(QaAgent, "_generate_with_openai_compatible", staticmethod(fake_generate))
    graph = Graph()
    graph.add_node(
        "repo::acmenet",
        label="acmenet",
        type="repository",
        path=str(tmp_path / "source" / "acmenet"),
        summary=(
            "Repository snapshot with 5702 files. Key files: CMakeLists.txt, README.md. "
            "AcmeNet is an open-source network control project designed for production deployment. "
            "It provides topology discovery, policy validation, and runtime configuration for distributed network services."
        ),
    )
    graph.add_node(
        "file::acmenet::CMakeLists.txt",
        label="CMakeLists.txt",
        type="config",
        path=str(tmp_path / "source" / "acmenet" / "CMakeLists.txt"),
        summary='This is bad practice.") endif (${CMAKE_SOURCE_DIR} STREQUAL ${CMAKE_BINARY_DIR})',
    )
    graph.add_edge("repo::acmenet", "file::acmenet::CMakeLists.txt")
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

    answer = QaAgent().answer(topic, "what is this project do").answer

    assert answer == "LLM processed the graph context."
    assert captured["question"] == "what is this project do"
    assert any(item.startswith("repo::acmenet") for item in captured["context_items"])
    assert all("This is bad practice" not in item for item in captured["context_items"])


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
