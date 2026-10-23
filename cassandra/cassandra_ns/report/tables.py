"""Table builders shared by the notebooks and the final report.

probe_summary_table(results) turns the aggregated probe results into
the README-facing metrics table: one row per (model, layer, mode,
probe type) with the AUC and its bootstrap CI, AP, ECE, Brier, the
paired-baseline p-value and the Holm-adjusted p-value. Every number
comes from the executed runs recorded in logs/ - the builder formats,
it never recomputes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cassandra_ns.probes.stats import holm_bonferroni


def probe_summary_table(results: pd.DataFrame) -> pd.DataFrame:
    """Formatted metrics table for the overall (domain = null) rows.

    Sorted by model then AUC (best first within each model), with the
    Holm-Bonferroni adjustment applied over the pre-registered family
    (all overall rows).
    """
    overall = results[results["domain"].isna()].copy()
    if overall.empty:
        raise ValueError("results contain no overall rows (domain null)")

    family = overall.reset_index(drop=True)
    family["p_holm"] = holm_bonferroni(family["p_baseline"].tolist())
    family["ci_excludes_zero"] = (family["diff_lo"] > 0) \
        | (family["diff_hi"] < 0)
    family["claimable"] = (family["p_holm"] < 0.05)
    family["claimable"] = family["claimable"] & family["ci_excludes_zero"]

    family["auc_ci"] = family.apply(
        lambda r: f"{r['auc']:.3f} [{r['ci_lo']:.3f}, {r['ci_hi']:.3f}]",
        axis=1)

    columns = ["model", "layer", "mode", "ptype", "auc_ci", "ap", "ece",
               "brier", "baseline_auc", "p_baseline", "p_holm",
               "claimable"]
    table = family[columns].copy()
    table["ap"] = table["ap"].round(4)
    table["ece"] = table["ece"].round(4)
    table["brier"] = table["brier"].round(4)
    table["baseline_auc"] = table["baseline_auc"].round(4)
    for col in ("p_baseline", "p_holm"):
        table[col] = table[col].round(6)
    return table.sort_values(["model", "auc_ci"],
                             ascending=[True, False]).reset_index(drop=True)
