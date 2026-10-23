#!/usr/bin/env python3
"""RFT round CLI (FASE 5) — Lote 2 v1.1.0 (ANCHOR_CHANGES #16).

Wrapper REAL del harness que midió la fase: gaea_v/scripts/run_fase5.py
con el preregistro `prereg_20261020_rft_rondas_v2`. FASE 5 se midió vía
gaea_v; este CLI la invoca, imprime el sha256 del prereg para el
registro y propaga el código de salida del harness. La verificación de
identidad S-01 (heph / pesos / holdout) la aplica el propio harness vía
AtlasHook.verify_identity ANTES de tocar insumos — este wrapper no la
duplica.

Fail-loud con causa nombrada (exit 2) si: no hay hermano gaea_v, falta
el harness o falta el prereg (preregistro ANTES de datos, nunca al
revés). Aviso honesto: re-ejecutar una ronda produce artefactos NUEVOS
en gaea_v/artifacts/runs/ y anexa eventos a gaea_v/logs/audit.jsonl.

Uso: rft_round.py [STAGE]   STAGE: h3 | h4 | candidates | all[:only]
    (default: all; se pasa tal cual al harness)
El hermano se resuelve con $GAEA_V_ROOT o el gaea_v hermano de atlas/.
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

HARNESS_REL = "scripts/run_fase5.py"
PREREG_REL = "artifacts/prereg/prereg_20261020_rft_rondas_v2.json"
STAGES = "h3 | h4 | candidates | all[:only]  (default: all)"


def _fail(cause: str) -> int:
    print(f"FALLO (rft_round): {cause}", file=sys.stderr)
    print("Protocolo: README raíz (Pendientes declarados) y "
          "ANCHOR_CHANGES #16.", file=sys.stderr)
    return 2


def main() -> int:
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    gaea = Path(os.environ.get("GAEA_V_ROOT")
                or (Path(__file__).resolve().parents[2] / "gaea_v"))
    if not gaea.is_dir():
        return _fail(
            f"no encuentro el hermano gaea_v en {gaea} — clona el "
            "monorepo completo o exporta GAEA_V_ROOT")
    harness = gaea / HARNESS_REL
    if not harness.is_file():
        return _fail(f"falta el harness {harness}")
    prereg = gaea / PREREG_REL
    if not prereg.is_file():
        return _fail(
            f"falta el preregistro {prereg} — el preregistro va ANTES de "
            "los datos; no se mide una ronda sin él")
    sha = hashlib.sha256(prereg.read_bytes()).hexdigest()
    print(f"[rft_round] harness={harness}")
    print(f"[rft_round] prereg={prereg.name} sha256={sha}")
    print(f"[rft_round] stage={stage}  (STAGE válido: {STAGES})")
    print("[rft_round] aviso honesto: la corrida produce artefactos NUEVOS "
          "en gaea_v/artifacts/runs/ y anexa a gaea_v/logs/audit.jsonl")
    proc = subprocess.run([sys.executable, str(harness), stage],
                          cwd=str(gaea))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
