"""Figure utilities shared by the pipeline and the notebooks.

save_figure(fig, name) writes docs/figures/{name}.png at dpi 150 and
returns the path. Figures render with the Agg backend when no display
is available, so headless execution (nbconvert, make notebooks) never
needs a window server.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

if not matplotlib.is_interactive() or "DISPLAY" not in __import__("os").environ:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

FIGURES_DIR = Path("docs") / "figures"


def save_figure(fig: plt.Figure, name: str, out_dir: str | Path = FIGURES_DIR
                ) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path
