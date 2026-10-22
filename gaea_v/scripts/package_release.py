"""package_release: empaquetado de entrega (FASE 7 core).

Builds the release zip (no .venv, no .git, no __pycache__), guarantees
.gitkeep in EVERY declared-but-empty directory (M-01: zips lose empty
dirs; generic sweep, not a hand-written list), runs the
FORBIDDEN_MARKERS anchor (Anexo D: the test runs in CI and in
packaging; S-17: one marker stops the release), writes
SHA256SUMS_GAEA_V.txt with the 4 delivery hashes (repo, artefactos,
METRICS, manifiesto) and re-verifies the sums file mechanically after
writing.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDE_PARTS = {".venv", ".git", "__pycache__", ".pytest_cache"}

# Los 4 entregables del Anexo E / FASE 7.c:
# repo (zip), artefactos, METRICS, manifiesto.
SUMS_NAME = "SHA256SUMS_GAEA_V.txt"
SUMS_ENTRIES = [
    "artifacts/champion_tag.json",
    "docs/METRICS_baseline.md",
    "profiles/code_qa/suite_manifest.json",
]


def markers_scan_ok() -> bool:
    """Run the frozen structure anchor (S-17: one marker stops the
    packaging). Reusing the anchor keeps a single source of truth for
    the marker list."""
    proc = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), "-m", "pytest",
         "tests/test_structure.py::test_forbidden_markers", "-q",
         "--no-header"],
        cwd=str(ROOT), capture_output=True, text=True)
    return proc.returncode == 0


def ensure_gitkeeps() -> list[str]:
    """Generic sweep: every directory that ends up empty after the
    exclusion of .venv/.git/caches gets a .gitkeep (M-01)."""
    created = []
    for d in sorted(ROOT.rglob("*")):
        if not d.is_dir() or EXCLUDE_PARTS & set(d.parts):
            continue
        visible = [p for p in d.iterdir()
                   if not (EXCLUDE_PARTS & set(p.parts))]
        if not visible:
            keep = d / ".gitkeep"
            if not keep.exists():
                keep.write_text("", encoding="utf-8")
                created.append(str(d.relative_to(ROOT)))
    return created


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sums(sums: Path, base: Path) -> bool:
    """Recompute every line of the sums file (mechanical, post-pack)."""
    ok = True
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, rel = line.split("  ", 1)
        target = base / rel
        if not target.exists() or sha256_of(target) != digest:
            ok = False
    return ok


def main() -> int:
    if not markers_scan_ok():
        print("FORBIDDEN_MARKERS red (S-17): packaging stopped")
        return 1
    created = ensure_gitkeeps()
    if created:
        print("gitkeep created in: " + ", ".join(created))
    out = ROOT.parent / "gaea_v_entrega.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(ROOT.rglob("*")):
            if not p.is_file() or EXCLUDE_PARTS & set(p.parts):
                continue
            zf.write(p, p.relative_to(ROOT.parent))
    sums = ROOT.parent / SUMS_NAME
    lines = [f"{sha256_of(out)}  {out.name}"]
    for rel in SUMS_ENTRIES:
        target = ROOT / rel
        if not target.exists():
            print(f"missing delivery entry: {rel} (packaging stopped)")
            return 1
        lines.append(f"{sha256_of(target)}  gaea_v/{rel}")
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not verify_sums(sums, ROOT.parent):
        print("SHA256SUMS verification FAILED: packaging stopped")
        return 1
    print(f"packaged {out.name} ({out.stat().st_size} bytes); "
          f"{sums.name} written and verified ({len(lines)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
