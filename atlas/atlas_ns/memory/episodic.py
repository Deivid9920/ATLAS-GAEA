"""Episodic memory (#1) + graph versioning (#3).

Memory records {task -> plan -> result -> lesson}; retrieval is BM25
implemented in pure Python (no index service, CPU-only). PII scrubbing
happens BEFORE insertion — memory never stores personal text.

Graph versioning: every change produces a snapshot id + a diff with a
CAUSE; history is append-only and replayable (mejora #3).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import OrderedDict
from pathlib import Path

from atlas_ns.safety.fencing import is_fenced, strip_fence
from atlas_ns.safety.pii import PIIScrubber

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(str(text).lower())


class EpisodicMemory:
    def __init__(self, config: dict | None = None,
                 scrubber: PIIScrubber | None = None) -> None:
        cfg = (config or {}).get("memory", {})
        self.max_entries = int(cfg.get("max_entries", 10000))
        self.scrubber = scrubber or PIIScrubber(config)
        self._records: OrderedDict[str, dict] = OrderedDict()
        # inverted index: token -> {task_id: term_frequency}
        self._postings: dict[str, dict[str, int]] = {}
        self._doc_len: dict[str, int] = {}

    # -- insertion ---------------------------------------------------------
    def add(self, task_id: str, goal: str, plan: list[str],
            result: str, lesson: str) -> dict:
        """Store one episode; PII scrubbed first (counts audited)."""
        clean_goal, c1 = self.scrubber.scrub(goal)
        clean_result, c2 = self.scrubber.scrub(_unfence(result))
        clean_lesson, c3 = self.scrubber.scrub(lesson)
        record = {"task_id": task_id, "goal": clean_goal,
                  "plan": list(plan), "result": clean_result,
                  "lesson": clean_lesson,
                  "pii_counts": {k: c1.get(k, 0) + c2.get(k, 0)
                                 + c3.get(k, 0) for k in
                                 set(c1) | set(c2) | set(c3)}}
        if task_id in self._records:  # same task updates in place
            self._remove_from_index(task_id)
        self._records[task_id] = record
        self._records.move_to_end(task_id)
        while len(self._records) > self.max_entries:
            oldest, _ = self._records.popitem(last=False)
            self._remove_from_index(oldest)
        self._index(task_id)
        return record

    # -- BM25 (pure python) --------------------------------------------------
    def _index(self, task_id: str) -> None:
        doc = self._records[task_id]
        text = " ".join([doc["goal"], doc["lesson"], doc["result"]])
        tokens = _tokens(text)
        self._doc_len[task_id] = len(tokens)
        for tok in tokens:
            self._postings.setdefault(tok, {})
            self._postings[tok][task_id] = \
                self._postings[tok].get(task_id, 0) + 1

    def _remove_from_index(self, task_id: str) -> None:
        self._doc_len.pop(task_id, None)
        for postings in self._postings.values():
            postings.pop(task_id, None)

    def _bm25_scores(self, query_tokens: list[str], k1: float = 1.5,
                     b: float = 0.75) -> dict[str, float]:
        n_docs = len(self._doc_len)
        if not n_docs:
            return {}
        avg_len = sum(self._doc_len.values()) / n_docs
        scores: dict[str, float] = {}
        for tok in query_tokens:
            postings = self._postings.get(tok)
            if not postings:
                continue
            idf = math.log(1.0 + (n_docs - len(postings) + 0.5)
                           / (len(postings) + 0.5))
            for task_id, tf in postings.items():
                norm = tf * (k1 + 1.0) / (
                    tf + k1 * (1.0 - b + b * self._doc_len[task_id]
                               / max(avg_len, 1e-9)))
                scores[task_id] = scores.get(task_id, 0.0) + idf * norm
        return scores

    def retrieve(self, query: str, k: int = 3) -> list[dict]:
        """Top-k episodes for the query by BM25 (deterministic ties by
        insertion order)."""
        scores = self._bm25_scores(_tokens(query))
        if not scores:
            return []
        order = list(self._records.keys())
        ranked = sorted(scores.items(),
                        key=lambda kv: (-kv[1], order.index(kv[0])))
        return [dict(self._records[tid], bm25=round(score, 4))
                for tid, score in ranked[:k]]

    def __len__(self) -> int:
        return len(self._records)


def _unfence(text: str) -> str:
    """Tool outputs arrive fenced; store the payload (still scrubbed)."""
    if is_fenced(text):
        return strip_fence(text)
    return text


# -- graph versioning (#3) ---------------------------------------------------
class GraphVersions:
    """Append-only snapshot history with caused diffs."""

    def __init__(self) -> None:
        self.graph = {"nodes": [], "edges": []}
        self.history: list[dict] = []
        self._gen = 0

    @staticmethod
    def _digest(graph: dict) -> str:
        return hashlib.sha256(json.dumps(
            graph, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]

    def apply_change(self, cause: str, add_nodes: list[dict] | None = None,
                     add_edges: list[dict] | None = None,
                     drop_node_ids: list[str] | None = None) -> dict:
        """Apply one change; record {gen, cause, diff, snapshot_hash}."""
        diff: dict = {"add_nodes": [], "add_edges": [],
                      "drop_node_ids": list(drop_node_ids or [])}
        existing = {n.get("id") for n in self.graph["nodes"]}
        for node in add_nodes or []:
            if node.get("id") not in existing:
                self.graph["nodes"].append(dict(node))
                diff["add_nodes"].append(node.get("id"))
                existing.add(node.get("id"))
        edge_set = {(e.get("source"), e.get("target"), e.get("rel"))
                    for e in self.graph["edges"]}
        for edge in add_edges or []:
            key = (edge.get("source"), edge.get("target"), edge.get("rel"))
            if key not in edge_set:
                self.graph["edges"].append(dict(edge))
                diff["add_edges"].append(key)
                edge_set.add(key)
        if diff["drop_node_ids"]:
            drop = set(diff["drop_node_ids"])
            self.graph["nodes"] = [n for n in self.graph["nodes"]
                                   if n.get("id") not in drop]
            self.graph["edges"] = [e for e in self.graph["edges"]
                                   if e.get("source") not in drop
                                   and e.get("target") not in drop]
        self._gen += 1
        entry = {"gen": self._gen, "cause": cause, "diff": diff,
                 "snapshot_hash": self._digest(self.graph)}
        self.history.append(entry)
        return entry

    def snapshot_hash(self) -> str:
        return self._digest(self.graph)

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(
            {"graph": self.graph, "history": self.history},
            ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "GraphVersions":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        store = cls()
        store.graph = data["graph"]
        store.history = data["history"]
        store._gen = data["history"][-1]["gen"] if data["history"] else 0
        return store
