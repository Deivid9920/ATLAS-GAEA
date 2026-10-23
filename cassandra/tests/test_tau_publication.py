"""Bridge-publication contracts for docs/ensemble_table.md.

v1.2.0 integration finding: the ensemble table did not publish tau* in
the format the ATLAS probe bridge parses, so the sibling's _tau_star()
returned None (honest NEUTRAL vote, but without the calibrated
threshold). These tests pin the publication contract from the
CASSANDRA side: the published value must be exactly the measured tau*
of the canonical source record, and every source record cited by the
table must exist inside the tree.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TABLE = REPO_ROOT / "docs" / "ensemble_table.md"


def _parse_tau_star(text: str) -> float | None:
    """Reference port of the ATLAS probe bridge parser
    (atlas/atlas_ns/verify/plugins/probe.py, _tau_star): the first
    numeric token in (0, 1) of the first line that mentions tau and
    contains a table pipe. Kept in sync by contract, not by import:
    CASSANDRA does not depend on the sibling's code."""
    for line in text.splitlines():
        if "tau" in line.lower() and "|" in line:
            for token in line.split("|"):
                token = token.strip()
                if token.replace(".", "", 1).isdigit():
                    value = float(token)
                    if 0.0 < value < 1.0:
                        return value
    return None


def test_tau_star_published_and_matches_source_record() -> None:
    """The table publishes tau* in the parseable format and the value
    equals the measured tau_star of the canonical gpt2 record."""
    published = _parse_tau_star(TABLE.read_text(encoding="utf-8"))
    assert published is not None, (
        "docs/ensemble_table.md does not publish tau* in the parseable "
        "format: the ATLAS bridge would read None")
    source = json.loads(
        (REPO_ROOT / "logs" / "abstention_gpt2.json").read_text(
            encoding="utf-8"))
    # Exact float equality: the table embeds the full repr of the
    # measured value, and JSON round-trips it exactly.
    assert published == source["tau_star"], (
        f"published tau* {published!r} != measured "
        f"{source['tau_star']!r}")


def test_pythia_tau_star_published_and_matches_source_record() -> None:
    """The pythia-410m row publishes the measured value of its own
    source record (both rows must be present, not just the canonical
    gpt2 one)."""
    text = TABLE.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines()
            if line.strip().startswith("|") and "pythia-410m" in line
            and "tau" in line.lower()]
    assert rows, "no tau* row for pythia-410m in ensemble_table.md"
    source = json.loads(
        (REPO_ROOT / "logs" / "abstention_pythia-410m.json").read_text(
            encoding="utf-8"))
    expected = repr(float(source["tau_star"]))
    assert any(expected in row for row in rows), (
        f"pythia-410m tau* row does not carry the measured value "
        f"{expected}")


def test_cited_source_records_exist_in_tree() -> None:
    """Every source record cited by the table lives inside the tree:
    each published number keeps its manifest (house rule)."""
    text = TABLE.read_text(encoding="utf-8")
    cited = sorted(set(re.findall(r"logs/[A-Za-z0-9_.-]+\.json", text)))
    assert cited, "no source records cited by ensemble_table.md"
    missing = [rel for rel in cited
               if not (REPO_ROOT / rel).is_file()]
    assert not missing, (
        f"cited source records missing from the tree: {missing}")
