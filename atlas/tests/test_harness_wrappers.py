"""Lote 2 (v1.1.0, ANCHOR_CHANGES #16): los CLIs `rft_round` / `lineage_round`
son wrappers REALES del harness gaea_v. Fail-loud con causa nombrada (exit 2)
cuando falta el hermano gaea_v, el harness o el prereg; passthrough de stage;
transparencia del sha256 del prereg. La identidad S-01 la aplica el propio
harness vía AtlasHook.verify_identity — el wrapper no la duplica.

Lote 3 (v1.2.0, ANCHOR_CHANGES #17): las rondas son explícitas
(`--round N`): la ronda 1 conserva el prereg congelado; la ronda 2 exige el
prereg NUEVO registrado ANTES de datos. El stage `defs` del linaje es el
paso de REGISTRO: no exige que el archivo preexista; medir sin defs sigue
siendo fail-loud."""
import json
import os
import subprocess
import sys
from pathlib import Path

ATLAS_ROOT = Path(__file__).resolve().parents[1]
RFT = ATLAS_ROOT / "scripts" / "rft_round.py"
LIN = ATLAS_ROOT / "scripts" / "lineage_round.py"

RFT_PREREG_R1 = "prereg_20261020_rft_rondas_v2.json"
RFT_PREREG_R2 = "prereg_20261023_rft_ronda2.json"
LIN_DEFS_R1 = "lineage_defs_20261021.json"
LIN_DEFS_R2 = "lineage_defs_20261023.json"

STUB_BODY = """import sys, json
json.dump({{"argv": sys.argv[1:]}},
          open({marker!r}, "w"))
print("STAGE_OK")
"""


def fake_gaea(tmp_path: Path, *, rft_stub: bool = True,
              lin_stub: bool = True, with_rft_prereg: bool = True,
              with_lin_defs: bool = True, with_r2_prereg: bool = False,
              with_r2_defs: bool = False) -> Path:
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
        (root / "artifacts" / "prereg" / RFT_PREREG_R1).write_text(
            json.dumps({"rounds": 1, "note": "prereg fixture"}),
            encoding="utf-8")
    if with_lin_defs:
        (root / "artifacts" / "prereg" / LIN_DEFS_R1).write_text(
            json.dumps({"defs": "g1-g4", "note": "fixture"}),
            encoding="utf-8")
    if with_r2_prereg:
        (root / "artifacts" / "prereg" / RFT_PREREG_R2).write_text(
            json.dumps({"rounds": 2, "note": "prereg r2 fixture"}),
            encoding="utf-8")
    if with_r2_defs:
        (root / "artifacts" / "prereg" / LIN_DEFS_R2).write_text(
            json.dumps({"defs": "g1-g4-r2", "note": "fixture r2"}),
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
    assert marker["argv"] == ["h3", "--round", "1"]  # passthrough exacto
    assert RFT_PREREG_R1 in proc.stdout and "sha256=" in proc.stdout


def test_rft_round_default_stage_is_all(tmp_path):
    gaea = fake_gaea(tmp_path)
    proc = run_wrapper(RFT, [], gaea)
    assert proc.returncode == 0, proc.stderr
    marker = json.loads((gaea / "marker_rft.json").read_text())
    assert marker["argv"][0] == "all"


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


def test_rft_round_r2_requires_new_prereg(tmp_path):
    gaea = fake_gaea(tmp_path)  # r1 presente, r2 ausente
    proc = run_wrapper(RFT, ["all", "--round", "2"], gaea)
    assert proc.returncode == 2
    assert "ronda 2" in (proc.stderr + proc.stdout)
    assert not (gaea / "marker_rft.json").exists()   # nada corrió


def test_rft_round_r2_passes_round_flag(tmp_path):
    gaea = fake_gaea(tmp_path, with_r2_prereg=True)
    proc = run_wrapper(RFT, ["all", "--round", "2"], gaea)
    assert proc.returncode == 0, proc.stderr
    marker = json.loads((gaea / "marker_rft.json").read_text())
    assert marker["argv"] == ["all", "--round", "2"]
    assert RFT_PREREG_R2 in proc.stdout and "sha256=" in proc.stdout


def test_rft_round_refuses_unregistered_round(tmp_path):
    gaea = fake_gaea(tmp_path, with_r2_prereg=True)
    proc = run_wrapper(RFT, ["all", "--round", "3"], gaea)
    assert proc.returncode == 2
    assert "no registrada" in (proc.stderr + proc.stdout)
    assert not (gaea / "marker_rft.json").exists()


# -- lineage_round -------------------------------------------------------------
def test_lineage_round_invokes_harness_with_stage(tmp_path):
    gaea = fake_gaea(tmp_path)
    proc = run_wrapper(LIN, ["measure"], gaea)
    assert proc.returncode == 0, proc.stderr
    assert "STAGE_OK" in proc.stdout
    marker = json.loads((gaea / "marker_lineage.json").read_text())
    assert marker["argv"] == ["measure", "--round", "1"]
    assert LIN_DEFS_R1 in proc.stdout


def test_lineage_round_fails_loud_without_gaea_sibling(tmp_path):
    proc = run_wrapper(LIN, ["all"], None)
    assert proc.returncode == 2
    assert "gaea_v" in (proc.stderr + proc.stdout)


def test_lineage_round_fails_loud_without_defs(tmp_path):
    gaea = fake_gaea(tmp_path, with_lin_defs=False)
    proc = run_wrapper(LIN, ["all"], gaea)
    assert proc.returncode == 2
    assert "prereg" in (proc.stderr + proc.stdout)


def test_lineage_round_defs_stage_registers_without_existing_defs(tmp_path):
    # El stage `defs` es el paso de REGISTRO: genera y encadena; no
    # exige que el archivo preexista.
    gaea = fake_gaea(tmp_path, with_lin_defs=False, with_r2_defs=False)
    proc = run_wrapper(LIN, ["defs", "--round", "2"], gaea)
    assert proc.returncode == 0, proc.stderr
    marker = json.loads((gaea / "marker_lineage.json").read_text())
    assert marker["argv"] == ["defs", "--round", "2"]
    assert LIN_DEFS_R2 in proc.stdout


def test_lineage_round_measure_r2_requires_r2_defs(tmp_path):
    gaea = fake_gaea(tmp_path, with_r2_defs=False)
    proc = run_wrapper(LIN, ["measure", "--round", "2"], gaea)
    assert proc.returncode == 2
    assert "ronda 2" in (proc.stderr + proc.stdout)
    assert not (gaea / "marker_lineage.json").exists()
    # con las defs r2 presentes, mide:
    gaea2 = fake_gaea(tmp_path / "b", with_r2_defs=True)
    proc2 = run_wrapper(LIN, ["measure", "--round", "2"], gaea2)
    assert proc2.returncode == 0, proc2.stderr
    assert (gaea2 / "marker_lineage.json").exists()
