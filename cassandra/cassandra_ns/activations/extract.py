"""TransformerLens residual extraction for CASSANDRA.

For each configured layer the hooks capture "blocks.{L}.hook_resid_post"
of a batch of statements. Two feature modes are cached per layer:

- last_token: the residual vector of the statement's final real token
  (padding positions are never read; real lengths are tracked);
- mean_pool: the mean of the residual vectors over the statement's real
  tokens (BOS excluded).

Everything is computed in fp32 on CPU (fp16 on CUDA), batch 32. A
statement processed alone must produce the same activation as inside a
batch - right padding with causal attention leaves real positions
untouched, and the tests pin that property at 1e-4.

The mean per-token logprob of the statement under the same model is
cached alongside as the |logprob| BASELINE input. The logprob is a
comparison baseline only, never a probe feature.

Public API: extract_statements(...) fills an ActivationCacheWriter for
the ids it is given (resume = pass only the missing ids, see
cache.done_ids); load_hooked(name) returns the pinned HookedTransformer.
"""

from __future__ import annotations

import time

import numpy as np
import torch
from tqdm import tqdm

from cassandra_ns.activations.cache import (MODES, ActivationCacheWriter,
                                            statement_sha256)

BATCH_SIZE = 32


def extract_statements(hooker, ids: list[str], statements: list[str],
                       layers: list[int], writer: ActivationCacheWriter,
                       batch_size: int = BATCH_SIZE,
                       capture_logprob: bool = True,
                       device: str = "cpu") -> None:
    """Extract and cache activations for the given statements.

    hooker: a TransformerLens HookedTransformer. ids/statements: the
    processed dataset's statement ids and texts (a subset on resume).
    Position in the vectors block is assigned by the writer; the index
    keeps the dataset id so load_vectors can reassemble row order.
    """
    assert len(ids) == len(statements)
    bos_id = hooker.tokenizer.bos_token_id
    if bos_id is None:
        bos_id = hooker.tokenizer.eos_token_id
    pad_id = bos_id

    # tokenize once: no padding here, BOS prepended for a stable left
    # context; truncation respects the model context window
    encoded = []
    for text in statements:
        ids_tok = hooker.tokenizer(text, add_special_tokens=False)["input_ids"]
        encoded.append([bos_id] + ids_tok[-(hooker.cfg.n_ctx - 1):])

    t0 = time.time()
    done = 0
    with torch.no_grad():
        for start in range(0, len(ids), batch_size):
            batch_ids = ids[start:start + batch_size]
            batch_texts = statements[start:start + batch_size]
            batch_enc = encoded[start:start + batch_size]

            lens = torch.tensor([len(e) for e in batch_enc])
            max_len = int(lens.max())
            tokens = torch.full((len(batch_enc), max_len), pad_id,
                                dtype=torch.long)
            for i, e in enumerate(batch_enc):
                tokens[i, :len(e)] = torch.tensor(e)

            logits, cache = hooker.run_with_cache(
                tokens.to(device),
                names_filter=lambda name: name.endswith("hook_resid_post")
                and any(f"blocks.{layer}." in name for layer in layers))
            shas = [statement_sha256(t) for t in batch_texts]

            for layer in layers:
                resid = cache[f"blocks.{layer}.hook_resid_post"].float()
                for row in range(len(batch_enc)):
                    length = int(lens[row])
                    last = resid[row, length - 1]
                    mean = resid[row, 1:length].mean(dim=0)
                    writer.write(batch_ids[row], shas[row],
                                 layer, MODES[0], last.numpy())
                    writer.write(batch_ids[row], shas[row],
                                 layer, MODES[1], mean.numpy())
            del cache

            if capture_logprob:
                # logsumexp + gather instead of a full log_softmax:
                # avoids a second full-vocab copy (the logits tensor is
                # 32 x seq x vocab fp32)
                lse = torch.logsumexp(logits.float(), dim=-1)
                for row in range(len(batch_enc)):
                    length = int(lens[row])
                    targets = tokens[row, 1:length].to(device)
                    tok_logits = logits[row, torch.arange(length - 1),
                                        targets]
                    lp = tok_logits.float() - lse[row, :length - 1]
                    writer.write_logprob(batch_ids[row], shas[row],
                                         float(lp.mean().cpu()))
            del logits

            done += len(batch_ids)
            elapsed = time.time() - t0
            rate = done / max(elapsed, 1e-9)
            eta = (len(ids) - done) / max(rate, 1e-9)
            tqdm.write(
                f"    extracted {done}/{len(ids)} statements "
                f"({rate:.1f}/s, ETA {eta/60:.1f} min)")
            writer.flush()


def load_hooked(model_name: str, device: str = "cpu",
                 reuse_cache: bool = True):
    """Load a configured model through TransformerLens.

    No activation folding / weight centering: the raw resid_post of the
    original checkpoint is the object of study, and skipping the folds
    keeps the loaded weights byte-equal to the HF checkpoint.

    The TransformerLens conversion of the larger checkpoints takes
    minutes on CPU, so the converted model is pickled once under
    artifacts/activations/ and reloaded from there afterwards (the
    pickle is a local cache: it is gitignored and regenerable by
    deleting it).
    """
    import gc
    from pathlib import Path as _Path

    import torch as _torch
    from transformer_lens import HookedTransformer

    cache_path = _Path("artifacts") / "activations" / \
        f"{model_name.replace('/', '_')}_hooked.pt"
    if reuse_cache and cache_path.is_file():
        # mmap=True: pages come from the file lazily instead of holding
        # a second full copy of the weights in RAM
        hooker = _torch.load(cache_path, map_location=device,
                             weights_only=False, mmap=True)
        hooker.eval()
        return hooker

    _torch.set_grad_enabled(False)
    hooker = HookedTransformer.from_pretrained(
        model_name,
        device=device,
        fold_ln=False,
        center_writing_weights=False,
        center_unembed=False,
        dtype=_torch.float32,
    )
    hooker.eval()
    if reuse_cache:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(".tmp")
        _torch.save(hooker, tmp)
        tmp.replace(cache_path)
        gc.collect()
    return hooker
