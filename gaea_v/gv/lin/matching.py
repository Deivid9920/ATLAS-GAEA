"""matching: doble eje de matching params + FLOPs (campos GAEA-L).

Reserved for GAEA substrate comparison: substrates are matched on
BOTH parameter count and training FLOPs, always reported together.
Matching on parameters alone biases toward SSMs (Mamba-2 packs more
state per parameter). The formula freezes here BEFORE any substrate
is trained.
"""

from __future__ import annotations

from dataclasses import dataclass

GAEA_L_FIELDS = ("substrate_id", "matching_params",
                 "matching_training_flops")


@dataclass(frozen=True)
class SubstrateSpec:
    substrate_id: str
    n_params: int
    training_flops: int


def flops_v1(n_layer: int, d_model: int, d_ff: int) -> int:
    """FLOPs per token for a transformer decoder block stack (MAC=2).

    per layer: QKVO 4*d_model^2, SwiGLU MLP 3*d_model*d_ff.
    Champion (6, 384, 1024): 10,616,832 FLOPs/token exactly.
    """
    return n_layer * (4 * d_model * d_model + 3 * d_model * d_ff)


def matching_axes(spec: SubstrateSpec) -> dict:
    """Both axes, always. Callers must never drop one of the two."""
    if spec.n_params <= 0 or spec.training_flops <= 0:
        raise ValueError("matching requires positive params and flops")
    return {"substrate_id": spec.substrate_id,
            "matching_params": spec.n_params,
            "matching_training_flops": spec.training_flops}


def params_from_tensors(tsv_path) -> int:
    """Parameter count measured from a tensors manifest (heph TSV).

    Column 2 holds the shape as "dxdy"; the parameter count is the
    product of its dimensions. Measured from the frozen artifact,
    never from a formula: G4 (ceiling) consumes this number.
    """
    from pathlib import Path
    total = 0
    for line in Path(tsv_path).read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) < 2 or not parts[1]:
            continue
        try:
            n = 1
            for dim in parts[1].split("x"):
                n *= int(dim)
        except ValueError:
            continue
        total += n
    if total <= 0:
        raise ValueError(f"no tensor shapes parsed from {tsv_path}")
    return total
