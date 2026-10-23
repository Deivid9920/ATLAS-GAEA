"""EDA helpers for CASSANDRA.

Per-domain summary (n, %true, n entities, mean statement length), class
balance and cross-domain entity overlap. The summary CSV is written to
docs/figures/data_summary.csv next to its figure; every table the
notebooks show is computed here so notebook 01 never re-implements a
statistic.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def summary_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per-domain: n, %true, distinct entities, mean statement length."""
    work = df.copy()
    work["length"] = work["statement"].str.len()
    summary = (work.groupby("domain")
                   .agg(n=("id", "size"),
                        pct_true=("label", "mean"),
                        n_entities=("entity", "nunique"),
                        mean_length_chars=("length", "mean"))
                   .reset_index())
    summary["pct_true"] = summary["pct_true"].round(4)
    summary["mean_length_chars"] = summary["mean_length_chars"].round(1)
    return summary.sort_values("domain").reset_index(drop=True)


def overlap_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Number of entity strings shared between each pair of domains."""
    sets = {d: set(g["entity"]) for d, g in df.groupby("domain")}
    domains = sorted(sets)
    overlap = pd.DataFrame(0, index=domains, columns=domains, dtype=int)
    for i, a in enumerate(domains):
        for b in domains:
            overlap.loc[a, b] = len(sets[a] & sets[b])
    return overlap


def entity_size_table(df: pd.DataFrame) -> pd.Series:
    """Statements per (domain, entity): the empirical case for grouped CV."""
    return df.groupby(["domain", "entity"]).size()


def write_summary(df: pd.DataFrame, figures_dir: str | Path) -> Path:
    """Write docs/figures/data_summary.csv (the PNG is drawn by the
    notebook and by prepare_data through report.figures.save_figure)."""
    figures = Path(figures_dir)
    figures.mkdir(parents=True, exist_ok=True)
    out = figures / "data_summary.csv"
    summary_table(df).to_csv(out, index=False)
    return out
