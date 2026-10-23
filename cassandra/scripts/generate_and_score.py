#!/usr/bin/env python3
"""CLI: --config config.yaml --model NAME.

Generates TriviaQA answers (greedy, config temperature 0.0), scores
them with the model's best Fase 3 probe, writes the scored table plus
the abstention analysis and the generation-time calibration:
logs/scored_generations_{model}.jsonl, logs/abstention_{model}.json,
logs/generation_calibration_{model}.json and the reliability diagram
under docs/figures/. Idempotent per prompt_id.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--model", required=True)
    args = ap.parse_args()

    import matplotlib
    matplotlib.use("Agg")

    from cassandra_ns.config import load_config
    from cassandra_ns.generation import generate, scoring
    from cassandra_ns.probes.calibration import reliability_diagram
    from cassandra_ns.report.figures import save_figure

    cfg = load_config(args.config)
    model = args.model

    print(f"[1/4] greedy generation for {model} "
          f"(n={cfg['generation']['n_prompts']}, "
          f"max_new_tokens={cfg['generation']['max_new_tokens']})")
    gen_path = generate.generate_for_model(cfg, model)
    print(f"  -> {gen_path}")

    print("[2/4] scoring generations (best Fase 3 configuration)")
    best = scoring.load_best_config(cfg, model)
    print(f"  best config: layer {best['layer']} {best['mode']} "
          f"{best['ptype']} (AUC {best['auc']:.3f})")
    scored_path = scoring.score_generations(cfg, model)
    print(f"  -> {scored_path}")

    scored = scoring.load_scored(cfg, model)
    plot_df = scored.dropna(subset=["correct", "score"])
    excluded = len(scored) - len(plot_df)
    print(f"  scored {len(scored)} | excluded {excluded} (flagged) | "
          f"match rate {plot_df['correct'].mean():.3f}")

    print("[3/4] abstention analysis")
    curve, tau_star = scoring.abstention_curve(
        plot_df["correct"].astype(int).to_numpy(),
        plot_df["score"].to_numpy(),
        float(cfg["abstention"]["min_coverage"]))
    feasible = curve[curve["coverage"] >=
                     float(cfg["abstention"]["min_coverage"])]
    star = feasible.loc[feasible["accuracy"].idxmax()]
    baseline_acc = float(plot_df["correct"].mean())
    doc = {
        "model": model,
        "n_scored": int(len(scored)),
        "n_excluded": int(excluded),
        "baseline_accuracy": baseline_acc,
        "tau_star": tau_star,
        "coverage_at_tau_star": float(star["coverage"]),
        "accuracy_at_tau_star": float(star["accuracy"]),
        "gain_vs_always_answer": float(star["accuracy"]) - baseline_acc,
        "match_rate": baseline_acc,
    }
    out = Path("logs") / f"abstention_{model}.json"
    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    curve.to_json(Path("logs") / f"abstention_curve_{model}.json",
                  orient="records")
    print(f"  tau* = {tau_star:.4f} -> (coverage "
          f"{star['coverage']:.2f}, accuracy {star['accuracy']:.3f}), "
          f"gain {doc['gain_vs_always_answer']:+.3f}")
    print(f"  -> {out}")

    print("[4/4] generation-time calibration")
    fig, info = reliability_diagram(
        plot_df["correct"].astype(int).to_numpy(),
        plot_df["score"].to_numpy())
    fig.gca().set_title(f"{model}: reliability on generations")
    fig_path = save_figure(fig, f"04_reliability_generations_{model}")
    cal = {"model": model, "ece": info["ece"], "brier": info["brier"],
           "n": int(len(plot_df))}
    out = Path("logs") / f"generation_calibration_{model}.json"
    out.write_text(json.dumps(cal, indent=2), encoding="utf-8")
    print(f"  ECE {info['ece']:.4f} | Brier {info['brier']:.4f} "
          f"-> {out}, figure {fig_path}")


if __name__ == "__main__":
    main()
