"""Matching double-axis + flops_v1 numeric contract (M-07: the champion
value is frozen exactly)."""
import pytest

from gv.lin.matching import (SubstrateSpec, flops_v1, matching_axes,
                             params_from_tensors)


def test_flops_v1_champion_exact():
    assert flops_v1(6, 384, 1024) == 10616832


def test_flops_v1_single_layer():
    assert flops_v1(1, 384, 1024) == 4 * 384 * 384 + 3 * 384 * 1024


def test_matching_axes_both_present():
    spec = SubstrateSpec("mamba2_384", 12_000_000, 940_000_000)
    axes = matching_axes(spec)
    assert axes["matching_params"] == 12_000_000
    assert axes["matching_training_flops"] == 940_000_000
    assert axes["substrate_id"] == "mamba2_384"


def test_matching_rejects_nonpositive():
    with pytest.raises(ValueError):
        matching_axes(SubstrateSpec("x", 0, 100))
    with pytest.raises(ValueError):
        matching_axes(SubstrateSpec("x", 100, 0))


def test_params_from_tensors_sums_shapes(tmp_path):
    tsv = tmp_path / "tensors.tsv"
    tsv.write_text("embedding.weight\t8000x384\tF32\t0\t12288000\n"
                   "final_norm.weight\t384\tF32\t12288000\t1536\n"
                   "layer.0.attn.wq.weight\t384x384\tF32\t12294856\t589824\n",
                   encoding="utf-8")
    assert params_from_tensors(tsv) == 8000 * 384 + 384 + 384 * 384


def test_params_from_tensors_rejects_empty(tmp_path):
    tsv = tmp_path / "empty.tsv"
    tsv.write_text("no shapes here\n", encoding="utf-8")
    with pytest.raises(ValueError):
        params_from_tensors(tsv)
