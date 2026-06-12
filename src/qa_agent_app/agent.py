import re
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

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
    URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", flags=re.IGNORECASE)

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

    def draft_topic(self, message: str) -> tuple[str, list[str]]:
        sources = self.extract_sources(message)
        name = self._suggest_topic_name(message, sources)
        return name[:120], sources

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
        return QaAgent._summarize_context_without_llm(question, context_items)

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
                    "content": (
                        "Answer using only the supplied graph context. Synthesize the evidence instead of copying raw "
                        "snippets verbatim. Match the user's requested level of technical detail. Prefer repository and "
                        "README context for broad project questions, and use code/config snippets only when they add "
                        "specific technical evidence. If the context is insufficient, say so."
                    ),
                },
                {"role": "user", "content": f"Question: {question}\n\nGraph context:\n{context}"},
            ],
            **kwargs,
        )
        content = response.choices[0].message.content
        return str(content or "")

    def _suggest_topic_name(self, message: str, sources: list[str]) -> str:
        provider = self.llm_provider.lower()
        try:
            if provider == "local":
                return self._generate_topic_name_with_openai_compatible(
                    message=message,
                    sources=sources,
                    base_url=self.local_base_url,
                    api_key=self.local_api_key,
                    model=self.local_model,
                )
            if provider == "openrouter" and self.openrouter_api_key:
                return self._generate_topic_name_with_openai_compatible(
                    message=message,
                    sources=sources,
                    base_url=self.openrouter_base_url,
                    api_key=self.openrouter_api_key,
                    model=self.openrouter_models[0],
                    extra_body={"models": [model for model in self.openrouter_models if model]},
                )
        except Exception:
            pass
        return self._fallback_topic_name(message, sources)

    @staticmethod
    def _generate_topic_name_with_openai_compatible(
        *,
        message: str,
        sources: list[str],
        base_url: str,
        api_key: str,
        model: str,
        extra_body: dict | None = None,
    ) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0, timeout=None)
        source_lines = "\n".join(f"- {source}" for source in sources) or "- none provided"
        kwargs = {"extra_body": extra_body} if extra_body else {}
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You create short topic names for a repository and document QA app. "
                        "Return only the topic name. Prefer the real project or repository name from the source over "
                        "the user's command phrasing. Keep it 2 to 6 words, clear, specific, and without quotes."
                    ),
                },
                {
                    "role": "user",
                    "content": f"User request:\n{message}\n\nDetected sources:\n{source_lines}",
                },
            ],
            **kwargs,
        )
        content = str(response.choices[0].message.content or "").strip()
        cleaned = QaAgent._sanitize_topic_name(content)
        if cleaned:
            return cleaned
        return QaAgent._fallback_topic_name(message, sources)

    @classmethod
    def extract_sources(cls, message: str) -> list[str]:
        seen: set[str] = set()
        results: list[str] = []
        for match in cls.URL_PATTERN.findall(message):
            cleaned = match.rstrip(".,);:!?]}")
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                results.append(cleaned)
        return results

    @staticmethod
    def _sanitize_topic_name(name: str) -> str:
        cleaned = " ".join(name.replace("\n", " ").replace("\r", " ").split()).strip(" \"'")
        if not cleaned:
            return ""
        if len(cleaned) > 120:
            cleaned = cleaned[:120].rstrip()
        return cleaned

    @classmethod
    def _fallback_topic_name(cls, message: str, sources: list[str]) -> str:
        for source in sources:
            inferred = cls._topic_name_from_source(source)
            if inferred:
                return inferred
        stripped = re.sub(
            r"^(please\s+)?(create|make|start|open|add)\s+(a\s+)?topic(\s+(about|for|from))?\s+",
            "",
            message.strip(),
            flags=re.IGNORECASE,
        )
        stripped = cls._sanitize_topic_name(stripped)
        return stripped or "New Topic"

    @staticmethod
    def _topic_name_from_source(source: str) -> str:
        parsed = urlparse(source)
        path_parts = [part for part in parsed.path.split("/") if part]
        if parsed.netloc.lower() in {"github.com", "www.github.com", "gitlab.com", "www.gitlab.com"} and len(path_parts) >= 2:
            return QaAgent._humanize_topic_token(path_parts[1])
        if path_parts:
            return QaAgent._humanize_topic_token(path_parts[-1])
        host = parsed.netloc.split(":")[0].strip()
        return QaAgent._humanize_topic_token(host)

    @staticmethod
    def _humanize_topic_token(token: str) -> str:
        base = re.sub(r"\.git$", "", token.strip(), flags=re.IGNORECASE)
        base = re.sub(r"[_\-]+", " ", base)
        base = re.sub(r"\s+", " ", base).strip()
        if not base:
            return "New Topic"
        words = []
        for part in base.split():
            if part.isupper():
                words.append(part)
            elif any(ch.isdigit() for ch in part):
                words.append(part)
            elif len(part) <= 4 and part.lower() != "topic":
                words.append(part)
            else:
                words.append(part.capitalize())
        return " ".join(words)

    @staticmethod
    def _summarize_context_without_llm(question: str, context_items: list[str]) -> str:
        repo_summaries = [QaAgent._extract_repo_summary(item) for item in context_items]
        repo_summaries = [summary for summary in repo_summaries if summary]
        archive_notice = next((summary for summary in repo_summaries if summary.get("archived_redirect")), None)
        repo_descriptions = [summary for summary in repo_summaries if summary is not archive_notice]
        file_signals = [signal for signal in (QaAgent._extract_file_signal(item) for item in context_items) if signal]
        broad_repo_question = QaAgent._is_broad_repo_question(question)

        lines: list[str] = []
        overview = ""
        purpose = ""
        if repo_descriptions:
            primary = repo_descriptions[0]
            overview = str(primary.get("overview") or "").strip()
            if QaAgent._looks_like_noisy_summary(overview):
                overview = QaAgent._derive_overview_from_context(context_items, str(primary["repo"])) or overview
            if not overview or "repository snapshot" in overview.lower():
                overview = f"{primary['repo']} is the active codebase for this topic."
            lines.append(overview)
            archived_repo = str(archive_notice.get("repo") or "").strip() if archive_notice else ""
            purpose = str(primary.get("purpose") or "").strip() or QaAgent._derive_purpose_from_context(
                context_items,
                overview,
                excluded_repo=archived_repo,
            )
            if purpose:
                lines.append(purpose)
            if primary.get("key_files"):
                lines.append(f"Important entry points in the indexed snapshot include {', '.join(primary['key_files'][:5])}.")

        if archive_notice:
            lines.append(QaAgent._format_archive_notice(archive_notice))

        if file_signals and not broad_repo_question:
            lines.append("Relevant indexed files include:")
            for signal in file_signals[:2]:
                lines.append(f"- {signal}")

        if not lines:
            lines.append("Relevant graph context found:")
            for item in context_items[:3]:
                lines.append(f"- {QaAgent._compact_generic_context(item)}")

        if not lines:
            lines.append("I found graph context for this topic, but the local fallback could not build a readable summary.")

        if broad_repo_question and repo_descriptions:
            concise_lines: list[str] = []
            if overview:
                concise_lines.append(overview)
            else:
                concise_lines.append(lines[0])
            if purpose:
                concise_lines.append(purpose)
            archive_line_index = 3 if purpose else 2
            if archive_notice:
                concise_lines.append(QaAgent._format_archive_notice(archive_notice))
            elif len(lines) > archive_line_index:
                concise_lines.append(lines[archive_line_index])
            return "\n\n".join(concise_lines)

        lines.append("Local LLM endpoint was not used, so this answer was assembled from indexed repository metadata.")
        return "\n".join(lines)

    @staticmethod
    def _is_broad_repo_question(question: str) -> bool:
        return bool(re.search(r"\b(describe|summary|summarize|overview|project|repository|repo)\b", question, flags=re.IGNORECASE))

    @staticmethod
    def _extract_repo_summary(item: str) -> dict[str, object] | None:
        if not item.startswith("repo::"):
            return None
        repo_match = re.match(r"repo::([^|]+)\s+\|\s+([^|]+)\s+\|\s+repository\s+\|", item)
        repo = repo_match.group(2).strip() if repo_match else item.split("|", 2)[1].strip()

        summary_match = re.search(r"Repository snapshot with \d+ files\.\s+Key files:\s+(.+?)\.\s+(.*?)(?:\s+\|\s+related:|$)", item)
        key_files: list[str] = []
        overview = ""
        purpose = ""
        if summary_match:
            key_files = [part.strip() for part in summary_match.group(1).split(",") if part.strip()]
            overview = summary_match.group(2).strip()
        overview = re.sub(r"\s+", " ", overview)
        overview = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", overview)
        overview = re.sub(r"\[\]\(([^)]+)\)", "", overview)
        overview = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", overview)
        overview = re.sub(r"<img[^>]*>", "", overview)
        overview = re.sub(r"^#+\s*", "", overview)
        overview = overview.replace("| Repository", " Repository")
        repo_sentence = QaAgent._extract_repo_named_sentence(overview, repo) or QaAgent._extract_repo_named_sentence(item, repo)
        if repo_sentence:
            overview = repo_sentence
        purpose_sentence = QaAgent._extract_followup_purpose_sentence(overview, item)
        if purpose_sentence:
            purpose = purpose_sentence
        descriptive_sentences = QaAgent._descriptive_sentences(overview)
        if descriptive_sentences:
            if not repo_sentence:
                overview = descriptive_sentences[0]
            if not purpose and len(descriptive_sentences) > 1:
                purpose = descriptive_sentences[1]
        if not purpose:
            purpose_candidates = QaAgent._descriptive_sentences(item)
            for sentence in purpose_candidates:
                if sentence != overview:
                    purpose = sentence
                    break
        if not overview:
            overview = f"{repo} is the active codebase for this topic."
        overview = overview[:420].strip(" -|")
        purpose = purpose[:420].strip(" -|")
        archived_redirect = QaAgent._extract_archive_redirect(item, repo)
        return {"repo": repo, "key_files": key_files, "overview": overview, "purpose": purpose, "archived_redirect": archived_redirect}

    @staticmethod
    def _extract_file_signal(item: str) -> str | None:
        if not item.startswith("file::"):
            return None
        match = re.match(r"file::[^:]+::([^|]+)\s+\|", item)
        path = match.group(1).strip() if match else None
        snippet_match = re.search(r"Content snippet:\s+(.*?)(?:\s+\|\s+related:|$)", item)
        snippet = snippet_match.group(1).strip() if snippet_match else ""
        snippet = re.sub(r"\s+", " ", snippet)
        snippet = re.sub(r"\[[^\]]+\]\(([^)]+)\)", r"\1", snippet)
        snippet = snippet[:180].strip(" -|")
        if not path:
            return None
        if snippet:
            return f"`{path}`: {snippet}"
        return f"`{path}`"

    @staticmethod
    def _compact_generic_context(item: str) -> str:
        cleaned = re.sub(r"\s*\|\s*related:.*$", "", item)
        parts = [part.strip() for part in cleaned.split("|") if part.strip()]
        if len(parts) >= 4:
            head = parts[1]
            tail = parts[-1]
            return f"{head}: {tail}"
        return cleaned[:220]

    @staticmethod
    def _descriptive_sentences(text: str) -> list[str]:
        cleaned = re.sub(r"`+", "", text)
        cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", cleaned)
        cleaned = re.sub(r"\[\]\(([^)]+)\)", " ", cleaned)
        cleaned = re.sub(r"\[[^\]]*\]\(([^)]+)\)", " ", cleaned)
        cleaned = re.sub(r"<img[^>]*>", " ", cleaned)
        cleaned = re.sub(r"https?://\S+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        keywords = (
            " is ",
            " are ",
            " provides ",
            " includes ",
            " supports ",
            " designed ",
            " compliant ",
            " platform",
            " project",
            " solution",
            " framework",
            " library",
            " system",
            " stack",
            " service",
            " toolkit",
            " agent",
            " app",
        )
        selected: list[str] = []
        for sentence in sentences:
            candidate = sentence.strip(" -|")
            if len(candidate) < 24:
                continue
            lowered = candidate.lower()
            if "repository snapshot" in lowered or "key files:" in lowered:
                continue
            if "copyright" in lowered or "spdx-license-identifier" in lowered:
                continue
            if not any(keyword in lowered for keyword in keywords):
                continue
            if candidate.startswith("#") or candidate.startswith("[") or candidate.startswith("!"):
                continue
            selected.append(candidate)
            if len(selected) == 2:
                break
        return selected

    @staticmethod
    def _extract_repo_named_sentence(text: str, repo: str) -> str:
        cleaned = re.sub(r"\s+", " ", text)
        pattern = re.compile(rf"({re.escape(repo)}\s+is\s+.*?[.!?])", flags=re.IGNORECASE)
        match = pattern.search(cleaned)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_followup_purpose_sentence(overview_text: str, source_text: str) -> str:
        for text in (overview_text, source_text):
            cleaned = re.sub(r"\s+", " ", text)
            match = re.search(r"((?:It|This project|This repository)\s+(?:is|provides|includes|supports)\s+.*?[.!?])", cleaned, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    @staticmethod
    def _derive_purpose_from_context(context_items: list[str], overview: str, excluded_repo: str = "") -> str:
        prioritized = sorted(
            context_items,
            key=lambda item: 0 if ((QaAgent._extract_context_path(item) and QaAgent._extract_context_path(item).name.lower().startswith("readme")) or item.lower().startswith("file::") and "::readme" in item.lower()) else 1,
        )
        for item in prioritized:
            repo_name = QaAgent._extract_context_repo(item)
            if excluded_repo and repo_name and repo_name.lower() == excluded_repo.lower():
                continue
            path = QaAgent._extract_context_path(item)
            if path and path.name.lower().startswith("readme") and path.exists():
                for sentence in QaAgent._descriptive_sentences(path.read_text(encoding="utf-8", errors="ignore")):
                    if sentence == overview:
                        continue
                    lowered = sentence.lower()
                    if "repository snapshot" in lowered or "key files:" in lowered:
                        continue
                    if "copyright" in lowered or "spdx-license-identifier" in lowered:
                        continue
                    return sentence
            snippet_match = re.search(r"Content snippet:\s+(.*?)(?:\s+\|\s+related:|$)", item)
            if snippet_match:
                snippet_text = snippet_match.group(1).strip()
                for sentence in QaAgent._descriptive_sentences(snippet_text):
                    if sentence == overview:
                        continue
                    lowered = sentence.lower()
                    if "repository snapshot" in lowered or "key files:" in lowered:
                        continue
                    if "copyright" in lowered or "spdx-license-identifier" in lowered:
                        continue
                    return sentence
            for sentence in QaAgent._descriptive_sentences(item):
                if sentence == overview:
                    continue
                lowered = sentence.lower()
                if "repository snapshot" in lowered or "key files:" in lowered:
                    continue
                if "copyright" in lowered or "spdx-license-identifier" in lowered:
                    continue
                return sentence
        return ""

    @staticmethod
    def _derive_overview_from_context(context_items: list[str], repo: str) -> str:
        prioritized = sorted(
            context_items,
            key=lambda item: 0 if ((QaAgent._extract_context_path(item) and QaAgent._extract_context_path(item).name.lower().startswith("readme")) or item.lower().startswith("file::") and "::readme" in item.lower()) else 1,
        )
        for item in prioritized:
            repo_name = QaAgent._extract_context_repo(item)
            if repo_name and repo_name.lower() != repo.lower():
                continue
            path = QaAgent._extract_context_path(item)
            if path and path.name.lower().startswith("readme") and path.exists():
                readme_text = path.read_text(encoding="utf-8", errors="ignore")
                repo_sentence = QaAgent._extract_repo_named_sentence(readme_text, repo)
                if repo_sentence and not QaAgent._looks_like_noisy_summary(repo_sentence):
                    return repo_sentence
                sentences = QaAgent._descriptive_sentences(readme_text)
                if sentences and not QaAgent._looks_like_noisy_summary(sentences[0]):
                    return sentences[0]
            snippet_match = re.search(r"Content snippet:\s+(.*?)(?:\s+\|\s+related:|$)", item)
            candidate_sources = []
            if snippet_match:
                candidate_sources.append(snippet_match.group(1).strip())
            candidate_sources.append(item)
            for source in candidate_sources:
                repo_sentence = QaAgent._extract_repo_named_sentence(source, repo)
                if repo_sentence and not QaAgent._looks_like_noisy_summary(repo_sentence):
                    return repo_sentence
                sentences = QaAgent._descriptive_sentences(source)
                if sentences:
                    candidate = sentences[0]
                    if not QaAgent._looks_like_noisy_summary(candidate):
                        return candidate
        return ""

    @staticmethod
    def _looks_like_noisy_summary(text: str) -> bool:
        if not text:
            return True
        lowered = text.lower()
        if "repository snapshot" in lowered or "key files:" in lowered:
            return True
        if "spdx-license-identifier" in lowered or "copyright" in lowered:
            return True
        if "repository " in lowered and "project" not in lowered and "platform" not in lowered and "solution" not in lowered:
            return True
        if "[" in text or "](" in text or "http://" in lowered or "https://" in lowered:
            return True
        if text.endswith("permissivel") or len(text) < 28:
            return True
        return False

    @staticmethod
    def _extract_context_path(item: str) -> Path | None:
        parts = [part.strip() for part in item.split("|")]
        if len(parts) < 4:
            return None
        raw_path = parts[3]
        if not raw_path or raw_path.startswith("Repository snapshot"):
            return None
        try:
            return Path(raw_path)
        except Exception:
            return None

    @staticmethod
    def _extract_archive_redirect(text: str, repo: str) -> str:
        lowered = text.lower()
        if "archived" not in lowered and "no longer maintained" not in lowered:
            return ""
        matches = [match.group(0).rstrip(".,") for match in re.finditer(r"https?://[^\s)>\]]+", text, flags=re.IGNORECASE)]
        if not matches:
            return repo
        for candidate in matches:
            lowered_candidate = candidate.lower()
            if "gitlab.com" in lowered_candidate or "github.com" in lowered_candidate:
                return candidate
        return matches[-1]

    @staticmethod
    def _format_archive_notice(summary: dict[str, object]) -> str:
        repo = str(summary.get("repo") or "This repository")
        redirect = str(summary.get("archived_redirect") or "").strip()
        if redirect:
            return f"The original `{repo}` repository in this topic is archived and redirects users to {redirect}."
        return f"The original `{repo}` repository in this topic is archived."

    @staticmethod
    def _extract_context_repo(item: str) -> str:
        if item.startswith("repo::"):
            return item.split("|", 1)[0].replace("repo::", "").strip()
        if item.startswith("file::"):
            match = re.match(r"file::([^:]+)::", item)
            if match:
                return match.group(1).strip()
        return ""
