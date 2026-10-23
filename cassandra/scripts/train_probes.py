#!/usr/bin/env python3
"""CLI: --config config.yaml.

Trains the full pre-registered probe grid (models x layers x feature
modes x probe types) with grouped CV and writes out-of-fold predictions
to logs/oof_predictions.jsonl. Appends per configuration: an
interrupted run resumes without recomputing finished configurations.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--model", default=None,
                    help="optional: train a single model's grid")
    args = ap.parse_args()

    from cassandra_ns.probes.train import train_all_probes
    from cassandra_ns.config import load_config

    cfg = load_config(args.config)
    models = [args.model] if args.model else None
    out = train_all_probes(cfg, models=models)
    print(f"out-of-fold predictions -> {out}")


if __name__ == "__main__":
    main()
