#!/usr/bin/env python3
"""CLI: --config config.yaml [--figures-only].

Aggregates out-of-fold predictions into the probe results table
(logs/probe_results.jsonl + docs/probe_table.md), runs the mandatory
leakage audit when any AUC exceeds 0.95, and produces the secondary
analyses: leave-one-domain-out, the TF-IDF stylistic confound control
and the same-subject minimal-pairs control. --figures-only skips the
re-aggregation and renders the evaluation figures only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def render_figures(cfg) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    from cassandra_ns.probes.evaluate import load_results
    from cassandra_ns.report.figures import save_figure

    sns.set_theme(style="whitegrid")
    results = load_results(cfg)
    overall = results[results["domain"].isna()]

    fig, ax = plt.subplots(figsize=(9, 4.6))
    for model, group in overall.groupby("model"):
        for ptype, g2 in group.groupby("ptype"):
            g = g2.sort_values("layer")
            ax.plot(g["layer"], g["auc"], marker="o",
                    label=f"{model} / {ptype}")
    ax.set_xlabel("layer")
    ax.set_ylabel("out-of-fold AUC")
    ax.set_title("AUC by layer (both feature modes pooled at their max)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    save_figure(fig, "probe_auc_by_layer")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--figures-only", action="store_true")
    args = ap.parse_args()

    from cassandra_ns.data import eda
    from cassandra_ns.probes import evaluate
    from cassandra_ns.config import load_config

    cfg = load_config(args.config)

    if args.figures_only:
        render_figures(cfg)
        print("figures rendered to docs/figures/")
        return

    print("[1/5] aggregating out-of-fold predictions")
    table = evaluate.aggregate(cfg)

    print("[2/5] leakage audit gate (AUC > 0.95)")
    audit = evaluate.leakage_audit(cfg, table)
    print("  audit written to logs/leakage_audit.md"
          if audit else "  no AUC above 0.95: audit not triggered")

    print("[3/5] secondary analysis: leave-one-domain-out")
    lodo = evaluate.leave_one_domain_out(cfg)
    print(f"  -> {lodo}")

    print("[4/5] stylistic confound controls (TF-IDF + minimal pairs)")
    tfidf = evaluate.tfidf_control(cfg)
    print(f"  -> {tfidf}: {json.loads(tfidf.read_text())['auc']:.3f} AUC")
    pairs = evaluate.style_pairs_control(cfg)
    print(f"  -> {pairs}")

    print("[5/5] probe table")
    md = evaluate.write_probe_table_md(cfg, table)
    print(f"  -> {md}")

    render_figures(cfg)


if __name__ == "__main__":
    main()
