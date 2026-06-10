import json
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph


class GraphIndex:
    def __init__(self, graph_path: Path):
        self.graph_path = graph_path
        self.graph = self._load_graph(graph_path)

    def search(self, question: str, limit: int = 8) -> list[dict[str, Any]]:
        query_terms = _terms(question)
        scored: list[dict[str, Any]] = []
        for node_id, attrs in self.graph.nodes(data=True):
            text = _node_text(node_id, attrs)
            score = _score(query_terms, text, attrs)
            if score > 0:
                scored.append(
                    {
                        "id": str(node_id),
                        "label": str(attrs.get("label") or attrs.get("name") or node_id),
                        "text": text,
                        "path": attrs.get("path") or attrs.get("file") or attrs.get("source"),
                        "score": score,
                    }
                )
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]

    def neighbors(self, node_id: str, limit: int = 5) -> list[str]:
        if node_id not in self.graph:
            return []
        labels: list[str] = []
        for neighbor in list(self.graph.neighbors(node_id))[:limit]:
            attrs = self.graph.nodes[neighbor]
            labels.append(str(attrs.get("label") or attrs.get("name") or neighbor))
        return labels

    @staticmethod
    def _load_graph(graph_path: Path) -> nx.Graph:
        with graph_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if isinstance(payload, dict) and "nodes" in payload and "links" in payload:
            return json_graph.node_link_graph(payload)
        if isinstance(payload, dict) and "nodes" in payload and "edges" in payload:
            return json_graph.node_link_graph({**payload, "links": payload["edges"]})
        raise ValueError("Unsupported graph.json format.")


def _terms(text: str) -> set[str]:
    return {part.lower() for part in "".join(ch if ch.isalnum() else " " for ch in text).split() if len(part) > 2}


def _node_text(node_id: object, attrs: dict[str, Any]) -> str:
    parts = [str(node_id)]
    for key in ("label", "name", "type", "path", "file", "source", "summary", "text", "content"):
        value = attrs.get(key)
        if value:
            parts.append(str(value))
    return " | ".join(parts)


def _score(query_terms: set[str], text: str, attrs: dict[str, Any] | None = None) -> float:
    if not query_terms:
        return 0
    text_terms = _terms(text)
    overlap = query_terms & text_terms
    score = len(overlap) / max(len(query_terms), 1)
    node_type = str((attrs or {}).get("type") or "").lower()
    if node_type == "repository" and query_terms & {"repo", "repository", "project", "summary", "summarize"}:
        score += 0.35
    return score
