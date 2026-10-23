"""Lote 2 (v1.1.0, ANCHOR_CHANGES #16): los CLIs `rft_round` / `lineage_round`
son wrappers REALES del harness gaea_v. Fail-loud con causa nombrada (exit 2)
cuando falta el hermano gaea_v, el harness o el prereg; passthrough de stage;
transparencia del sha256 del prereg. La identidad S-01 la aplica el propio
harness vía AtlasHook.verify_identity — el wrapper no la duplica."""
import json
import os
import subprocess
import sys
from pathlib import Path

ATLAS_ROOT = Path(__file__).resolve().parents[1]
RFT = ATLAS_ROOT / "scripts" / "rft_round.py"
LIN = ATLAS_ROOT / "scripts" / "lineage_round.py"

RFT_PREREG = "prereg_20261020_rft_rondas_v2.json"
LIN_DEFS = "lineage_defs_20261021.json"

STUB_BODY = """import sys, json
json.dump({{"stage": sys.argv[1] if len(sys.argv) > 1 else "NOARG"}},
          open({marker!r}, "w"))
print("STAGE_OK")
"""


def fake_gaea(tmp_path: Path, *, rft_stub: bool = True,
              lin_stub: bool = True, with_rft_prereg: bool = True,
              with_lin_defs: bool = True) -> Path:
    root = tmp_path / "gaea_v"
    (root / "scripts").mkdir(parents=True)
    (root / "artifacts" / "prereg").mkdir(parents=True)
    (root / "logs").mkdir(parents=True)
    (root / "config.yaml").write_text("seed: 1\n", encoding="utf-8")
    if rft_stub:
        (root / "scripts" / "run_fase5.py").write_text(
            STUB_BODY.format(marker="marker_rft.json"), encoding="utf-8")
    if lin_stub:
        (root / "scripts" / "lineage_measured.py").write_text(
            STUB_BODY.format(marker="marker_lineage.json"), encoding="utf-8")
    if with_rft_prereg:
        (root / "artifacts" / "prereg" / RFT_PREREG).write_text(
            json.dumps({"rounds": 1, "note": "prereg fixture"}),
            encoding="utf-8")
    if with_lin_defs:
        (root / "artifacts" / "prereg" / LIN_DEFS).write_text(
            json.dumps({"defs": "g1-g4", "note": "fixture"}),
            encoding="utf-8")
    return root


def run_wrapper(script: Path, args: list[str], gaea_root) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if gaea_root is None:
        env["GAEA_V_ROOT"] = str(Path(script).parent / "no_existe")
    else:
        env["GAEA_V_ROOT"] = str(gaea_root)
    return subprocess.run([sys.executable, str(script), *args],
                          env=env, capture_output=True, text=True,
                          timeout=120)


# -- rft_round ---------------------------------------------------------------
def test_rft_round_invokes_harness_with_stage(tmp_path):
    gaea = fake_gaea(tmp_path)
    proc = run_wrapper(RFT, ["h3"], gaea)
    assert proc.returncode == 0, proc.stderr
    assert "STAGE_OK" in proc.stdout
    marker = json.loads((gaea / "marker_rft.json").read_text())
    assert marker["stage"] == "h3"            # passthrough exacto del stage
    assert RFT_PREREG in proc.stdout and "sha256=" in proc.stdout


def test_rft_round_default_stage_is_all(tmp_path):
    gaea = fake_gaea(tmp_path)
    proc = run_wrapper(RFT, [], gaea)
    assert proc.returncode == 0, proc.stderr
    marker = json.loads((gaea / "marker_rft.json").read_text())
    assert marker["stage"] == "all"


def test_rft_round_fails_loud_without_gaea_sibling(tmp_path):
    proc = run_wrapper(RFT, ["all"], None)
    assert proc.returncode == 2
    assert "gaea_v" in (proc.stderr + proc.stdout)


def test_rft_round_fails_loud_without_prereg(tmp_path):
    gaea = fake_gaea(tmp_path, with_rft_prereg=False)
    proc = run_wrapper(RFT, ["all"], gaea)
    assert proc.returncode == 2
    assert "prereg" in (proc.stderr + proc.stdout)
    assert not (gaea / "marker_rft.json").exists()   # nada corrió


# -- lineage_round -------------------------------------------------------------
def test_lineage_round_invokes_harness_with_stage(tmp_path):
    gaea = fake_gaea(tmp_path)
    proc = run_wrapper(LIN, ["measure"], gaea)
    assert proc.returncode == 0, proc.stderr
    assert "STAGE_OK" in proc.stdout
    marker = json.loads((gaea / "marker_lineage.json").read_text())
    assert marker["stage"] == "measure"
    assert LIN_DEFS in proc.stdout


def test_lineage_round_fails_loud_without_gaea_sibling(tmp_path):
    proc = run_wrapper(LIN, ["all"], None)
    assert proc.returncode == 2
    assert "gaea_v" in (proc.stderr + proc.stdout)


def test_lineage_round_fails_loud_without_defs(tmp_path):
    gaea = fake_gaea(tmp_path, with_lin_defs=False)
    proc = run_wrapper(LIN, ["all"], gaea)
    assert proc.returncode == 2
    assert "prereg" in (proc.stderr + proc.stdout)
