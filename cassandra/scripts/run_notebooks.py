#!/usr/bin/env python3
"""CLI: --config config.yaml.

Executes the four demonstration notebooks in order, in place
(nbconvert-style headless execution through nbclient). Any failing
cell fails the run, so `make notebooks` stays red until the notebooks
execute end to end. The kernel is pinned to this script's interpreter:
a user kernelspec "python3" is registered for the venv when missing.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

NB_ORDER = ["01_data_exploration.ipynb", "02_activation_analysis.ipynb",
            "03_probe_evaluation.ipynb", "04_generation_case_study.ipynb",
            "05_symbolic_bridge.ipynb"]


def ensure_kernel() -> None:
    """Register a python3 kernelspec for this interpreter if absent."""
    import ipykernel

    try:
        from jupyter_client.kernelspec import KernelSpecManager
        specs = KernelSpecManager().find_kernel_specs()
        if "python3" in specs:
            spec_path = Path(specs["python3"]) / "kernel.json"
            argv0 = json.loads(spec_path.read_text())["argv"][0]
            if Path(argv0).resolve() == Path(sys.executable).resolve():
                return
        ipykernel.kernelspec.install(user=True, kernel_name="python3",
                                     display_name="Python 3 (cassandra)")
    except Exception as exc:  # pragma: no cover - environment specific
        print(f"kernel registration warning: {exc}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    from cassandra_ns.config import load_config  # noqa: F401

    load_config(args.config)  # fail fast on a broken config

    ensure_kernel()

    try:
        from nbclient import NotebookClient
        import nbformat
    except ImportError as exc:
        raise SystemExit(
            f"missing notebook runtime dependency: {exc}. "
            "pip install -r requirements.txt") from exc

    notebooks_dir = REPO / "notebooks"
    missing = [nb for nb in NB_ORDER
               if not (notebooks_dir / nb).is_file()]
    if missing:
        raise SystemExit(
            f"missing notebooks: {missing}. Run "
            "scripts/make_notebooks.py first (make notebooks does).")

    for name in NB_ORDER:
        path = notebooks_dir / name
        print(f"executing {name} ...", flush=True)
        nb = nbformat.read(str(path), as_version=4)
        client = NotebookClient(
            nb,
            timeout=3600,
            kernel_name="python3",
            resources={"metadata": {"path": str(REPO)}},
        )
        try:
            client.execute()
        except Exception as exc:
            raise SystemExit(
                f"{name} failed during execution: {exc}. The failing "
                "cell is recorded in the notebook object above; fix "
                "the cause and re-run make notebooks.") from exc
        nbformat.write(nb, str(path))
        print(f"  ok: {name} ({len(nb.cells)} cells, executed in place)",
              flush=True)

    print(f"all {len(NB_ORDER)} notebooks executed without errors")


if __name__ == "__main__":
    main()
