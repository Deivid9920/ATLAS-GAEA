"""Activation cache contract tests: round-trip fidelity, batch
consistency and idempotency.

Runs against a tiny random-weight HookedTransformer (deterministic
under seed 42, no checkpoint download) so the contracts are exercised
in seconds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from cassandra_ns.activations import cache, extract
from cassandra_ns.activations.extract import extract_statements

STATEMENTS = [
    "Tiraspol is a city in Transnistria.",
    "The kangaroo has a pouch for carrying its young.",
    "Cerium appears in its standard state as Solid.",
    "Nikolai Basov invented the molecular laser.",
    "The sun is a star.",
]

IDS = [f"cities:{i:05d}" for i in range(len(STATEMENTS))]
LAYERS = [0, 1]

CFG = {
    "seed": 42,
    "data": {"cache_dir": "data/processed"},
}


@pytest.fixture(autouse=True)
def _isolate_fs(tmp_path, monkeypatch):
    """Run every test in its own tmp dir: the cache paths are relative
    (artifacts/activations under the repo root), so chdir is the
    isolation boundary. The module-scoped tiny model never touches it."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture(scope="module")
def tiny_hooker():
    from transformer_lens import HookedTransformer, HookedTransformerConfig

    torch.manual_seed(42)
    cfg = HookedTransformerConfig(
        n_layers=2, d_model=32, n_heads=2, d_head=16, d_mlp=64,
        d_vocab=50257, n_ctx=64, act_fn="gelu", tokenizer_name="gpt2")
    return HookedTransformer(cfg)


@pytest.fixture()
def tmp_cfg(tmp_path):
    return {"seed": 42, "data": {"cache_dir": str(tmp_path / "processed")}}, \
        tmp_path


def test_fp16_round_trip_matches_reference(tmp_path) -> None:
    """A vector read back from the cache equals its fp16-cast reference
    within 1e-4: the cache adds no error beyond the storage dtype."""
    rng = np.random.default_rng(42)
    original = rng.normal(size=(16, 32)).astype(np.float32)

    cfg = {"seed": 42, "data": {"cache_dir": "data/processed"}}
    writer = cache.ActivationCacheWriter(cfg, "gpt2", d_model=32,
                                         n_capacity=4, layers=LAYERS)
    try:
        for i, vec in enumerate(original):
            writer.write(f"id:{i:05d}", f"sha{i}", LAYERS[i % 2],
                         "last_token", vec)
        writer.flush()
        df_index = cache.load_index(cfg, "gpt2")
        assert len(df_index) == 16
        even_ids = [f"id:{i:05d}" for i in range(0, 16, 2)]
        got = cache.load_vectors(cfg, "gpt2", 0, "last_token",
                                 ids=even_ids)
    finally:
        writer.close()
    reference = original[::2].astype(np.float16).astype(np.float32)
    assert np.allclose(got.astype(np.float32), reference,
                       rtol=1e-4, atol=1e-4)


def test_reconstructed_cache_matches_direct_forward(
        tiny_hooker, tmp_cfg) -> None:
    """The activation reconstructed from the cache equals the direct
    forward pass of the same statement alone (fp16 storage tolerance)."""
    cfg, _ = tmp_cfg
    writer = cache.ActivationCacheWriter(cfg, "gpt2", d_model=32,
                                         n_capacity=len(STATEMENTS),
                                         layers=LAYERS)
    try:
        extract_statements(tiny_hooker, IDS, STATEMENTS, LAYERS, writer)
        vectors = cache.load_vectors(cfg, "gpt2", 1, "last_token", ids=IDS)
    finally:
        writer.close()

    bos = tiny_hooker.tokenizer.bos_token_id
    for i, text in enumerate(STATEMENTS):
        tokens = torch.tensor([[bos] + tiny_hooker.tokenizer(
            text, add_special_tokens=False)["input_ids"]])
        _, c = tiny_hooker.run_with_cache(tokens)
        direct = c["blocks.1.hook_resid_post"][0, -1].numpy()
        assert np.allclose(vectors[i].astype(np.float32), direct,
                           rtol=2e-3, atol=2e-3), \
            f"cache reconstruction diverged for {IDS[i]}"


