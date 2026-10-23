#!/usr/bin/env python3
"""CLI: --config config.yaml --model NAME.

Caches residual activations (last_token + mean_pool at the configured
layers) plus the mean-logprob baseline for every statement of the given
model. Idempotent: statements already cached with a matching sha256 are
skipped, so an interrupted run resumes where it stopped.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--model", required=True)
    args = ap.parse_args()

    from cassandra_ns.activations import cache, extract
    from cassandra_ns.config import load_config, model_layers
    from cassandra_ns.data.loader import load_processed

    cfg = load_config(args.config)
    model = args.model
    layers = model_layers(cfg, model)

    df = load_processed(cfg)
    ids = df["id"].tolist()
    statements = df["statement"].tolist()

    done = cache.done_ids(cfg, model, ids, statements, layers)
    todo = [i for i, sid in enumerate(ids) if sid not in done]
    print(f"{model}: {len(done)}/{len(ids)} statements already cached, "
          f"{len(todo)} to extract (layers {layers})")

    device = "cuda" if __import__("torch").cuda.is_available() else "cpu"
    hooker = extract.load_hooked(model, device=device)
    d_model = hooker.cfg.d_model

    writer = cache.ActivationCacheWriter(cfg, model, d_model=d_model,
                                         n_capacity=len(ids),
                                         layers=layers)
    try:
        extract.extract_statements(
            hooker,
            ids=[ids[i] for i in todo],
            statements=[statements[i] for i in todo],
            layers=layers,
            writer=writer,
            device=device,
        )
    finally:
        writer.close()
    print(f"{model}: cache complete -> {cache.index_file(cfg, model)}")


if __name__ == "__main__":
    main()
