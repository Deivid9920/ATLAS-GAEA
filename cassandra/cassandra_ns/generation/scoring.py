"""Generation scoring and selective abstention.

Policy (declared once, applied uniformly - never decided case by case):

- the scored text is the FIRST DECLARATIVE sentence of the generation:
  the first segment terminated by ., ! or ? that is not a question and
  is not empty; generations without such a sentence are flagged
  (match_status = no_declarative) and EXCLUDED from the metrics
  (correct = null), never forced into an outcome;
- ground truth is a normalized string-match of that sentence against
  the question's aliases (statistical, not semantic: phrasings outside
  the alias list count as incorrect, match_status = no_alias);
- the probe score comes from the best Fase 3 configuration of the
  model, refit on the full statement dataset (the generative probe is
  a fixed instrument, not re-tuned per generation);
- abstention: threshold tau answers only generations with
  score >= tau; tau* maximizes accuracy subject to
  coverage >= config.abstention.min_coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_QUESTION_STARTERS = ("who", "what", "when", "where", "why", "how",
                      "which", "is", "are", "was", "were", "do", "does",
                      "did", "can", "could", "will", "would", "should")


def scored_path(cfg: dict, model: str) -> Path:
    return Path("logs") / f"scored_generations_{model}.jsonl"


def best_config_path(cfg: dict) -> Path:
    return Path("logs") / "best_config.json"


def first_declarative(text: str) -> tuple[str, bool]:
    """Simplified, deterministic: first non-question segment.

    Returns (sentence, flagged) where flagged=True when the generation
    produced no usable declarative sentence.
    """
    if not text.strip():
        return "", True
    segments = []
    current = ""
    for char in text:
        current += char
        if char in ".!?":
            segments.append(current.strip())
            current = ""
    if current.strip():
        segments.append(current.strip())
    for seg in segments:
        if not seg:
            continue
        if seg.endswith("?"):
            continue
        words = seg.lower().split()
        if words and words[0] in ("who", "what", "when", "where", "why",
                                  "how", "which"):
            continue
        return seg, False
    return "", True


def load_best_config(cfg: dict, model: str) -> dict:
    """Best Fase 3 configuration per model, from probe_results.jsonl."""
    path = best_config_path(cfg)
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
        if model in doc:
            return doc[model]
    from cassandra_ns.probes.evaluate import load_results
    results = load_results(cfg)
    overall = results[(results["model"] == model)
                      & (results["domain"].isna())]
    if overall.empty:
        raise RuntimeError(
            f"no probe results for {model}: run `make report` first")
    best = overall.sort_values("auc", ascending=False).iloc[0]
    doc = json.loads(path.read_text(encoding="utf-8")) if path.is_file() \
        else {}
    doc[model] = {"layer": int(best["layer"]), "mode": best["mode"],
                  "ptype": best["ptype"], "auc": float(best["auc"])}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return doc[model]


def fit_full_probe(cfg: dict, model: str, layer: int, mode: str,
                   ptype: str):
    """Refit the best configuration on the full statement dataset."""
    import joblib

    from cassandra_ns.activations.cache import load_vectors
    from cassandra_ns.data.loader import load_processed
    from cassandra_ns.data.splits import load_folds  # noqa: F401
    from cassandra_ns.probes.train import _make_probe, _select_C

    df = load_processed(cfg)
    vectors = np.asarray(load_vectors(cfg, model, layer, mode),
                         dtype=np.float32)
    y = df["label"].astype(bool).astype(int).to_numpy()
    strata = (df["domain"].astype(str) + "|"
              + df["label"].astype(bool).astype(int).astype(str)).to_numpy()
    groups = df["entity"].to_numpy()

    if ptype == "logistic":
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler().fit(vectors)
        X = scaler.transform(vectors)
        C, _ = _select_C(X, y, groups, strata, cfg["probes"]["C_grid"],
                         int(cfg["seed"]))
        probe = _make_probe("logistic", C, int(cfg["probes"]["mlp_hidden"]),
                            int(cfg["seed"]))
        probe.fit(X, y)
    else:
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler().fit(vectors)
        X = scaler.transform(vectors)
        probe = _make_probe("mlp", 1.0, int(cfg["probes"]["mlp_hidden"]),
                            int(cfg["seed"]))
        probe.fit(X, y)

    out = Path("artifacts") / "probes" / f"{model}_best.joblib"
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"scaler": scaler, "probe": probe, "layer": layer,
                 "mode": mode, "ptype": ptype}, out)
    return out


def probe_score_sentences(cfg: dict, model: str,
                          sentences: list[str]) -> np.ndarray:
    """Probe scores for arbitrary sentences under the model's best
    configuration (TransformerLens extraction + cached probe)."""
    import joblib
    import torch

    from cassandra_ns.activations import extract

    bundle_path = Path("artifacts") / "probes" / f"{model}_best.joblib"
    if not bundle_path.is_file():
        best = load_best_config(cfg, model)
        bundle_path = fit_full_probe(cfg, model, best["layer"],
                                     best["mode"], best["ptype"])
    bundle = joblib.load(bundle_path)

    hooker = extract.load_hooked(model)
    bos_id = hooker.tokenizer.bos_token_id or \
        hooker.tokenizer.eos_token_id

    scores = np.empty(len(sentences), dtype=np.float64)
    batch_size = 32
    with torch.no_grad():
        for start in range(0, len(sentences), batch_size):
            chunk = sentences[start:start + batch_size]
            encoded = []
            for text in chunk:
                ids = hooker.tokenizer(text,
                                       add_special_tokens=False)["input_ids"]
                encoded.append([bos_id]
                               + ids[-(hooker.cfg.n_ctx - 1):])
            lens = torch.tensor([len(e) for e in encoded])
            max_len = int(lens.max())
            tokens = torch.full((len(encoded), max_len), bos_id,
                                dtype=torch.long)
            for i, e in enumerate(encoded):
                tokens[i, :len(e)] = torch.tensor(e)
            layer = int(bundle["layer"])
            _, cache = hooker.run_with_cache(
                tokens,
                names_filter=lambda n, _l=layer:
                    n == f"blocks.{_l}.hook_resid_post")
            resid = cache[f"blocks.{layer}.hook_resid_post"].float()
            feats = np.empty((len(chunk), resid.shape[-1]),
                             dtype=np.float32)
            for row in range(len(chunk)):
                length = int(lens[row])
                if bundle["mode"] == "last_token":
                    feats[row] = resid[row, length - 1].numpy()
                else:
                    feats[row] = resid[row, 1:length].mean(dim=0).numpy()
            X = bundle["scaler"].transform(feats)
            scores[start:start + len(chunk)] = \
                bundle["probe"].predict_proba(X)[:, 1]
    return scores


def score_generations(cfg: dict, model: str) -> Path:
    """Score every generation: first sentence, probe score, ground
    truth. Writes logs/scored_generations_{model}.jsonl."""
    from cassandra_ns.data.loader import string_match_correct
    from cassandra_ns.generation.generate import load_generations

    rows = load_generations(cfg, model)
    out = scored_path(cfg, model)
    out.parent.mkdir(parents=True, exist_ok=True)

    done: set[str] = set()
    if out.is_file():
        with out.open(encoding="utf-8") as fh:
            for line in fh:
                done.add(json.loads(line)["prompt_id"])
    todo = [r for r in rows if r["prompt_id"] not in done]
    if not todo:
        return out

    sentences = []
    for row in todo:
        sentence, flagged = first_declarative(row["generation"])
        sentences.append(sentence if not flagged else "")

    # score ALL sentences in one pass (flagged ones get a score too,
    # but are excluded from metrics via correct=null)
    active_idx = [i for i, s in enumerate(sentences) if s]
    scores = np.full(len(todo), np.nan)
    if active_idx:
        active_scores = probe_score_sentences(
            cfg, model, [sentences[i] for i in active_idx])
        for local, score in zip(active_idx, active_scores):
            scores[local] = score

    with out.open("a", encoding="utf-8") as fh:
        for i, row in enumerate(todo):
            sentence = sentences[i]
            if not sentence:
                correct = None
                status = "no_declarative"
                flagged = True
            else:
                correct, status = string_match_correct(
                    sentence, row["aliases"], row["normalized_aliases"],
                    question_text=row["question"])
                flagged = correct is None
            fh.write(json.dumps({
                "prompt_id": row["prompt_id"],
                "question": row["question"],
                "generation": row["generation"],
                "first_sentence": sentence,
                "match_status": status,
                "flagged": flagged,
                "correct": correct,
                "score": None if np.isnan(scores[i]) else float(scores[i]),
            }, ensure_ascii=False) + "\n")
    return out


def load_scored(cfg: dict, model: str) -> pd.DataFrame:
    """The scored generations table for notebooks and the report."""
    path = scored_path(cfg, model)
    if not path.is_file():
        raise RuntimeError(
            f"{path} not found: run `make generate` first (the notebook "
            "guard cell does this automatically)")
    df = pd.DataFrame([json.loads(line) for line in
                       path.read_text(encoding="utf-8").splitlines()
                       if line])
    if df.empty:
        raise RuntimeError(f"{path} is empty: run `make generate` first")
    # correct arrives as object dtype from JSON (True/False/null);
    # boolean dtype makes ~correct and .astype(int) behave correctly
    df["correct"] = df["correct"].astype("boolean")
    return df


def abstention_curve(correct: np.ndarray, scores: np.ndarray,
                     min_coverage: float) -> tuple[pd.DataFrame, float]:
    """Coverage-accuracy sweep with tau* at the coverage constraint.

    Returns (curve, tau_star). curve has one row per candidate
    threshold (descending unique scores) plus the always-answer row;
    tau_star = NaN when the constraint cannot be met (cannot happen
    with min_coverage < 1 because coverage 1.0 is always in the sweep).
    """
    y = np.asarray(correct).astype(int)
    s = np.asarray(scores, dtype=float)
    order = np.argsort(-s, kind="mergesort")
    s_sorted = s[order]
    y_sorted = y[order]
    n = len(y)

    thresholds = np.unique(s_sorted)[::-1]
    rows = []
    # always-answer row: threshold below the minimum score
    rows.append({"tau": float(thresholds[-1]) - 1e-9 if n else 0.0,
                 "coverage": 1.0,
                 "accuracy": float(y.mean()) if n else np.nan,
                 "n_answered": n})
    cum_correct = np.cumsum(y_sorted)
    k = np.arange(1, n + 1)
    for tau in thresholds:
        answered = int((s >= tau).sum())
        if answered == 0:
            continue
        # accuracy among the top-answered by score (ties included)
        idx = order[:answered]
        acc = float(y[idx].mean())
        rows.append({"tau": float(tau),
                     "coverage": answered / n,
                     "accuracy": acc,
                     "n_answered": answered})
    curve = pd.DataFrame(rows)
    feasible = curve[curve["coverage"] >= min_coverage]
    if feasible.empty:
        return curve, float("nan")
    best = feasible.loc[feasible["accuracy"].idxmax()]
    return curve, float(best["tau"])
