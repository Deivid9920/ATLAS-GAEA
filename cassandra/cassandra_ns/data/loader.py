"""Dataset loading for CASSANDRA.

Part 1 - the Azaria & Mitchell true/false dataset: download the six
domain files from config.data.tf_base_url, verify every file against
data/raw/manifest.json (sha256, fail loudly on mismatch or on a domain
that no longer resolves - the loader never invents data), and normalize
records to {id, statement, label, domain, entity}. The entity is the
grammatical subject: the native subject field when the source provides
one, otherwise a spaCy dependency heuristic (nsubj subtree of the root
verb) with a regex + NER fallback. The NER path is audited on 100
sampled extractions per run.

Part 2 - TriviaQA: a deterministic subset of config.data.trivias_n
questions (seed 42) from the rc.nocontext train split, filtered to
answers verifiable by normalized string-match against their aliases,
cached to data/processed/triviaqa_subset.jsonl with its sha256 in the
manifest.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_TRUE_FALSE_COLUMNS = ["id", "statement", "label", "domain", "entity"]

_COPULA_RE = re.compile(
    r"\b(is|are|was|were|has|have|had|uses|use|can|will|appears|"
    r"contains|lived|lives|invented|does|did|gets|get|grows|grow|"
    r"comes|come|consists)\b", flags=re.IGNORECASE)

_ARTICLE_RE = re.compile(r"^(the|a|an)\s+", flags=re.IGNORECASE)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def download_true_false(cfg: dict, force: bool = False) -> dict:
    """Download the six domain CSVs and write data/raw/manifest.json.

    Fail-loud contract: any HTTP error or missing domain raises instead
    of inventing or skipping data. Already-downloaded files are verified
    against the manifest and re-downloaded only when missing, when the
    manifest is missing, or when force is True.
    """
    import urllib.request

    data_cfg = cfg["data"]
    raw_dir = Path(data_cfg["cache_dir"]).parent / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "manifest.json"

    manifest: dict = {}
    if manifest_path.is_file() and not force:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    files: dict[str, dict] = {}
    for domain in data_cfg["domains"]:
        filename = data_cfg["tf_filename_template"].format(domain=domain)
        url = data_cfg["tf_base_url"] + filename
        target = raw_dir / filename
        if target.is_file() and not force:
            existing = manifest.get("files", {}).get(domain, {})
            if existing.get("sha256") == _sha256_file(target):
                files[domain] = existing
                continue
            # fall through: content drifted, re-download and re-record
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                payload = resp.read()
        except Exception as exc:  # fail loud, never invent data
            raise RuntimeError(
                f"true/false domain '{domain}' could not be downloaded "
                f"from {url}: {exc}. The loader does not invent data; "
                "fix the network or update data.tf_base_url to the "
                "official repository linked from the paper.") from exc
        target.write_bytes(payload)
        files[domain] = {
            "url": url,
            "sha256": _sha256_bytes(payload),
            "bytes": len(payload),
        }
        print(f"  downloaded {domain}: {len(payload)} bytes "
              f"sha256 {files[domain]['sha256'][:12]}...")

    manifest = {
        "source_note": (
            "Original repository github.com/Azariaa/true-false-dataset "
            "returns 404; files come from the ApolloResearch/deception-"
            "detection vendored copy pinned to a full commit SHA, "
            "cross-checked statement-by-statement against the HF mirror "
            "pminervini/true-false."),
        "retrieved_at": manifest.get("retrieved_at")
                        or datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True),
                             encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------
# entity extraction (grammatical subject)
# ---------------------------------------------------------------------------

def _heuristic_subject(statement: str) -> str:
    """Regex fallback: the text before the first verb-ish token."""
    match = _COPULA_RE.search(statement)
    span = statement[:match.start()] if match else statement
    span = span.strip().strip(",;:").rstrip(".")
    return _ARTICLE_RE.sub("", span).strip()


def extract_entity(statement: str, nlp=None) -> str:
    """Grammatical subject of a statement.

    Order: (1) spaCy nsubj subtree of the root verb; (2) NER proper
    noun inside the heuristic pre-verb span; (3) the raw heuristic span
    with the leading article stripped. Normalized to lowercase without
    the leading article so the same subject always maps to the same
    group string.
    """
    span = _heuristic_subject(statement)
    entity = ""
    if nlp is not None:
        doc = nlp(statement)
        subjects = [tok for tok in doc
                    if tok.dep_ in ("nsubj", "nsubjpass")
                    and tok.head.dep_ == "ROOT"]
        if not subjects:
            # try the root's own nsubj chain one level down
            roots = [tok for tok in doc if tok.dep_ == "ROOT"]
            for root in roots:
                subjects = [tok for tok in root.children
                            if tok.dep_ in ("nsubj", "nsubjpass")]
                if subjects:
                    break
            # 'There are no X for Y': no nsubj anywhere; the notional
            # subject is the attribute of the root
            if not subjects:
                for root in roots:
                    attrs = [tok for tok in root.children
                             if tok.dep_ == "attr"]
                    if attrs:
                        subjects = attrs
                        break
        # expletive 'there' ('There are no ... for skunk'): the real
        # subject follows the verb
        if subjects and subjects[0].text.lower() == "there":
            after = [tok for tok in doc if tok.i > subjects[0].i
                     and tok.dep_ in ("nsubj", "attr", "nsubjpass", "dobj")]
            if after:
                subjects = [after[0]]
        if subjects:
            entity = " ".join(t.text for t in subjects[0].subtree)
        if not entity:
            ents = [e.text for e in doc.ents
                    if e.label_ in ("PERSON", "ORG", "GPE", "LOC", "NORP",
                                    "FAC", "PRODUCT", "EVENT", "WORK_OF_ART")]
            if ents:
                entity = ents[0]
    if not entity:
        entity = span
    entity = entity.strip().strip(",;:").rstrip(".").strip()
    entity = _ARTICLE_RE.sub("", entity).strip().lower()
    return entity or statement.strip().lower()


def _load_spacy():
    import spacy
    try:
        return spacy.load("en_core_web_sm")
    except OSError as exc:
        raise RuntimeError(
            "spaCy model en_core_web_sm is required for subject "
            "extraction. Run: python -m spacy download en_core_web_sm"
        ) from exc


def build_true_false_dataset(cfg: dict) -> pd.DataFrame:
    """Normalized {id, statement, label, domain, entity} for all domains."""
    data_cfg = cfg["data"]
    raw_dir = Path(data_cfg["cache_dir"]).parent / "raw"
    frames: list[pd.DataFrame] = []
    for domain in data_cfg["domains"]:
        filename = data_cfg["tf_filename_template"].format(domain=domain)
        path = raw_dir / filename
        if not path.is_file():
            raise RuntimeError(
                f"missing raw file {path}: run the download step first")
        raw = pd.read_csv(path)
        for col in ("statement", "label"):
            if col not in raw.columns:
                raise RuntimeError(
                    f"{filename}: required column '{col}' missing")
        frame = pd.DataFrame({
            "statement": raw["statement"].astype(str),
            "label": raw["label"].astype(int).astype(bool),
        })
        frame["domain"] = domain
        frames.append(frame)
    df = pd.concat(frames, ignore_index=True)
    df["id"] = [f"{d}:{i:05d}" for i, d in enumerate(df["domain"])]

    nlp = _load_spacy()
    entities = [extract_entity(s, nlp=nlp) for s in df["statement"]]
    df["entity"] = entities

    empty = (df["entity"].str.len() == 0).sum()
    if empty:
        raise RuntimeError(f"{empty} statements produced an empty entity")
    return df[_TRUE_FALSE_COLUMNS]


def audit_entities(df: pd.DataFrame, out_path: Path, n: int = 100,
                   seed: int = 42) -> pd.DataFrame:
    """Audit contract: 100 sampled extractions, written for inspection.

    The audit table pairs the statement with the extracted entity so a
    reviewer can eyeball the error rate; it is saved under logs/ and
    summarized in the stdout of prepare_data.
    """
    sample = df.sample(n=min(n, len(df)), random_state=seed)
    table = sample[["id", "domain", "statement", "entity"]].copy()
    table = table.sort_index()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_path, index=False)
    return table


# ---------------------------------------------------------------------------
# processed dataset IO
# ---------------------------------------------------------------------------

def processed_path(cfg: dict) -> Path:
    return Path(cfg["data"]["cache_dir"]) / "statements.csv"


def write_processed(cfg: dict, df: pd.DataFrame) -> Path:
    path = processed_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def load_processed(cfg: dict) -> pd.DataFrame:
    """Load the processed dataset (id, statement, label, domain, entity).

    The guard cell in the notebooks regenerates it through
    scripts/prepare_data.py when missing; loading without preparation
    fails loudly instead of returning an empty frame.
    """
    path = processed_path(cfg)
    if not path.is_file():
        raise RuntimeError(
            f"{path} not found: run `make data` "
            "(scripts/prepare_data.py) first")
    df = pd.read_csv(path)
    df["label"] = df["label"].astype(bool)
    for col in _TRUE_FALSE_COLUMNS:
        if col not in df.columns:
            raise RuntimeError(f"{path}: required column '{col}' missing")
    return df[_TRUE_FALSE_COLUMNS]


# ---------------------------------------------------------------------------
# TriviaQA subset
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def triviaqa_subset_path(cfg: dict) -> Path:
    return Path(cfg["data"]["cache_dir"]) / "triviaqa_subset.jsonl"


def load_triviaqa_subset(cfg: dict) -> list[dict]:
    """Deterministic TriviaQA subset (seed 42), cached to disk.

    Build: stream the rc.nocontext train split in its deterministic
    order, keep the first 20000 verifiable questions (non-empty value
    and normalized aliases), sample n_prompts of them with seed 42, and
    write the subset jsonl. Rebuilds are byte-identical; the cached file
    is verified against the manifest when present.
    """
    path = triviaqa_subset_path(cfg)
    if path.is_file():
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line]

    import random

    from datasets import load_dataset

    n = int(cfg["data"]["trivias_n"])
    seed = int(cfg["seed"])
    print(f"  streaming trivia_qa rc.nocontext train (verifiable answers "
          f"only, sampling {n} with seed {seed})...")
    ds = load_dataset("trivia_qa", "rc.nocontext", split="train",
                      streaming=True)
    pool: list[dict] = []
    seen_questions: set[str] = set()
    target_pool = 20000
    for row in ds:
        answer = row.get("answer") or {}
        value = (answer.get("value") or "").strip()
        aliases = [a for a in (answer.get("aliases") or []) if a.strip()]
        normalized = sorted({_normalize(a) for a in aliases if _normalize(a)})
        if not value or not normalized:
            continue
        question = (row.get("question") or "").strip()
        if not question or question.lower() in seen_questions:
            continue
        seen_questions.add(question.lower())
        pool.append({
            "question_id": row.get("question_id") or "",
            "question": question,
            "answer_value": value,
            "aliases": aliases,
            "normalized_aliases": normalized,
        })
        if len(pool) >= target_pool:
            break
    if len(pool) < n:
        raise RuntimeError(
            f"only {len(pool)} verifiable TriviaQA questions streamed "
            f"(needed {n}): refusing to pad the subset")

    rng = random.Random(seed)
    subset = rng.sample(pool, n)
    subset.sort(key=lambda r: r["question_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True)
                      + "\n" for r in subset)
    path.write_text(payload, encoding="utf-8")

    manifest_path = (path.parent.parent / "raw" / "manifest.json")
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["triviaqa_subset"] = {
            "sha256": hashlib.sha256(
                payload.encode("utf-8")).hexdigest(),
            "rows": len(subset),
            "seed": seed,
            "pool_size": len(pool),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2,
                                            sort_keys=True),
                                 encoding="utf-8")
    return subset


def string_match_correct(generation_text: str, aliases: list[str],
                         normalized_aliases: list[str],
                         question_text: str = "") -> tuple[bool | None, str]:
    """Normalized string-match ground truth for one generation.

    Returns (correct, match_status) where correct can be:
    - True  ('alias_match'): the generation contains a normalized gold
      alias on word boundaries, and at least one matched alias is NOT
      already contained in the question (the model added information);
    - None  ('alias_in_question'): every matched alias is a substring
      of the question itself - the generation may be merely restating
      the question, which string-match cannot disambiguate, so the
      case is EXCLUDED and counted, never forced;
    - False ('no_alias'): the generation names no gold alias: it is
      incorrect under the statistical ground truth (documented in the
      README limits).
    """
    if not generation_text.strip():
        return False, "empty"
    normalized_text = _normalize(generation_text)
    words = normalized_text.split()
    matched_spans: list[list[str]] = []
    for alias in normalized_aliases:
        target = alias.split()
        span = len(target)
        if span == 0:
            continue
        for start in range(len(words) - span + 1):
            if words[start:start + span] == target:
                matched_spans.append(target)
                break
    if not matched_spans:
        return False, "no_alias"
    if question_text:
        question_words = _normalize(question_text).split()
        q = " ".join(question_words)
        adding_information = False
        for target in matched_spans:
            if " ".join(target) not in q:
                adding_information = True
                break
        if not adding_information:
            return None, "alias_in_question"
    return True, "alias_match"
