"""Helper imported by run_task.py's crash-test child (keeps the -c
snippet small): composite wiring shared with the parent CLI."""

from __future__ import annotations  # noqa: F401

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_task import build_composite  # noqa: E402,F401
