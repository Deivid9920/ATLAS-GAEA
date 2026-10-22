"""Anchor 9: contamination fingerprints and the fail-loud gate."""
import pytest

from gv.contamination.fingerprints import (normalize, fingerprint,
                                           ngrams, build_holdout_index)
from gv.contamination.gates import (require_clean, ContaminationError,
                                    SensorMissingError)

HOLDOUT = ("the quick brown fox jumps over the lazy dog and runs "
           "through the forest")


def test_normalize_is_stable():
    assert normalize("Hello, WORLD!  ") == "hello world"
    assert fingerprint("A  B") == fingerprint("a b")
    assert fingerprint("x") != fingerprint("y")


def test_exact_fingerprint_hit():
    index_fps = {fingerprint(HOLDOUT)}
    assert fingerprint(HOLDOUT) in index_fps
    assert fingerprint("other text") not in index_fps


def test_eight_gram_overlap_detected():
    index = build_holdout_index([HOLDOUT], 8)
    leaked = ("a story where the quick brown fox jumps over the lazy "
              "dog and runs far away")
    assert ngrams(leaked, 8) & index, "8-gram overlap must be found"
    clean = "an entirely different sentence about nothing at all"
    assert not (ngrams(clean, 8) & index)


def test_gate_passes_clean_and_fires_on_hit():
    index = build_holdout_index([HOLDOUT], 8)
    fps = {fingerprint(HOLDOUT)}
    ok = require_clean("nothing to see here", index, fps, 8, 0)
    assert ok == {"exact_hits": 0, "ngram_hits": 0, "status": "ok"}
    with pytest.raises(ContaminationError):
        require_clean(HOLDOUT, index, fps, 8, 0)
    with pytest.raises(ContaminationError):
        require_clean("the quick brown fox jumps over the lazy dog "
                      "and runs through the forest again", index, fps,
                      8, 0)


def test_missing_sensor_invalidates_round():
    with pytest.raises(SensorMissingError):
        require_clean("anything", None, set(), 8, 0)
    with pytest.raises(SensorMissingError):
        require_clean("anything", set(), None, 8, 0)
