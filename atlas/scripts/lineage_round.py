"""Lineage round CLI (FASE 6) — Lote 2 v1.1.0 (ANCHOR_CHANGES #16),
rondas v1.2.0 (ANCHOR_CHANGES #17).

Wrapper REAL del harness que midió la fase: gaea_v/scripts/
lineage_measured.py. La ronda 1 usa las definiciones preregistradas
`lineage_defs_20261021`; la ronda 2 (re-medición de protocolo)
registra defs NUEVAS (`lineage_defs_20261023`) encadenadas ANTES de
recalcular cualquier métrica. Este CLI invoca el harness, imprime el
sha256 de las defs para el registro y propaga el código de salida. La
verificación de identidad S-01 (heph / pesos / holdout) la aplica el
propio harness vía AtlasHook.verify_identity ANTES de tocar insumos —
este wrapper no la duplica.

Fail-loud con causa nombrada (exit 2) si: no hay hermano gaea_v, falta
el harness o faltan las defs de la ronda pedida al MEDIR (preregistro
ANTES de datos, nunca al revés). El stage `defs` es el paso de
registro: no exige que el archivo preexista, lo genera y encadena.
Aviso honesto: re-ejecutar una ronda produce artefactos NUEVOS en
gaea_v/artifacts/ y anexa eventos a gaea_v/logs/audit.jsonl.

Uso: lineage_round.py [STAGE] [--round N]   STAGE: defs | measure |
all (default: all; se pasa tal cual al harness). Rondas registradas:
1 (congelada), 2 (protocolo). El hermano se resuelve con
$GAEA_V_ROOT o el gaea_v hermano de atlas/.
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

HARNESS_REL = "scripts/lineage_measured.py"
ROUND_DEFS = {
    1: "artifacts/prereg/lineage_defs_20261021.json",
    2: "artifacts/prereg/lineage_defs_20261023.json",
}
STAGES = "defs | measure | all  (default: all)"


def _fail(cause: str) -> int:
    print(f"FALLO (lineage_round): {cause}", file=sys.stderr)
    print("Protocolo: README raíz (Pendientes declarados) y "
          "ANCHOR_CHANGES #16/#17.", file=sys.stderr)
    return 2


def main() -> int:
    args = sys.argv[1:]
    round_n = 1
    if "--round" in args:
        i = args.index("--round")
        try:
            round_n = int(args[i + 1])
        except (IndexError, ValueError):
            return _fail("--round requiere un entero (1 o 2)")
        del args[i:i + 2]
    stage = args[0] if args else "all"
    if round_n not in ROUND_DEFS:
        return _fail(f"ronda no registrada: {round_n}; "
                     f"registradas: {sorted(ROUND_DEFS)}")
    gaea = Path(os.environ.get("GAEA_V_ROOT")
                or (Path(__file__).resolve().parents[2] / "gaea_v"))
    if not gaea.is_dir():
        return _fail(
            f"no encuentro el hermano gaea_v en {gaea} — clona el "
            "monorepo completo o exporta GAEA_V_ROOT")
    harness = gaea / HARNESS_REL
    if not harness.is_file():
        return _fail(f"falta el harness {harness}")
    defs = gaea / ROUND_DEFS[round_n]
    if stage != "defs" and not defs.is_file():
        return _fail(
            f"faltan las definiciones preregistradas de la ronda "
            f"{round_n} ({defs}) — el preregistro va ANTES de los "
            "datos; no se mide una ronda sin él (corre primero el "
            "stage defs, que las registra y encadena)")
    sha = hashlib.sha256(defs.read_bytes()).hexdigest() \
        if defs.is_file() else "(se registran en el stage defs)"
    print(f"[lineage_round] harness={harness}")
    print(f"[lineage_round] ronda={round_n} defs={defs.name} "
          f"sha256={sha}")
    print(f"[lineage_round] stage={stage}  (STAGE válido: {STAGES})")
    print("[lineage_round] aviso honesto: la corrida produce artefactos "
          "NUEVOS en gaea_v/artifacts/ y anexa a gaea_v/logs/audit.jsonl")
    proc = subprocess.run(
        [sys.executable, str(harness), stage, "--round", str(round_n)],
        cwd=str(gaea))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
