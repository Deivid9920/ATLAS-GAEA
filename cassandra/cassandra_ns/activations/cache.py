"""fp16 disk cache for residual activations.

Layout under artifacts/activations/:

  {model}_vectors.f16   one fp16 vector per (statement, layer, mode),
                        concatenated in write order
  {model}_index.csv     id, sha256, model, layer, mode, offset,
                        d_model  (one row per stored vector)
  {model}_logprob.csv   id, sha256, mean_logprob  (|logprob| baseline
                        input; logprob is NEVER a probe feature)

Contracts:
- idempotent: done_ids() reports which dataset ids are fully cached
  (every layer x mode present AND sha256 of the statement text
  matching), so re-runs extract only what is missing;
- fail-loud on stub caches: a present-but-empty (header-only) index or
  logprob file is never consumed as a complete cache. load_index() and
  load_logprobs() raise with the cause, and done_ids() warns loudly on
  stderr before reporting an empty done set (resume then re-extracts
  everything). A header-only CSV left by an interrupted first run is
  therefore impossible to mistake for cached data;
- atomic-safe: vector rows are flushed to disk before their index rows
  are appended, so a killed process never leaves an index entry that
  points at unwritten data;
- load_index(cfg, model) and load_vectors(cfg, model, layer, mode)
  expose the cache to probes and notebooks with per-layer lazy loading
  and vectors returned in the processed-dataset row order.
"""

from __future__ import annotations

import csv
import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

MODES = ("last_token", "mean_pool")

INDEX_FIELDS = ["id", "sha256", "model", "layer", "mode", "offset",
                "d_model"]


def activation_dir(cfg: dict) -> Path:
    return Path("artifacts") / "activations"


def statement_sha256(statement: str) -> str:
    return hashlib.sha256(statement.encode("utf-8")).hexdigest()


def vectors_file(cfg: dict, model: str) -> Path:
    return activation_dir(cfg) / f"{model}_vectors.f16"


def index_file(cfg: dict, model: str) -> Path:
    return activation_dir(cfg) / f"{model}_index.csv"


def logprob_file(cfg: dict, model: str) -> Path:
    return activation_dir(cfg) / f"{model}_logprob.csv"


