"""Structured verifier outputs (#7): JSON-schema contracts.

Every plugin verdict and every composite decision crossing a boundary
(MCP response, audit event, bench row) validates against these schemas.
jsonschema is the validator; schemas are versioned constants.
"""

from __future__ import annotations

VERDICT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "atlas:verdict:v1",
    "title": "Verifier verdict",
    "type": "object",
    "required": ["verifier", "score", "evidence", "hard_block"],
    "additionalProperties": False,
    "properties": {
        "verifier": {"type": "string", "minLength": 1},
        "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "evidence": {"type": "string"},
        "hard_block": {"type": "boolean"},
    },
}

DECISION_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "atlas:decision:v1",
    "title": "Composite decision",
    "type": "object",
    "required": ["decision", "weighted_score", "votes", "causes"],
    "additionalProperties": False,
    "properties": {
        "decision": {"enum": ["approve", "revise", "block", "abstain"]},
        "weighted_score": {"type": "number",
                           "minimum": 0.0, "maximum": 1.0},
        "votes": {"type": "array", "items": VERDICT_SCHEMA},
        "causes": {"type": "array", "items": {"type": "string"}},
    },
}


def verdict_to_dict(verdict) -> dict:
    """Verdict -> schema-shaped dict (validated by callers)."""
    return {
        "verifier": verdict.verifier,
        "score": round(float(verdict.score), 6),
        "evidence": verdict.evidence or "",
        "hard_block": bool(verdict.hard_block),
    }


def decision_to_dict(decision) -> dict:
    return {
        "decision": decision.decision,
        "weighted_score": round(float(decision.weighted_score), 6),
        "votes": [verdict_to_dict(v) for v in decision.votes],
        "causes": list(decision.causes),
    }


def validate(obj: dict, schema: dict) -> None:
    """Validate; raise jsonschema.ValidationError on violation."""
    import jsonschema

    jsonschema.validate(instance=obj, schema=schema)
