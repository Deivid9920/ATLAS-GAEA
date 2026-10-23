#!/usr/bin/env python3
"""Generate the CASSANDRA tree: package inits, module stubs with API
contracts, CLI script stubs and .gitkeep placeholders.

Existing files are never overwritten: the specification package anchors
(config.yaml, Makefile, tests/, scripts/colab_setup.py,
scripts/make_notebooks.py, cassandra_ns/probes/stats.py,
tests/test_stats.py) are placed first, and this scaffold only fills the
gaps so the tree matches tests/test_structure.py.

Usage:
    python3 scripts/scaffold.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DIRECTORIES = [
    "cassandra_ns/data",
    "cassandra_ns/activations",
    "cassandra_ns/probes",
    "cassandra_ns/generation",
    "cassandra_ns/ensemble",
    "cassandra_ns/report",
    "notebooks",
    "scripts",
    "tests",
    "data/raw",
    "data/processed",
    "artifacts/activations",
    "artifacts/probes",
    "docs/figures",
    "logs",
]

GITKEEP = [f"{d}/.gitkeep" for d in DIRECTORIES
           if d.startswith(("data/", "artifacts/", "logs"))]

PACKAGES = {
    "cassandra_ns": "CASSANDRA: hallucination detection from internal signals.",
    "cassandra_ns/data": "Dataset loading, grouped splits and EDA helpers.",
    "cassandra_ns/activations": "TransformerLens residual extraction + fp16 disk cache.",
    "cassandra_ns/probes": "Veracity probes, calibration and the stats anchor.",
    "cassandra_ns/generation": "TriviaQA generation, probe scoring and abstention.",
    "cassandra_ns/ensemble": "Optional symbolic bridge to the PROMETHEUS-NS graph.",
    "cassandra_ns/report": "Table and figure builders shared by the notebooks.",
}

STUBS = {
    "cassandra_ns/config.py": (
        "load_config(path) -> dict: read config.yaml, validate every\n"
        "section key-by-key (seed, models, data, splits, probes, stats,\n"
        "generation, abstention, ensemble, colab) and return the dict.\n"
        "Invalid or missing keys raise ValueError with the offending key."),
    "cassandra_ns/data/loader.py": (
        "Dataset contract: download True/False domain files from\n"
        "config.data.tf_base_url using tf_filename_template, verify each\n"
        "file sha256 against data/raw/manifest.json (fail loudly on any\n"
        "mismatch), normalize records to {{statement, label, domain,\n"
        "entity}}. The entity is the native subject field when present,\n"
        "otherwise a heuristic + spaCy en_core_web_sm NER fallback (the\n"
        "NER path is audited on 100 extractions). TriviaQA subset loading\n"
        "with normalized string-match against aliases lives here too."),
    "cassandra_ns/data/splits.py": (
        "Split contract: StratifiedGroupKFold with groups = entity and\n"
        "stratification = (domain, label); n_folds fixed folds written to\n"
        "data/processed/folds.json with its sha256. A statement never\n"
        "appears in two folds; rebuilding with the same seed reproduces\n"
        "the file byte for byte."),
    "cassandra_ns/data/eda.py": (
        "EDA contract: per-domain summary (n, %true, n entities, mean\n"
        "statement length), class balance, entity-size distribution and\n"
        "cross-domain entity overlap; summary CSV written to\n"
        "docs/figures/data_summary.csv and the paired figure to\n"
        "docs/figures/data_summary.png (dpi 150)."),
    "cassandra_ns/activations/extract.py": (
        "Extraction contract: TransformerLens hooks on\n"
        "blocks.{{L}}.hook_resid_post for the configured layers of each\n"
        "model; capture the last-token vector (real lengths tracked, no\n"
        "padding tokens) and the mean-pool over the statement; batch 32,\n"
        "fp32 on CPU / fp16 on CUDA. A statement alone must produce the\n"
        "same activation as inside a batch."),
    "cassandra_ns/activations/cache.py": (
        "Cache contract: memmap float16 store + CSV index (id, model,\n"
        "layer, mode, offset); idempotent (re-runs skip statements already\n"
        "cached by their sha256); atomic writes. load_index(config, model)\n"
        "and load_vectors(config, model, layer, mode) expose the cache to\n"
        "probes and notebooks with per-layer lazy loading."),
    "cassandra_ns/probes/train.py": (
        "Probe training contract: for every (model, layer, mode, type)\n"
        "combination a StandardScaler + probe (logistic over C_grid, or\n"
        "MLP with mlp_hidden units and early stopping) is trained on 4\n"
        "folds and evaluated on the held-out fold; the scaler is fitted\n"
        "inside each training fold, never globally. All out-of-fold\n"
        "predictions are persisted to logs/oof_predictions.jsonl."),
    "cassandra_ns/probes/evaluate.py": (
        "Evaluation contract: aggregate out-of-fold predictions into the\n"
        "table (model, layer, mode, type, AUC with bootstrap CI, AP, ECE,\n"
        "Brier, paired p vs |logprob| baseline, Holm-adjusted\n"
        "significance) written to logs/probe_results.jsonl and\n"
        "docs/probe_table.md; AUC above 0.95 triggers the documented\n"
        "leakage audit; leave-one-domain-out is the secondary analysis.\n"
        "probe_summary_table() and load_oof() serve notebooks."),
    "cassandra_ns/probes/calibration.py": (
        "Calibration contract: ECE (10 equal-width bins), Brier score and\n"
        "reliability diagram data for any (y_true, score) pair;\n"
        "reliability_diagram() builds the notebook figure."),
    "cassandra_ns/probes/stats.py": (
        "ANCHOR: immutable numerical specification (bootstrap_ci,\n"
        "paired_bootstrap_diff_auc, holm_bonferroni, roc_auc). If this\n"
        "file is missing, copy it from the specification package; never\n"
        "reimplement its metrics elsewhere."),
    "cassandra_ns/generation/generate.py": (
        "Generation contract: n_prompts TriviaQA questions -> greedy\n"
        "(temperature 0.0) generation of max_new_tokens tokens per model,\n"
        "full transcriptions saved with the prompt and the answer aliases."),
    "cassandra_ns/generation/scoring.py": (
        "Scoring contract: first declarative sentence of each generation\n"
        "(flagged when absent, with a declared policy), probe score from\n"
        "the best Phase 3 configuration, ground truth by normalized\n"
        "string-match against aliases; ambiguous matches are excluded and\n"
        "counted, never forced. abstention_curve() sweeps the threshold\n"
        "tau and computes the coverage-accuracy curve plus tau* at\n"
        "min_coverage; load_scored() serves notebooks."),
    "cassandra_ns/ensemble/symbolic_bridge.py": (
        "Ensemble contract: when config.ensemble.prometheus_graph points\n"
        "to a consistency graph, extract subject-predicate-object triplets\n"
        "from generations, map them to a symbolic signal {{0, 0.5, 1}} by\n"
        "consistency, and fit a 2-feature logistic ensemble (probe score,\n"
        "symbolic signal) inside validation folds only; report probe-alone\n"
        "vs signal-alone vs ensemble on the same extractable subset with\n"
        "paired bootstrap. Without a graph the ensemble is marked\n"
        "unavailable with its cause. load_ensemble_results() serves\n"
        "notebooks."),
    "cassandra_ns/report/tables.py": (
        "Reporting contract: probe_summary_table(results) returns the\n"
        "formatted metrics table for notebook 03 and the README; every\n"
        "number comes from logs/ or an executed cell."),
    "cassandra_ns/report/figures.py": (
        "Figure contract: save_figure(fig, name) writes docs/figures/\n"
        "{name}.png at dpi 150 and returns the path; figures render with\n"
        "the Agg backend when no display is available."),
}

SCRIPTS = {
    "scripts/prepare_data.py": (
        "CLI: --config config.yaml. Downloads/verifies the true/false\n"
        "domain files, builds entities, folds.json and the EDA summary."),
    "scripts/extract_activations.py": (
        "CLI: --config config.yaml --model NAME. Caches residual\n"
        "activations for every statement of the given model."),
    "scripts/train_probes.py": (
        "CLI: --config config.yaml. Trains the full probe grid with\n"
        "grouped CV and writes out-of-fold predictions."),
    "scripts/evaluate_probes.py": (
        "CLI: --config config.yaml [--figures-only]. Aggregates results,\n"
        "writes the probe table and renders the evaluation figures."),
    "scripts/generate_and_score.py": (
        "CLI: --config config.yaml --model NAME. Generates TriviaQA\n"
        "answers, scores them with the best probe and writes the scored\n"
        "table plus the abstention analysis."),
    "scripts/ensemble_eval.py": (
        "CLI: --config config.yaml. Evaluates the symbolic-neural\n"
        "ensemble or records it as unavailable with its cause."),
    "scripts/run_notebooks.py": (
        "CLI: --config config.yaml. Executes the four notebooks in order\n"
        "with nbconvert --execute --inplace; any failing cell fails the\n"
        "run."),
}


def stub_source(contract: str, cli: bool) -> str:
    body = '"""' + contract + '"""\n'
    if cli:
        body += (
            "\nfrom __future__ import annotations\n\n"
            "import argparse\n\n\n"
            "def main() -> None:\n"
            "    ap = argparse.ArgumentParser()\n"
            "    ap.add_argument(\"--config\", default=\"config.yaml\")\n"
            "    ap.parse_args()\n"
            "    raise SystemExit(\"not implemented yet: see the module \"\n"
            "                     \"docstring for the API contract\")\n\n\n"
            "if __name__ == \"__main__\":\n"
            "    main()\n")
    return body


def main() -> None:
    created: list[str] = []
    kept: list[str] = []

    for d in DIRECTORIES:
        (ROOT / d).mkdir(parents=True, exist_ok=True)

    for keep in GITKEEP:
        target = ROOT / keep
        if target.exists():
            kept.append(keep)
            continue
        target.write_text("", encoding="utf-8")
        created.append(keep)

    for pkg, doc in PACKAGES.items():
        init = ROOT / pkg / "__init__.py"
        if init.exists():
            kept.append(str(init.relative_to(ROOT)))
            continue
        init.write_text(f'"""{doc}"""\n', encoding="utf-8")
        created.append(str(init.relative_to(ROOT)))

    for rel, contract in STUBS.items():
        target = ROOT / rel
        if target.exists():
            kept.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if "ANCHOR" in contract:
            print(f"  !! {rel}: anchor missing — copy it from the "
                  "specification package")
            continue
        target.write_text(stub_source(contract, cli=False), encoding="utf-8")
        created.append(rel)

    for rel, contract in SCRIPTS.items():
        target = ROOT / rel
        if target.exists():
            kept.append(rel)
            continue
        target.write_text(stub_source(contract, cli=True), encoding="utf-8")
        created.append(rel)

    print("created:")
    for rel in created:
        print(f"  + {rel}")
    if kept:
        print("kept existing:")
        for rel in kept:
            print(f"  = {rel}")

    anchors = ["cassandra_ns/probes/stats.py", "tests/test_stats.py",
               "tests/test_structure.py", "config.yaml", "Makefile",
               "scripts/make_notebooks.py", "scripts/colab_setup.py"]
    print("anchors:")
    for rel in anchors:
        ok = (ROOT / rel).is_file()
        print(f"  {'ok' if ok else '!!'} {rel}: "
              f"{'present' if ok else 'MISSING: copy it from the specification package'}")

    print("\nnext: make setup && make test")


if __name__ == "__main__":
    main()
