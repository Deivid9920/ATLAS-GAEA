"""Tamper-evident audit chain. Immutable anchor.

Each entry: {seq, prev, event, hash} where hash = sha256(prev_hash +
canonical({seq, prev, event})). No timestamps inside the hash (the
caller embeds them in the event when wanted): the chain is fully
deterministic and testable. verify() walks the whole chain; one flipped
byte anywhere breaks it — the compliance receipt the niche buys.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

GENESIS = "0" * 64


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def _hash(seq: int, prev: str, event: dict) -> str:
    return hashlib.sha256(
        (prev + canonical({"seq": seq, "prev": prev, "event": event}))
        .encode("utf-8")).hexdigest()


class AuditChain:
    def __init__(self) -> None:
        self.entries: list[dict] = []
        self._prev = GENESIS

    def append(self, event: dict) -> dict:
        seq = len(self.entries)
        entry = {"seq": seq, "prev": self._prev, "event": event,
                 "hash": _hash(seq, self._prev, event)}
        self.entries.append(entry)
        self._prev = entry["hash"]
        return entry

    def verify(self) -> tuple[bool, int | None]:
        prev = GENESIS
        for entry in self.entries:
            expected = _hash(entry.get("seq"), prev, entry.get("event") or {})
            # .get everywhere: a MISSING field is itself tampering and
            # must report (False, seq), never raise (anchor defect fix #2).
            if entry.get("prev") != prev or entry.get("hash") != expected:
                return False, entry["seq"]
            prev = entry["hash"]
        return True, None

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            "\n".join(canonical(e) for e in self.entries) + "\n",
            encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "AuditChain":
        chain = cls()
        text = Path(path).read_text(encoding="utf-8").strip()
        if text:
            chain.entries = [json.loads(line) for line in text.splitlines()]
            chain._prev = chain.entries[-1]["hash"] if chain.entries \
                else GENESIS
        return chain
