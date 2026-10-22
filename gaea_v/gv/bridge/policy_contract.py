"""policy_contract: JSON-lines v1 (ops propose/score/health).

The frontier where GAEA substrates plug in: a substrate implements
EXACTLY these ops; no tensor or weight crosses it. Versioned and
fail-loud (anchor 13).

Requests:
  {"op": "propose", "args": {"state": ..., "n": int}}
  {"op": "score",   "args": {"candidate": ...}}
  {"op": "health",  "args": {}}
Responses:
  {"ok": true, "candidates": [...]}
  {"ok": true, "score": float, "components": {...}}
  {"ok": true, "substrate_id": str, "contract_version": "1"}
"""

from __future__ import annotations

CONTRACT_VERSION = "1"
OPS = ("propose", "score", "health")


class PolicyContractError(ValueError):
    pass


def validate_request(msg: dict) -> None:
    if not isinstance(msg, dict):
        raise PolicyContractError("request must be an object")
    op = msg.get("op")
    if op not in OPS:
        raise PolicyContractError(f"unknown op {op!r}; allowed {OPS}")
    args = msg.get("args")
    if not isinstance(args, dict):
        raise PolicyContractError(f"op {op} requires an args object")
    if op == "propose":
        if "state" not in args or "n" not in args:
            raise PolicyContractError("propose needs state and n")
        if not isinstance(args["n"], int) or args["n"] < 1:
            raise PolicyContractError("propose n must be a positive int")
    if op == "score" and "candidate" not in args:
        raise PolicyContractError("score needs candidate")
    extra = set(msg) - {"op", "args"}
    if extra:
        raise PolicyContractError(f"unknown request fields: {extra}")


def validate_response(op: str, msg: dict) -> None:
    if not isinstance(msg, dict) or msg.get("ok") is not True:
        raise PolicyContractError(f"{op}: response must start with "
                                  "ok=true")
    if op == "propose":
        if not isinstance(msg.get("candidates"), list):
            raise PolicyContractError("propose: candidates list "
                                      "required")
    elif op == "score":
        if not isinstance(msg.get("score"), (int, float)):
            raise PolicyContractError("score: numeric score required")
        if not isinstance(msg.get("components"), dict):
            raise PolicyContractError("score: components map required")
    elif op == "health":
        if not isinstance(msg.get("substrate_id"), str) or \
                not msg["substrate_id"]:
            raise PolicyContractError("health: substrate_id required")
        if str(msg.get("contract_version")) != CONTRACT_VERSION:
            raise PolicyContractError(
                f"health: contract_version must be {CONTRACT_VERSION}")


def encode_request(op: str, args: dict) -> str:
    msg = {"op": op, "args": args}
    validate_request(msg)
    import json
    return json.dumps(msg, sort_keys=True, separators=(",", ":"))


def conformance_check(substrate) -> dict:
    """A substrate is GAEA-ready iff its three ops validate under v1.

    Runs health, propose and score against reference payloads and
    fails loud on the first violation. The substrate is any callable
    request-dict -> response-dict; no tensor or weight crosses the
    frontier, so a substrate behind this contract enters the harness
    without arnes changes (the harness only consumes solvers).
    """
    health = substrate({"op": "health", "args": {}})
    validate_response("health", health)
    propose = substrate({"op": "propose",
                         "args": {"state": {"tokens": []}, "n": 2}})
    validate_response("propose", propose)
    if not propose["candidates"]:
        raise PolicyContractError("propose returned no candidates")
    score = substrate({"op": "score",
                       "args": {"candidate": propose["candidates"][0]}})
    validate_response("score", score)
    return {"substrate_id": health["substrate_id"],
            "contract_version": health["contract_version"],
            "conformant": True}
