# Symbolic bridge evaluation — PROMETHEUS-NS graph wired into CASSANDRA

Every number below is measured, not asserted. Source records:
`logs/ensemble_results.json` (gpt2, canonical), `logs/ensemble_results_pythia-410m.json`,
`logs/graph_export_stats.json`; analysis in `notebooks/05_symbolic_bridge.ipynb`
(committed executed). Environment: 2 CPU cores / 3.9 GB RAM, seed 42.

## 1. The graph (exported from PROMETHEUS-NS)

Produced by prometheus-ns `scripts/export_consistency_graph.py` over its own
pipeline output: spaCy triplet extraction (confidence >= 0.6) over the crawled
arXiv + Gutenberg corpus, NetworkX contradiction detection (is_a disjunction +
binary exclusivity), deterministic re-run of the recorded smoke run.

| Quantity | Value |
|---|---|
| store triplets (triplets/triplets.jsonl) | 4,442 |
| contradiction pairs found | 0 |
| bridge rows exported (incl. predicate-surface aliases) | 13,225 |
| — of which alias rows (documented schema adapter) | 9,311 |
| supported / contradicted rows | 13,225 / 0 |
| unique subjects / objects | 1,792 / 2,082 |
| dominant relations | is_a 2,704; have 112; take 70; make 63; give 50 |

The alias adapter repeats each store triplet with the surface verbs of
CASSANDRA's closed claim-verb list (is/are/was/were -> is_a, wrote -> write,
...) with the SAME subject, object and consistency verdict. `load_graph`
normalizes `is_a` to `isa`, so the alias rows are what makes the two predicate
schemas interoperate. It renames predicates only; it never invents facts.

## 2. Coverage over the generations' claims

Claims are extracted by the production shallow extractor from each generation's
first declarative sentence. Coverage is reported at three strictness levels.

| Model | labeled generations | extractable rows | claim tuples | tuples supported | tuples contradicted | subjects in graph / total | signal = 1 / 0 / 0.5 |
|---|---|---|---|---|---|---|---|
| gpt2 | 470 (30 excluded, reported) | 146 | 146 | **0** | **0** | 8 / 138 | 0 / 0 / **146** |
| pythia-410m | 470 (30 excluded, reported) | 107 | 107 | **0** | **0** | 6 / 92 | 0 / 0 / **107** |

**Finding.** Entity-level overlap exists (5.8% and 6.5% of claim subjects appear
somewhere in the graph) but tuple-level coverage is exactly zero: the
PROMETHEUS-NS corpus is technical/literary, the generations are open-domain
trivia, and no (subject, predicate, object) claim matches a graph row. The
symbolic signal is therefore constant 0.5 (unknown) on the whole extractable
subset — AUC 0.500 by construction, which doubles as a sanity check of the
machinery.

## 3. Ensemble outcome on the extractable subset

2-feature logistic (probe score, symbolic signal), out-of-fold with
StratifiedKFold(5, shuffle, seed 42); paired bootstrap 1000 resamples on
identical rows; single-class resamples are redrawn and counted.

| Metric | gpt2 | pythia-410m |
|---|---|---|
| AUC probe alone | 0.767 | 0.690 |
| AUC symbolic signal | 0.500 (constant) | 0.500 (constant) |
| AUC ensemble (OOF) | 0.448 | 0.670 |
| paired diff (ensemble - probe) | -0.319 | -0.020 |
| 95% CI | [-0.572, -0.078] | [-0.074, +0.022] |
| p (two-sided, bootstrap) | ~ 0.000 | 0.356 |
| positives in extractable subset | 2 / 146 | 9 / 107 |
| bootstrap resamples redrawn (single class) | 153 / 1000 | 0 / 1000 |

**Finding (honest negative).** With zero coverage, adding the symbolic feature
cannot help and does not: the ensemble degrades the probe significantly on gpt2
(OOF variance over a subset with 2 positives; the large redraw count is part of
that fragility and is reported, not hidden) and is statistically neutral on
pythia-410m. The operational conclusion is to keep abstention decisions on the
probe alone until the graph has general-knowledge coverage.

## 4. Machinery check (synthetic, clearly not a result)

An injected ORACLE signal on synthetic labels verifies the estimator can
exploit a second informative feature when one exists. Synthetic by design; it
says nothing about the models or the graph.

| Quantity | Value |
|---|---|
| AUC probe (synthetic) | 0.958 |
| AUC signal (oracle, injected) | 1.000 |
| AUC ensemble (OOF) | 1.000 |

## 5. What would make the bridge useful

Nothing in the bridge is broken: extraction, export, alias interop, signal,
OOF ensemble and paired statistics are pinned by the test suite (42 tests,
including the constant-signal case, the unlabeled-row exclusion, the
single-class redraw rule and the exported-graph loader). The bottleneck is
data, not code: pointing PROMETHEUS-NS's crawler at a general-knowledge corpus
(Wikipedia-class) and re-running `make data` + the export would raise tuple
coverage, and `make ensemble` picks it up with zero code changes.

## 6. Abstention thresholds (tau*), published for the ATLAS bridge

The selective-abstention curve picks tau* as the threshold that maximizes
accuracy subject to coverage >= `abstention.min_coverage` (0.6), over the 500
scored generations per model (30 unlabeled excluded, reported). Source
records: `logs/abstention_gpt2.json` and `logs/abstention_pythia-410m.json`
(full curves: `logs/abstention_curve_gpt2.json`,
`logs/abstention_curve_pythia-410m.json`). The `tau* (published)` cell is
the machine-readable contract consumed by the ATLAS probe bridge
(`atlas/atlas_ns/verify/plugins/probe.py`, `_tau_star()`): the first numeric
cell in (0, 1) of the first table row that mentions tau. Pinned by
`tests/test_tau_publication.py`. Before v1.3.0 this table did not publish
tau* and the bridge honestly parsed None (the vote is NEUTRAL with or
without it).

| quantity | model | value | source record |
|---|---|---|---|
| tau* (published, machine-readable) | gpt2 | 0.6447845697402954 | logs/abstention_gpt2.json |
| tau* (published, machine-readable) | pythia-410m | 0.4648858308792114 | logs/abstention_pythia-410m.json |
| coverage at tau* | gpt2 | 0.6000 | logs/abstention_gpt2.json |
| coverage at tau* | pythia-410m | 0.6404255319148936 | logs/abstention_pythia-410m.json |
| accuracy at tau* | gpt2 | 0.01773049645390071 | logs/abstention_gpt2.json |
| accuracy at tau* | pythia-410m | 0.09302325581395349 | logs/abstention_pythia-410m.json |
| gain vs always answer | gpt2 | 0.0049645390070922005 | logs/abstention_gpt2.json |
| gain vs always answer | pythia-410m | 0.02706580900544285 | logs/abstention_pythia-410m.json |

**Finding (honest).** Both tau* values sit in a regime where accuracy is
barely above the always-answer baseline (gpt2 1.77% vs 1.28%; pythia-410m
9.30% vs 6.60% on TriviaQA free-form generations): the abstention machinery
works, the generations themselves are the bottleneck. This matches the
zero-coverage finding of section 2 and does not change the ATLAS vote,
which stays NEUTRAL until live scoring lands with a trained probe bundle.
