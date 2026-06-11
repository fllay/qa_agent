import json
from collections import Counter
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph

from .models import TopicGraphEdge, TopicGraphNode, TopicGraphResponse


FALLBACK_PREVIEW_MAX_NODES = 520
FALLBACK_PREVIEW_MAX_EDGES = 900


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


def load_graph_preview(
    topic_id: str,
    topic_name: str,
    graph_path: Path,
    *,
    max_nodes: int | None = None,
    max_edges: int | None = None,
) -> TopicGraphResponse:
    graph = GraphIndex._load_graph(graph_path)
    kind_counts = Counter(
        str(graph.nodes[node_id].get("type") or graph.nodes[node_id].get("file_type") or "").lower() or "other"
        for node_id in graph.nodes
    )
    ordered_nodes = sorted(
        graph.nodes,
        key=lambda node_id: (
            -graph.degree[node_id],
            str(graph.nodes[node_id].get("label") or graph.nodes[node_id].get("name") or node_id).lower(),
        ),
    )
    sampled_node_ids = _sample_node_ids(graph, ordered_nodes, max_nodes=max_nodes)
    sampled_set = set(sampled_node_ids)

    nodes = [
        TopicGraphNode(
            id=str(node_id),
            label=str(
                graph.nodes[node_id].get("label")
                or graph.nodes[node_id].get("name")
                or graph.nodes[node_id].get("path")
                or node_id
            ),
            kind=str(graph.nodes[node_id].get("type") or graph.nodes[node_id].get("file_type") or ""),
            degree=int(graph.degree[node_id]),
        )
        for node_id in sampled_node_ids
    ]

    edges: list[TopicGraphEdge] = []
    for source, target, attrs in graph.edges(data=True):
        if source not in sampled_set or target not in sampled_set:
            continue
        edges.append(
            TopicGraphEdge(
                source=str(source),
                target=str(target),
                label=str(attrs.get("relation") or attrs.get("label") or ""),
            )
        )
        if max_edges is not None and len(edges) >= max_edges:
            break

    return TopicGraphResponse(
        topic_id=topic_id,
        topic_name=topic_name,
        graph_path=str(graph_path),
        graph_kind="fallback" if graph_path.name == "fallback-graph.json" else "graphify",
        total_nodes=graph.number_of_nodes(),
        total_edges=graph.number_of_edges(),
        kind_counts=dict(kind_counts),
        sampled=len(sampled_node_ids) < graph.number_of_nodes() or len(edges) < graph.number_of_edges(),
        nodes=nodes,
        edges=edges,
    )


def graph_preview_limits(graph_path: Path) -> tuple[int | None, int | None]:
    return None, None


def _sample_node_ids(graph: nx.Graph, ordered_nodes: list[object], *, max_nodes: int | None) -> list[object]:
    if max_nodes is None or len(ordered_nodes) <= max_nodes:
        return ordered_nodes

    grouped: dict[str, list[object]] = {
        "repository": [],
        "code": [],
        "config": [],
        "document": [],
        "other": [],
    }
    for node_id in ordered_nodes:
        kind = str(graph.nodes[node_id].get("type") or graph.nodes[node_id].get("file_type") or "").lower()
        family = kind if kind in grouped else "other"
        grouped[family].append(node_id)

    selected: list[object] = []
    selected_set: set[object] = set()

    def take_from(family: str, count: int) -> None:
        if count <= 0:
            return
        for node_id in grouped[family][:count]:
            if node_id in selected_set:
                continue
            selected.append(node_id)
            selected_set.add(node_id)

    take_from("repository", len(grouped["repository"]))
    remaining = max(max_nodes - len(selected), 0)
    quotas = {
        "code": int(remaining * 0.56),
        "config": int(remaining * 0.18),
        "document": int(remaining * 0.16),
        "other": remaining,
    }
    quotas["other"] -= quotas["code"] + quotas["config"] + quotas["document"]

    for family in ("code", "config", "document", "other"):
        take_from(family, quotas[family])

    if len(selected) < max_nodes:
        for node_id in ordered_nodes:
            if node_id in selected_set:
                continue
            selected.append(node_id)
            selected_set.add(node_id)
            if len(selected) >= max_nodes:
                break

    return selected
