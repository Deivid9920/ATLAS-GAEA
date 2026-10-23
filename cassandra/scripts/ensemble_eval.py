#!/usr/bin/env python3
"""CLI: --config config.yaml.

Evaluates the symbolic-neural ensemble when
config.ensemble.prometheus_graph points to a consistency graph, or
records the ensemble as "unavailable" with its cause (the anchored
default: prometheus_graph is null). Writes logs/ensemble_results.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# models evaluated by `make ensemble` in order; the first entry owns
# the canonical logs/ensemble_results.json record
MODELS = ["gpt2", "pythia-410m"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    from cassandra_ns.config import load_config
    from cassandra_ns.ensemble import symbolic_bridge as bridge
    from cassandra_ns.generation import scoring

    cfg = load_config(args.config)
    graph_ref = cfg["ensemble"]["prometheus_graph"]

    if not cfg["ensemble"]["enabled"] or graph_ref is None:
        doc = {
            "status": "unavailable",
            "cause": ("config.ensemble.prometheus_graph is null: no "
                      "PROMETHEUS-NS consistency graph was provided. "
                      "Point it to a graph JSON (see "
                      "cassandra_ns/ensemble/symbolic_bridge.py for "
                      "the format) and re-run make ensemble."),
        }
        print(f"ensemble unavailable: {doc['cause']}")
        out = Path("logs") / "ensemble_results.json"
        out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        print(f"  -> {out}")
    else:
        graph_path = Path(graph_ref)
        if not graph_path.is_file():
            doc = {"status": "unavailable",
                   "cause": f"graph file not found: {graph_path}"}
            print(f"ensemble unavailable: {doc['cause']}")
        else:
            graph = bridge.load_graph(graph_path)
            # canonical record stays on gpt2 (logs/ensemble_results.json,
            # the file the notebooks and report read); every other model
            # in MODELS gets its own per-model record next to it
            for model in MODELS:
                scored = scoring.load_scored(cfg, model)
                doc = bridge.evaluate_ensemble(cfg, scored, graph)
                out_name = ("ensemble_results.json" if model == "gpt2"
                            else f"ensemble_results_{model}.json")
                out = Path("logs") / out_name
                out.write_text(json.dumps(doc, indent=2),
                               encoding="utf-8")
                print(f"[{model}] ensemble {doc['status']}: "
                      f"{doc.get('n_extractable', '-')} extractable rows")
                if doc["status"] == "evaluated":
                    print(f"  AUC probe {doc['auc_probe']:.3f} | signal "
                          f"{doc['auc_signal']:.3f} | ensemble "
                          f"{doc['auc_ensemble']:.3f}")
                    cov = doc["coverage"]
                    print(f"  coverage: {cov['n_claim_tuples_supported']}"
                          f"/{cov['n_claim_tuples']} tuples supported, "
                          f"{cov['n_rows_signal_unknown']}/"
                          f"{cov['n_rows_extractable']} rows unknown "
                          f"-> {out}")


if __name__ == "__main__":
    main()
