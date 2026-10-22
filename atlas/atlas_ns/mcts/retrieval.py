"""Hybrid retrieval (#2, #4): pure-Python BM25 over profile docs +
symbolic-graph expansion with per-triplet citations.

Contradictions are DECLARED, never hidden: when two sources (or a doc
and a graph triplet) conflict, the result carries a contradictions
list so the composite can hard-block instead of averaging lies.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(str(text).lower())


class Bm25Index:
    """Classic Okapi BM25 over in-memory documents (CPU-only)."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.docs: list[dict] = []
        self._postings: dict[str, dict[int, int]] = {}
        self._len: list[int] = []

    def add(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        idx = len(self.docs)
        tokens = _tokens(text)
        self.docs.append({"id": doc_id, "text": text,
                          "metadata": metadata or {}})
        self._len.append(len(tokens))
        for tok in tokens:
            posting = self._postings.setdefault(tok, {})
            posting[idx] = posting.get(idx, 0) + 1

    def search(self, query: str, k: int = 3) -> list[dict]:
        n = len(self.docs)
        if not n:
            return []
        avg_len = sum(self._len) / n
        scores: dict[int, float] = {}
        for tok in _tokens(query):
            posting = self._postings.get(tok)
            if not posting:
                continue
            idf = math.log(1.0 + (n - len(posting) + 0.5)
                           / (len(posting) + 0.5))
            for i, tf in posting.items():
                norm = tf * (self.k1 + 1.0) / (
                    tf + self.k1 * (1.0 - self.b
                                    + self.b * self._len[i]
                                    / max(avg_len, 1e-9)))
                scores[i] = scores.get(i, 0.0) + idf * norm
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [dict(self.docs[i], bm25=round(s, 4))
                for i, s in ranked[:k]]


class HybridRetriever:
    """BM25 docs + graph triplets, with citations and contradictions."""

    def __init__(self, docs_dir: Path, graph_path: Path | None = None) -> None:
        self.index = Bm25Index()
        docs_dir = Path(docs_dir)
        if docs_dir.is_dir():
            for path in sorted(docs_dir.glob("*.md")):
                self.index.add(path.stem,
                               path.read_text(encoding="utf-8"),
                               {"source": path.name})
        self.graph = {"nodes": [], "edges": []}
        if graph_path is not None and Path(graph_path).is_file():
            self.graph = json.loads(
                Path(graph_path).read_text(encoding="utf-8"))
        self._node_by_triplet = {
            (str(n.get("subject", "")).lower(),
             str(n.get("predicate", "")).lower(),
             str(n.get("object", "")).lower()):
                n for n in self.graph.get("nodes", [])}

    def query_graph(self, query: str) -> dict:
        """Triplets whose subject/object tokens overlap the query."""
        q_tokens = set(_tokens(query))
        citations: list[dict] = []
        contradictions: list[dict] = []
        edge_by_source = {}
        for edge in self.graph.get("edges", []):
            edge_by_source.setdefault(edge["source"], []).append(edge)
        for key, node in self._node_by_triplet.items():
            words = set(key[0].split("_")) | set(key[2].split("_"))
            if words & q_tokens:
                tid = node.get("id", "?")
                citations.append({"triplet_id": tid,
                                  "subject": node.get("subject"),
                                  "predicate": node.get("predicate"),
                                  "object": node.get("object")})
                for edge in edge_by_source.get(tid, []):
                    if edge.get("rel") == "contradicts":
                        contradictions.append({
                            "triplet_id": tid,
                            "conflicts_with": edge["target"],
                            "declared": True})
        return {"citations": citations, "contradictions": contradictions}

    def search(self, query: str, k: int = 2) -> dict:
        docs = self.index.search(query, k=k)
        graph_hit = self.query_graph(query)
        return {"docs": docs, **graph_hit}

    def context_block(self, query: str, k: int = 2) -> str:
        """Fence-ready retrieval context with explicit citations.

        Embeds the matched doc's CODE BLOCK (not the raw head): the
        nano's max_seq (256 tokens) demands tight context.
        """
        from atlas_ns.safety.fencing import fence

        import re

        result = self.search(query, k=k)
        lines: list[str] = []
        for doc in result["docs"]:
            blocks = re.findall(r"```python\n(.*?)```", doc["text"], re.S)
            code = blocks[-1].strip() if blocks else doc["text"][:200]
            lines.append(f"[doc:{doc['id']}]\n```python\n{code}\n```")
        for cite in result["citations"][:2]:   # budget: nano window
            lines.append(f"[graph:{cite['triplet_id']}] "
                         f"{cite['subject']} {cite['predicate']} "
                         f"{cite['object']}")
        for contra in result["contradictions"][:2]:
            lines.append(f"[CONTRADICTION] {contra['triplet_id']} "
                         f"conflicts with {contra['conflicts_with']}")
        if not lines:
            return ""
        return fence("\n".join(lines))
