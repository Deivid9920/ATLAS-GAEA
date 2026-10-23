#!/usr/bin/env python3
"""Print the exact Colab setup cell for the CASSANDRA notebooks.

The output is a single Python code cell that, executed as the first cell
of a notebook on Google Colab: detects the environment, clones the
repository, installs the pinned dependencies, downloads the spaCy model
and prepares the data/cache directories. Locally, the same cell degrades
to a dependency check (the venv already provides everything).

Usage:
    python3 scripts/colab_setup.py --print-cell [--repo-url URL]
"""

from __future__ import annotations

import argparse

DEFAULT_REPO_URL = "https://github.com/REPLACE-USER/CASSANDRA.git"

CELL_TEMPLATE = '''\
# CASSANDRA setup cell — run this FIRST, in order, before any other cell.
# On Colab with GPU desired (Pythia extraction): Runtime > Change runtime
# type > GPU, THEN run this cell.
import importlib
import os
import subprocess
import sys
from pathlib import Path

IN_COLAB = "google.colab" in sys.modules
REPO_URL = "{repo_url}"

if IN_COLAB:
    if not Path("/content/CASSANDRA/.git").exists():
        subprocess.run(["git", "clone", REPO_URL, "/content/CASSANDRA"],
                       check=True)
    os.chdir("/content/CASSANDRA")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                    "-r", "requirements.txt"], check=True)
    subprocess.run([sys.executable, "-m", "spacy", "download",
                    "en_core_web_sm"], check=True, capture_output=True)
    subprocess.run([sys.executable, "scripts/prepare_data.py",
                    "--config", "config.yaml"], check=True)
    print("Colab setup complete. Working directory:", os.getcwd())
else:
    try:
        import torch, transformer_lens, sklearn, pandas, seaborn  # noqa: F401
        print("Local environment OK. Run `make data` if data/processed "
              "is empty.")
    except ImportError as exc:
        raise SystemExit(
            f"Missing dependency ({{exc}}). Run `make setup` from the "
            "repository root before executing this notebook."
        )
'''


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print-cell", action="store_true")
    ap.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    args = ap.parse_args()
    if not args.print_cell:
        raise SystemExit("nothing to do: pass --print-cell")
    print(CELL_TEMPLATE.format(repo_url=args.repo_url))


if __name__ == "__main__":
    main()