class ActivationCacheWriter:
    """Incremental fp16 writer with an append-only CSV index."""

    def __init__(self, cfg: dict, model: str, d_model: int,
                 n_capacity: int, layers: list[int]):
        """n_capacity: rows reserved = n_capacity * layers * 2 vectors
        (the full dataset size; the writer appends into it in order)."""
        self.cfg = cfg
        self.model = model
        self.d_model = int(d_model)
        self.layers = [int(l) for l in layers]
        self.n_capacity = int(n_capacity)

        out_dir = activation_dir(cfg)
        out_dir.mkdir(parents=True, exist_ok=True)
        self.vec_path = vectors_file(cfg, model)
        self.idx_path = index_file(cfg, model)
        self.logprob_path = logprob_file(cfg, model)

        rows_capacity = self.n_capacity * len(self.layers) * len(MODES)
        expected_bytes = rows_capacity * self.d_model * 2
        if not self.vec_path.exists() or \
                self.vec_path.stat().st_size != expected_bytes:
            # RAW binary store (no npy header): every read and write in
            # this module uses the same np.memmap layout, so the size
            # check above is the exact capacity in bytes
            arr = np.memmap(self.vec_path, mode="w+", dtype=np.float16,
                            shape=(rows_capacity, self.d_model))
            arr.flush()
            del arr
            self.idx_path.write_text(
                ",".join(INDEX_FIELDS) + "\n", encoding="utf-8")
            if self.logprob_path.exists():
                self.logprob_path.unlink()

        self._vectors = np.memmap(self.vec_path, mode="r+",
                                  dtype=np.float16,
                                  shape=(rows_capacity, self.d_model))
        with self.idx_path.open(newline="", encoding="utf-8") as fh:
            existing = list(csv.DictReader(fh))
        self._next_offset = 0
        if existing:
            self._next_offset = (max(int(r["offset"]) for r in existing)
                                 + self.d_model)
        self._index_fh = self.idx_path.open("a", newline="",
                                            encoding="utf-8")
        self._index_writer = csv.DictWriter(self._index_fh,
                                            fieldnames=INDEX_FIELDS)
        self._logprob_fh = self.logprob_path.open("a", newline="",
                                                  encoding="utf-8")
        self._logprob_writer = csv.DictWriter(
            self._logprob_fh,
            fieldnames=["id", "sha256", "mean_logprob"])
        if self._logprob_fh.tell() == 0:
            self._logprob_writer.writeheader()

    def write(self, sid: str, sha: str, layer: int, mode: str,
              vector: np.ndarray) -> None:
        self._vectors[self._next_offset // self.d_model] = \
            np.asarray(vector).astype(np.float16)
        self._index_writer.writerow({
            "id": sid, "sha256": sha, "model": self.model,
            "layer": int(layer), "mode": mode, "offset": self._next_offset,
            "d_model": self.d_model})
        self._next_offset += self.d_model

    def write_logprob(self, sid: str, sha: str,
                      mean_logprob: float) -> None:
        self._logprob_writer.writerow({"id": sid, "sha256": sha,
                                       "mean_logprob": repr(float(mean_logprob))})

    def flush(self) -> None:
        self._vectors.flush()
        self._index_fh.flush()
        os.fsync(self._index_fh.fileno())
        self._logprob_fh.flush()
        os.fsync(self._logprob_fh.fileno())

    def close(self) -> None:
        self.flush()
        self._index_fh.close()
        self._logprob_fh.close()
        del self._vectors


def done_ids(cfg: dict, model: str, ids: list[str], statements: list[str],
             layers: list[int]) -> set[str]:
    """Dataset ids fully cached: all (layer, mode) rows present and
    sha256 of the statement text unchanged."""
    path = index_file(cfg, model)
    if not path.is_file():
        return set()
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        # Header-only stub (interrupted first run or hand-made cache):
        # never treat it as cached data. Resume semantics apply - the
        # caller re-extracts everything - but the situation is loud.
        print(f"WARNING: {path} exists but has no data rows (header-only "
              "stub): treating the cache as empty and re-extracting "
              "everything", file=sys.stderr)
        return set()
    want = {f"{int(layer)}:{mode}" for layer in layers for mode in MODES}
    by_id: dict[str, tuple[set[str], str]] = {}
    for row in rows:
        entry = by_id.setdefault(row["id"], (set(), row["sha256"]))
        entry[0].add(f"{row['layer']}:{row['mode']}")
    done: set[str] = set()
    for sid, text in zip(ids, statements):
        modes, sha = by_id.get(sid, (set(), ""))
        if modes == want and sha == statement_sha256(text):
            done.add(sid)
    return done


def load_index(cfg: dict, model: str) -> pd.DataFrame:
    """The cache index (id, sha256, model, layer, mode, offset)."""
    path = index_file(cfg, model)
    if not path.is_file():
        raise RuntimeError(
            f"{path} not found: run the extraction for {model} first "
            "(the notebook guard cell does this automatically)")
    df = pd.read_csv(path)
    expected = set(INDEX_FIELDS)
    if not expected <= set(df.columns):
        raise RuntimeError(
            f"{path}: missing columns {expected - set(df.columns)}")
    if df.empty:
        raise RuntimeError(
            f"{path} has a header but no data rows (header-only stub "
            "cache): it is not a complete cache; delete this model's "
            "cache files and re-run the extraction")
    return df


def load_logprobs(cfg: dict, model: str) -> pd.DataFrame:
    """Mean per-token logprob per statement id (the baseline input)."""
    path = logprob_file(cfg, model)
    if not path.is_file():
        raise RuntimeError(
            f"{path} not found: re-run the extraction for {model}")
    df = pd.read_csv(path)
    if df.empty:
        raise RuntimeError(
            f"{path} has a header but no data rows (header-only stub "
            "cache): the |logprob| baseline source is incomplete; "
            "re-run the extraction for this model")
    return df[["id", "mean_logprob"]]


def load_vectors(cfg: dict, model: str, layer: int, mode: str,
                 ids: list[str] | None = None) -> np.ndarray:
    """One (statements x features) fp16 block, dataset row order.

    Rows are ordered by the processed dataset position: position i of
    the returned array corresponds to row i of load_processed(cfg).
    Lazily reads only the pages backing the requested layer and mode.
    """
    index = load_index(cfg, model)
    sel = index[(index["layer"] == int(layer)) & (index["mode"] == mode)]
    if sel.empty:
        raise RuntimeError(
            f"cache has no rows for {model} layer {layer} mode {mode}")
    d_model = int(sel["d_model"].iloc[0])
    offsets = sel.set_index("id")["offset"]

    vectors_path = vectors_file(cfg, model)
    n_rows = vectors_path.stat().st_size // (d_model * 2)
    mem = np.memmap(vectors_path, mode="r", dtype=np.float16,
                    shape=(n_rows, d_model))

    if ids is None:
        from cassandra_ns.data.loader import load_processed
        df = load_processed(cfg)
        ids = df["id"].tolist()
    missing = [sid for sid in ids if sid not in offsets.index]
    if missing:
        raise RuntimeError(
            f"{len(missing)} statements missing from the cache for "
            f"{model} layer {layer} mode {mode} (e.g. {missing[:3]}): "
            "re-run the extraction")
    rows = offsets.loc[ids].to_numpy() // d_model
    return np.asarray(mem[rows])
