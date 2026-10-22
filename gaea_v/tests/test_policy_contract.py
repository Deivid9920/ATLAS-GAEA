"""Anchor 13: policy contract JSON-lines v1 (propose/score/health)."""
import json

import pytest

from gv.bridge.policy_contract import (CONTRACT_VERSION,  # noqa: F401
                                       conformance_check,
                                       validate_request,
                                       validate_response, encode_request,
                                       PolicyContractError)


def test_valid_requests_pass():
    validate_request({"op": "propose", "args": {"state": {}, "n": 4}})
    validate_request({"op": "score", "args": {"candidate": "x"}})
    validate_request({"op": "health", "args": {}})


def test_unknown_op_rejected():
    with pytest.raises(PolicyContractError):
        validate_request({"op": "train", "args": {}})
    with pytest.raises(PolicyContractError):
        validate_request({"op": None, "args": {}})


def test_bad_args_rejected():
    with pytest.raises(PolicyContractError):
        validate_request({"op": "propose", "args": {"state": {}}})
    with pytest.raises(PolicyContractError):
        validate_request({"op": "propose", "args": {"state": {},
                                                    "n": 0}})
    with pytest.raises(PolicyContractError):
        validate_request({"op": "score", "args": {}})
    with pytest.raises(PolicyContractError):
        validate_request({"op": "score", "args": {"candidate": "x"},
                          "extra": 1})


def test_valid_responses_pass():
    validate_response("propose", {"ok": True, "candidates": ["a"]})
    validate_response("score", {"ok": True, "score": 0.7,
                                "components": {"p": 0.7}})
    validate_response("health", {"ok": True, "substrate_id": "mamba2",
                                 "contract_version": "1"})


def test_responses_fail_loud():
    with pytest.raises(PolicyContractError):
        validate_response("propose", {"ok": False})
    with pytest.raises(PolicyContractError):
        validate_response("score", {"ok": True, "score": "high",
                                    "components": {}})
    with pytest.raises(PolicyContractError):
        validate_response("health", {"ok": True,
                                     "substrate_id": "mamba2",
                                     "contract_version": "2"})


def test_encode_roundtrip():
    line = encode_request("propose", {"state": {"k": 1}, "n": 2})
    msg = json.loads(line)
    validate_request(msg)


class _ReferenceSubstrate:
    """Minimal deterministic GAEA-ready surface for conformance."""

    def __init__(self, substrate_id="reference_stub"):
        self.substrate_id = substrate_id

    def __call__(self, request):
        op = request["op"]
        if op == "health":
            return {"ok": True, "substrate_id": self.substrate_id,
                    "contract_version": CONTRACT_VERSION}
        if op == "propose":
            n = int(request["args"]["n"])
            return {"ok": True,
                    "candidates": [{"token": f"c{i}"} for i in range(n)]}
        if op == "score":
            cand = request["args"]["candidate"]
            return {"ok": True, "score": 0.0,
                    "components": {"token": str(cand.get("token"))}}
        raise PolicyContractError(f"unknown op {op!r}")


def test_conformance_reference_substrate_passes():
    out = conformance_check(_ReferenceSubstrate())
    assert out["conformant"] is True
    assert out["substrate_id"] == "reference_stub"
    assert out["contract_version"] == CONTRACT_VERSION


def test_conformance_rejects_wrong_contract_version():
    class Bad(_ReferenceSubstrate):
        def __call__(self, request):
            if request["op"] == "health":
                return {"ok": True, "substrate_id": "bad",
                        "contract_version": "2"}
            return super().__call__(request)

    with pytest.raises(PolicyContractError):
        conformance_check(Bad())


def test_conformance_rejects_empty_candidates():
    class Empty(_ReferenceSubstrate):
        def __call__(self, request):
            if request["op"] == "propose":
                return {"ok": True, "candidates": []}
            return super().__call__(request)

    with pytest.raises(PolicyContractError):
        conformance_check(Empty())