def test_statement_alone_equals_inside_batch(tiny_hooker, tmp_cfg) -> None:
    """A statement processed inside a padded batch produces the same
    last-token activation as alone (fp32 compute, 1e-4 tolerance)."""
    bos = tiny_hooker.tokenizer.bos_token_id
    encoded = [[bos] + tiny_hooker.tokenizer(
        t, add_special_tokens=False)["input_ids"] for t in STATEMENTS]

    def last_token_activations(rows: list[int]) -> np.ndarray:
        batch = [encoded[i] for i in rows]
        lens = [len(e) for e in batch]
        max_len = max(lens)
        tokens = torch.full((len(batch), max_len), bos, dtype=torch.long)
        for r, e in enumerate(batch):
            tokens[r, :len(e)] = torch.tensor(e)
        _, c = tiny_hooker.run_with_cache(tokens)
        out = []
        for r in range(len(batch)):
            out.append(
                c["blocks.1.hook_resid_post"][r, lens[r] - 1].numpy())
        return np.stack(out)

    in_batch = last_token_activations(list(range(len(STATEMENTS))))
    for i in range(len(STATEMENTS)):
        alone = last_token_activations([i])[0]
        assert np.allclose(in_batch[i], alone, rtol=1e-4, atol=1e-4), \
            f"batch padding changed the activation of {IDS[i]}"


def test_idempotency_second_run_skips_everything(
        tiny_hooker, tmp_cfg, capsys) -> None:
    """A second extraction run skips statements already cached: the
    index hash after run 2 equals the hash after run 1."""
    cfg, _ = tmp_cfg
    for _ in range(2):
        writer = cache.ActivationCacheWriter(
            cfg, "gpt2", d_model=32, n_capacity=len(STATEMENTS),
            layers=LAYERS)
        try:
            done = cache.done_ids(cfg, "gpt2", IDS, STATEMENTS, LAYERS)
            todo_ids = [s for i, s in enumerate(IDS)
                        if s not in done]
            todo_texts = [t for i, t in enumerate(STATEMENTS)
                          if IDS[i] not in done]
            if todo_ids:
                extract_statements(tiny_hooker, todo_ids, todo_texts,
                                   LAYERS, writer)
        finally:
            writer.close()
    first = cache.load_index(cfg, "gpt2")
    assert len(first) == len(STATEMENTS) * len(LAYERS) * 2
    assert done == set(IDS)

    hash_a = pd.util.hash_pandas_object(first, index=True).sum()
    writer = cache.ActivationCacheWriter(cfg, "gpt2", d_model=32,
                                         n_capacity=len(STATEMENTS),
                                         layers=LAYERS)
    writer.close()
    second = cache.load_index(cfg, "gpt2")
    hash_b = pd.util.hash_pandas_object(second, index=True).sum()
    assert hash_a == hash_b, "second run modified the cache index"


def test_load_vectors_reassembles_dataset_order(tmp_cfg, tiny_hooker) -> None:
    """load_vectors returns rows in the dataset order given by ids,
    independent of the write order inside the file."""
    cfg, _ = tmp_cfg
    writer = cache.ActivationCacheWriter(cfg, "gpt2", d_model=32,
                                         n_capacity=len(STATEMENTS),
                                         layers=LAYERS)
    try:
        extract_statements(tiny_hooker, IDS, STATEMENTS, LAYERS, writer)
    finally:
        writer.close()
    reversed_ids = list(reversed(IDS))
    vec_rev = cache.load_vectors(cfg, "gpt2", 0, "last_token",
                                 ids=reversed_ids)
    vec_fwd = cache.load_vectors(cfg, "gpt2", 0, "last_token", ids=IDS)
    assert np.allclose(vec_rev.astype(np.float32),
                       vec_fwd[::-1].astype(np.float32))


def test_header_only_index_is_never_a_complete_cache(tmp_path,
                                                     capsys) -> None:
    """Regression (v1.2.0 finding): a header-only index left by an
    interrupted first run must never be consumed as a complete cache.
    load_index fails loud with the cause, and done_ids warns loudly on
    stderr while keeping resume semantics (empty done set)."""
    cfg = {"seed": 42, "data": {"cache_dir": "data/processed"}}
    index = cache.index_file(cfg, "gpt2")
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(",".join(cache.INDEX_FIELDS) + "\n",
                     encoding="utf-8")
    with pytest.raises(RuntimeError, match="no data rows"):
        cache.load_index(cfg, "gpt2")
    assert cache.done_ids(cfg, "gpt2", IDS, STATEMENTS, LAYERS) == set()
    assert "header-only stub" in capsys.readouterr().err


def test_header_only_logprob_cache_is_rejected_loudly(tmp_path) -> None:
    """Regression (v1.2.0 finding): a header-only logprob CSV is not a
    usable baseline source; load_logprobs raises with the cause instead
    of returning an empty frame downstream."""
    cfg = {"seed": 42, "data": {"cache_dir": "data/processed"}}
    logprob = cache.logprob_file(cfg, "gpt2")
    logprob.parent.mkdir(parents=True, exist_ok=True)
    logprob.write_text("id,sha256,mean_logprob\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="no data rows"):
        cache.load_logprobs(cfg, "gpt2")
