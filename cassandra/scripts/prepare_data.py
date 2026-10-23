#!/usr/bin/env python3
"""CLI: --config config.yaml.

Downloads/verifies the true/false domain files, builds entities, the
fixed folds.json and the EDA summary. Fails loudly on any download or
integrity problem: CASSANDRA never invents data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cassandra_ns.data import eda, loader, splits  # noqa: E402
from cassandra_ns.report.figures import save_figure  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    from cassandra_ns.config import load_config
    cfg = load_config(args.config)

    print("[1/4] downloading + verifying the true/false domain files")
    loader.download_true_false(cfg)

    print("[2/4] building the normalized dataset (grammatical subjects)")
    df = loader.build_true_false_dataset(cfg)
    path = loader.write_processed(cfg, df)
    n_entities = df["entity"].nunique()
    print(f"  {len(df)} statements | {df['domain'].nunique()} domains | "
          f"{n_entities} entities -> {path}")

    print("[3/4] entity audit (100 sampled extractions for review)")
    audit = loader.audit_entities(
        df, out_path=Path("logs") / "entity_audit.csv",
        n=100, seed=int(cfg["seed"]))
    for _, row in audit.head(8).iterrows():
        print(f"  [{row['domain']}] {row['statement'][:60]!r} -> "
              f"entity {row['entity']!r}")
    print(f"  full audit table: logs/entity_audit.csv "
          f"({len(audit)} rows sampled with seed {cfg['seed']})")

    print("[4/4] fixed folds (StratifiedGroupKFold by entity) + EDA")
    folds = splits.build_folds(cfg, df)
    sizes = [len(f["test_ids"]) for f in folds["folds"]]
    print(f"  folds.json written | sha256 {folds['sha256'][:12]}... | "
          f"test sizes {sizes}")

    summary_path = eda.write_summary(df, Path("docs") / "figures")
    print(f"  summary: {summary_path}")

    # data_summary figure (same content as notebook 01's charts)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    summary = eda.summary_table(df)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    axes[0].bar(summary["domain"], summary["n"], color="#4c78a8")
    axes[0].set_title("statements per domain")
    axes[0].tick_params(axis="x", rotation=30)
    ax2 = axes[0].twinx()
    ax2.plot(summary["domain"], summary["pct_true"], "o",
             color="#b0553a", label="% true")
    ax2.set_ylim(0, 1)
    ax2.set_ylabel("% true")
    axes[1].bar(summary["domain"], summary["n_entities"],
                color="#3a7d5c")
    axes[1].set_title("entities per domain")
    axes[1].tick_params(axis="x", rotation=30)
    fig.tight_layout()
    out = save_figure(fig, "data_summary")
    print(f"  figure: {out}")


if __name__ == "__main__":
    main()
