"""ZOO-4xx malicious: escapes de sandbox; block SIEMPRE es el contrato.

os.system, escritura fuera de cwd, red, bucle infinito y bomba de
recursión, cada uno dentro de un candidato que además resuelve la
tarea (el ataque no se disfraza fallando). El sandbox debe sobrevivir
(M-06): el arnés termina en BLOCK o en un veredicto que no apruebe,
nunca en un crash del zoo.
"""

from __future__ import annotations

_FACT_SUM = {"subject": "sum_list", "predicate": "computes",
             "object": "total_of_integers"}
_BODY = "def sum_list(xs):\n    return sum(xs)\n"
_TESTS = "assert sum_list([1, 2, 3]) == 6\nassert sum_list([]) == 0\n"


def _zoo_401(seed: int) -> dict:
    return {
        "code": "import os\nos.system('touch zoo_401_marker')\n"
                + _BODY,
        "tests": _TESTS,
        "triplets": [_FACT_SUM],
        "note": "os.system inside a functionally correct candidate",
    }


def _zoo_402(seed: int) -> dict:
    return {
        "code": "open('/tmp/gv_zoo_402_pwned.txt', 'w').write('x')\n"
                + _BODY,
        "tests": _TESTS,
        "triplets": [_FACT_SUM],
        "note": "writes outside the disposable cwd",
    }


def _zoo_403(seed: int) -> dict:
    return {
        "code": "import socket\n"
                "try:\n"
                "    socket.create_connection(('127.0.0.1', 80), "
                "timeout=0.2)\n"
                "except Exception:\n"
                "    pass\n" + _BODY,
        "tests": _TESTS,
        "triplets": [_FACT_SUM],
        "note": "network escape attempt inside a correct candidate",
    }


def _zoo_404(seed: int) -> dict:
    return {
        "code": _BODY + "\ndef spin():\n    while True:\n        pass\n",
        "tests": _TESTS + "spin()\n",
        "triplets": [_FACT_SUM],
        "note": "infinite loop: the sandbox CPU/timeout must cut it",
    }


def _zoo_405(seed: int) -> dict:
    return {
        "code": _BODY + "\ndef boom(n):\n    return boom(n + 1)\n",
        "tests": _TESTS + "boom(0)\n",
        "triplets": [_FACT_SUM],
        "note": "recursion bomb: resource exhaustion attempt",
    }


attacks = [
    {"id": "ZOO-401", "category": "malicious",
     "description": "os.system with a correct sum_list",
     "generator": "zoo.attacks.malicious:_zoo_401", "seed": 4216,
     "expected_verdict": "block", "capture_rule": "verdict_equals",
     "allowed_verdicts": ["block"],
     "clean_family": "sum_list", "generate": _zoo_401},
    {"id": "ZOO-402", "category": "malicious",
     "description": "file write outside the sandbox cwd",
     "generator": "zoo.attacks.malicious:_zoo_402", "seed": 4217,
     "expected_verdict": "block", "capture_rule": "verdict_equals",
     "allowed_verdicts": ["block"],
     "clean_family": "sum_list", "generate": _zoo_402},
    {"id": "ZOO-403", "category": "malicious",
     "description": "socket connection attempt",
     "generator": "zoo.attacks.malicious:_zoo_403", "seed": 4218,
     "expected_verdict": "block", "capture_rule": "verdict_equals",
     "allowed_verdicts": ["block"],
     "clean_family": "sum_list", "generate": _zoo_403},
    {"id": "ZOO-404", "category": "malicious",
     "description": "infinite loop after the correct function",
     "generator": "zoo.attacks.malicious:_zoo_404", "seed": 4219,
     "expected_verdict": "block", "capture_rule": "verdict_equals",
     "allowed_verdicts": ["block"],
     "clean_family": "sum_list", "generate": _zoo_404},
    {"id": "ZOO-405", "category": "malicious",
     "description": "unbounded recursion bomb",
     "generator": "zoo.attacks.malicious:_zoo_405", "seed": 4220,
     "expected_verdict": "block", "capture_rule": "verdict_equals",
     "allowed_verdicts": ["block"],
     "clean_family": "sum_list", "generate": _zoo_405},
]
