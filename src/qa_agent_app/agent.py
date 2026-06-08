from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .graph_loader import GraphIndex
from .models import Citation, QuestionResponse, Topic


class AgentState(TypedDict):
    topic: Topic
    question: str
    max_context_items: int
    graph_path: str
    retrieved: list[dict]
    context_items: list[str]
    answer: str
    citations: list[Citation]


class QaAgent:
    def __init__(
        self,
        llm_provider: str = "local",
        *,
        local_base_url: str = "http://127.0.0.1:11434/v1",
        local_api_key: str = "local",
        local_model: str = "llama3.1:8b",
        openrouter_api_key: str | None = None,
        openrouter_base_url: str = "https://openrouter.ai/api/v1",
        openrouter_main_model: str = "openrouter/auto",
        openrouter_reserve_model_1: str = "openai/gpt-4o-mini",
        openrouter_reserve_model_2: str = "google/gemini-flash-1.5",
    ):
        self.llm_provider = llm_provider
        self.local_base_url = local_base_url
        self.local_api_key = local_api_key
        self.local_model = local_model
        self.openrouter_api_key = openrouter_api_key
        self.openrouter_base_url = openrouter_base_url
        self.openrouter_models = [
            openrouter_main_model,
            openrouter_reserve_model_1,
            openrouter_reserve_model_2,
        ]
        self.graph = self._build_graph()

    def answer(self, topic: Topic, question: str, max_context_items: int = 8) -> QuestionResponse:
        if topic.status != "ready" or not topic.graph_path:
            raise ValueError("Topic is not ready. Ingest a source and build the graph first.")
        state = self.graph.invoke(
            {
                "topic": topic,
                "question": question,
                "max_context_items": max_context_items,
                "graph_path": topic.graph_path,
                "retrieved": [],
                "context_items": [],
                "answer": "",
                "citations": [],
            }
        )
        return QuestionResponse(
            topic_id=topic.id,
            question=question,
            answer=state["answer"],
            citations=state["citations"],
            context_items=state["context_items"],
        )

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("compose_context", self._compose_context)
        graph.add_node("generate_answer", self._generate_answer)
        graph.set_entry_point("retrieve")
        graph.add_edge("retrieve", "compose_context")
        graph.add_edge("compose_context", "generate_answer")
        graph.add_edge("generate_answer", END)
        return graph.compile()

    @staticmethod
    def _retrieve(state: AgentState) -> AgentState:
        index = GraphIndex(Path(state["graph_path"]))
        state["retrieved"] = index.search(state["question"], state["max_context_items"])
        for item in state["retrieved"]:
            item["neighbors"] = index.neighbors(item["id"])
        return state

    @staticmethod
    def _compose_context(state: AgentState) -> AgentState:
        items: list[str] = []
        citations: list[Citation] = []
        for result in state["retrieved"]:
            neighbors = ", ".join(result.get("neighbors") or [])
            text = result["text"]
            if neighbors:
                text = f"{text} | related: {neighbors}"
            items.append(text)
            citations.append(
                Citation(
                    label=result["label"],
                    path=result.get("path"),
                    score=float(result["score"]),
                )
            )
        state["context_items"] = items
        state["citations"] = citations
        return state

    def _generate_answer(self, state: AgentState) -> AgentState:
        provider = self.llm_provider.lower()
        if provider == "local":
            answer = self._generate_with_local_provider(state["question"], state["context_items"])
        elif provider == "openrouter":
            answer = self._generate_with_openrouter(state["question"], state["context_items"])
        else:
            raise ValueError("Unsupported LLM provider. Use 'local' or 'openrouter'.")
        state["answer"] = answer
        return state

    def _generate_with_local_provider(self, question: str, context_items: list[str]) -> str:
        try:
            return self._generate_with_openai_compatible(
                question=question,
                context_items=context_items,
                base_url=self.local_base_url,
                api_key=self.local_api_key,
                model=self.local_model,
            )
        except Exception:
            # Keep local mode usable before Ollama, LM Studio, or vLLM is running.
            return self._generate_local_context_answer(question, context_items)

    def _generate_with_openrouter(self, question: str, context_items: list[str]) -> str:
        if not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is required when QA_AGENT_LLM_PROVIDER=openrouter.")
        models = [model for model in self.openrouter_models if model]
        if len(models) != 3:
            raise ValueError("OpenRouter requires one main model and two reserve models.")
        return self._generate_with_openai_compatible(
            question=question,
            context_items=context_items,
            base_url=self.openrouter_base_url,
            api_key=self.openrouter_api_key,
            model=models[0],
            extra_body={"models": models},
        )

    @staticmethod
    def _generate_local_context_answer(question: str, context_items: list[str]) -> str:
        if not context_items:
            return (
                "I could not find matching graph context for this question. "
                "Try rephrasing the question or rebuilding the topic graph with more source files."
            )
        context = "\n".join(f"- {item}" for item in context_items)
        return (
            f"Question: {question}\n\n"
            "Relevant graph context found:\n"
            f"{context}\n\n"
            "Local LLM endpoint was not used. Start the configured local model endpoint for synthesized prose."
        )

    @staticmethod
    def _generate_with_openai_compatible(
        *,
        question: str,
        context_items: list[str],
        base_url: str,
        api_key: str,
        model: str,
        extra_body: dict | None = None,
    ) -> str:
        if not context_items:
            return (
                "I could not find matching graph context for this question. "
                "Try rephrasing the question or rebuilding the topic graph with more source files."
            )
        from openai import OpenAI

        # Do not cap model generation time at the app layer; long generations
        # should complete unless the provider or network closes the request.
        client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0, timeout=None)
        context = "\n".join(f"- {item}" for item in context_items) or "No graph context found."
        kwargs = {"extra_body": extra_body} if extra_body else {}
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Answer using only the supplied graph context. If the context is insufficient, say so.",
                },
                {"role": "user", "content": f"Question: {question}\n\nGraph context:\n{context}"},
            ],
            **kwargs,
        )
        content = response.choices[0].message.content
        return str(content or "")
