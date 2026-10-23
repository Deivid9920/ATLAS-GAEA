"""Lote 3 (v1.2.0): la ronda 2 es de protocolo y su preregistro existe
ANTES de datos. El registro de rondas es cerrado (1 congelada, 2 de
protocolo); una ronda no registrada se niega con causa. h3/h4 quedaron
congelados en FASE 5. Las defs de linaje r2 se registran encadenadas
antes de recalcular cualquier métrica."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gv.canon import config_sha256  # noqa: E402
from gv.stats.prereg import validate_prereg, verify_prereg_file  # noqa: E402


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


run_fase5 = _load("run_fase5_mod", "scripts/run_fase5.py")
lineage_measured = _load("lineage_measured_mod",
                         "scripts/lineage_measured.py")


# -- registro de rondas RFT ---------------------------------------------------
def test_round1_keeps_frozen_protocol():
    rr = run_fase5.resolve_round(1)
    assert rr["prereg_sha256"] == run_fase5.ROUND1_PREREG
    assert rr["rft_dir"] == ROOT / "artifacts" / "rft" / "round_1"
    assert rr["suffix"] == ""
    assert rr["prereg_sha256"].startswith("cf38d994")


def test_round2_resolves_new_prereg_before_data():
    p = ROOT / "artifacts" / "prereg" / "prereg_20261023_rft_ronda2.json"
    rr = run_fase5.resolve_round(2)
    # el manifiesto incrusta el hash CANÓNICO encadenado (el mismo del
    # evento prereg_registered), no el sha de los bytes del archivo
    from gv.stats.prereg import prereg_hash
    chained = prereg_hash(json.loads(p.read_text(encoding="utf-8")))
    assert rr["prereg_sha256"] == chained
    assert chained.startswith("5b401494")
    assert rr["rft_dir"] == ROOT / "artifacts" / "rft" / "round_2"
    assert rr["suffix"] == "_r2"


def test_unregistered_round_refuses():
    with pytest.raises(SystemExit, match="no registrada"):
        run_fase5.resolve_round(3)
    with pytest.raises(SystemExit, match="no registrada"):
        lineage_measured.resolve_round(3)


def test_round2_refuses_h3_h4(monkeypatch):
    monkeypatch.setattr(sys, "argv",
                        ["run_fase5.py", "h3", "--round", "2"])
    with pytest.raises(SystemExit, match="h3/h4"):
        run_fase5.main()


def test_round2_prereg_exists_and_is_chained():
    p = ROOT / "artifacts" / "prereg" / "prereg_20261023_rft_ronda2.json"
    assert p.is_file(), "el prereg de la ronda 2 debe existir ANTES de datos"
    assert verify_prereg_file(p) is True, \
        "el prereg r2 debe estar encadenado (prereg_registered)"


def test_round2_prereg_schema_and_family():
    p = ROOT / "artifacts" / "prereg" / "prereg_20261023_rft_ronda2.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    validate_prereg(data)  # fail-loud si el esquema está roto
    assert data["prereg_id"] == "prereg_20261023_rft_ronda2"
    assert data["pilot_usage"] == "none"
    assert [h["id"] for h in data["family_hypotheses"]] == ["R1", "R2", "R3"]
    assert all(h["direction"] == "equivalence"
               for h in data["family_hypotheses"])
    assert data["config_sha256"] == config_sha256(ROOT / "config.yaml"), \
        "el prereg r2 quedó emitido contra el config re-hasheado; un " \
        "cambio de config posterior exige nueva enmienda encadenada"
    assert data["suite_digest"].startswith("e775280a")


# -- registro de rondas de linaje ---------------------------------------------
def test_lineage_round1_frozen_defs():
    rr = lineage_measured.resolve_round(1)
    assert rr["defs_id"] == "lineage_defs_20261021"
    assert rr["artifact"] == ROOT / "artifacts" / "lineage_g1g4_round.json"


def test_lineage_round2_new_defs_id():
    rr = lineage_measured.resolve_round(2)
    assert rr["defs_id"] == "lineage_defs_20261023"
    assert rr["artifact"] == ROOT / "artifacts" / "lineage_g1g4_round2.json"
    assert "re-medición" in rr["label"]
    # los datos son los runs congelados de FASE 7, declarados en defs
    assert "bench_atlas" in rr["note"]
