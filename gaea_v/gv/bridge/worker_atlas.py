"""Worker ATLAS: ejecuta operaciones de lectura sobre atlas_ns.

Runs inside the ATLAS virtualenv as a subprocess of gaea_v's
atlas_hook. It IMPORTS ATLAS code read-only: no file of the atlas/
repo is written, no graph is saved, no learning is triggered. The
JSON-lines protocol on stdin/stdout mirrors the heph bridge pattern.

Ops:
  identity      -> git head + bridge health (binary/weights hashes)
  build_t1      -> the 50 deterministic ATLAS tasks (seed 42)
  solve         -> one task through nano-solo or ATLAS (MCTS+verifier)
  evaluate      -> the production composite verdict over a candidate
  cache_probe   -> ZOO-5xx state/cache scenarios on the real
                   CompositeVerifier memoization contract
  echo_pair     -> verdict of a candidate with and without echo text
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ATLAS_ROOT = Path.cwd()
sys.path.insert(0, str(ATLAS_ROOT))


def _git_head() -> str:
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True, cwd=ATLAS_ROOT)
    return out.stdout.strip()


class _Stack:
    """Lazy production stack, built exactly like the FASE 4 report."""

    def __init__(self) -> None:
        import yaml
        from atlas_ns.bridge.hephaestus import HephaestusBridge
        from atlas_ns.mcts.selfplay import SelfPlay
        from atlas_ns.mcts.retrieval import HybridRetriever
        from atlas_ns.verify.composite import CompositeVerifier
        from atlas_ns.verify.plugins.policy import PolicyVerifier
        from atlas_ns.verify.plugins.programmatic import \
            ProgrammaticVerifier
        from atlas_ns.verify.plugins.probe import ProbeVerifier
        from atlas_ns.verify.plugins.symbolic import SymbolicVerifier

        self.root = ATLAS_ROOT
        self.config = yaml.safe_load(
            (ATLAS_ROOT / "config.yaml").read_text(encoding="utf-8"))
        self.bridge = HephaestusBridge(self.config, repo_root=self.root)
        composite = CompositeVerifier(
            tau_approve=self.config["verifier"]["tau_approve"],
            tau_doubt=self.config["verifier"]["tau_doubt"])
        composite.register(ProgrammaticVerifier(self.config), 0.45)
        graph = Path(ATLAS_ROOT) / "profiles" / "code_qa" / "graph.json"
        composite.register(SymbolicVerifier(
            json.loads(graph.read_text(encoding="utf-8"))), 0.35)
        composite.register(ProbeVerifier(self.config,
                                         repo_root=self.root), 0.20)
        # Hard-block vote wired after the S-08 fix in atlas (policy
        # plugin, commit 4427672); weight 0.0, arithmetic unchanged.
        composite.register(PolicyVerifier(self.config), 0.0)
        self.composite = composite
        self.retriever = HybridRetriever(
            ATLAS_ROOT / "profiles" / "code_qa" / "docs",
            ATLAS_ROOT / "profiles" / "code_qa" / "graph.json")
        self.selfplay = SelfPlay(self.config, self.bridge, composite,
                                 retriever=self.retriever,
                                 root=self.root)

    def tokens_of(self, text: str) -> int:
        try:
            return len(self.bridge.tokenize(text))
        except Exception:
            return 0


_STACK: _Stack | None = None


def _stack() -> _Stack:
    global _STACK
    if _STACK is None:
        _STACK = _Stack()
    return _STACK


def op_identity(args: dict) -> dict:
    stack = _stack()
    return {"ok": True, "git_head": _git_head(),
            "health": stack.bridge.health()}


def op_build_t1(args: dict) -> dict:
    from atlas_ns.mcts.selfplay import build_suite
    tasks = build_suite(int(args.get("n", 50)),
                        int(args.get("seed", 42)))
    return {"ok": True, "tasks": tasks}


def _decision_dict(decision) -> dict:
    return {"decision": decision.decision,
            "weighted": decision.weighted_score,
            "votes": [{"verifier": v.verifier, "score": v.score,
                       "evidence": v.evidence,
                       "hard_block": v.hard_block}
                      for v in decision.votes],
            "causes": list(decision.causes)}


def op_solve(args: dict) -> dict:
    stack = _stack()
    task = args["task"]
    mode = args.get("mode", "atlas")
    budget = args.get("budget", "fast")
    max_iters = args.get("max_iters", 3)
    prune_mode = args.get("prune_mode", "verifier")
    answer_cap = int(args.get("answer_cap", 0))

    def _answer(res: dict) -> str:
        text = str(res.get("answer", ""))
        return text[:answer_cap] if answer_cap > 0 else text

    if mode == "nano":
        res = stack.selfplay.solve_nano(task)
        tokens = stack.tokens_of(res.get("answer", ""))
        out = {"ok": True, "tests_passed": res["tests_passed"],
               "decision": None, "nodes_evaluated": 0,
               "tokens_generated": tokens, "ms": res["ms"]}
        if answer_cap > 0:
            out["answer"] = _answer(res)
        return out
    res = stack.selfplay.solve_atlas(task, budget=budget,
                                     max_iters=max_iters,
                                     prune_mode=prune_mode)
    tokens = stack.tokens_of(res.get("answer", ""))
    out = {"ok": True, "tests_passed": res["tests_passed"],
           "decision": res.get("decision"),
           "nodes_evaluated": res.get("nodes_evaluated", 0),
           "nodes_pruned": res.get("nodes_pruned", 0),
           "tokens_generated": tokens, "ms": res["ms"]}
    if answer_cap > 0:
        out["answer"] = _answer(res)
    return out


def op_generate(args: dict) -> dict:
    """Candidatos RFT: generate del binario heph congelado.

    El rng del binario es fijo (20260922), asi que (prompt,
    temperature) es reproducible; la temperatura por candidato es la
    que da los 16 distintos. weights_variant permite fp32 | int8
    (H4), leyendo los pesos cuantizados publicados de hephaestus.
    Solo lectura de hermanos: ningun archivo se escribe.
    """
    stack = _stack()
    bridge = stack.bridge
    prompt = args["prompt"]
    max_new = int(args.get("max_new_tokens", 48))
    temperature = float(args.get("temperature", 0.8))
    variant = args.get("weights_variant", "fp32")
    if variant == "fp32":
        weights = bridge.resolve_weights()
    elif variant == "int8":
        weights = (bridge._repo_root.parent / "hephaestus" /
                   "artifacts" / "qint8" / "weights.bin")
        if not weights.is_file():
            raise FileNotFoundError(f"int8 weights missing: {weights}")
    else:
        raise ValueError(f"unknown weights_variant {variant!r}")
    argv = [str(bridge.resolve_bin()), "generate",
            "--manifest", str(bridge.resolve_manifest()),
            "--weights", str(weights),
            "--tokenizer", str(bridge._tokenizer_dir()),
            "--prompt", prompt,
            "--max-new-tokens", str(max_new),
            "--temperature", str(temperature)]
    import subprocess as sp
    proc = sp.run(argv, capture_output=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"heph generate failed: "
                           f"{proc.stderr[-200:]}")
    # the degenerate nano emits arbitrary byte sequences; decode
    # tolerantly instead of crashing the worker (M-06 sandbox
    # survival): the text is data, not a contract violation
    text = proc.stdout.decode("utf-8", errors="replace").strip()
    return {"ok": True, "text": text,
            "weights_variant": variant,
            "temperature": temperature}


def op_evaluate(args: dict) -> dict:
    stack = _stack()
    decision = stack.composite.evaluate(
        args["code"], {"code": args["code"], "tests": args["tests"],
                       "triplets": args.get("triplets", [])})
    return {"ok": True, "verdict": _decision_dict(decision)}


def op_echo_pair(args: dict) -> dict:
    stack = _stack()
    ctx = {"tests": args["tests"], "triplets": args.get("triplets", [])}
    base = stack.composite.evaluate(args["base_code"],
                                    dict(ctx, code=args["base_code"]))
    echo = stack.composite.evaluate(args["echo_code"],
                                    dict(ctx, code=args["echo_code"]))
    return {"ok": True,
            "base": _decision_dict(base), "echo": _decision_dict(echo)}


class _CountingPlugin:
    def __init__(self, name: str, score: float) -> None:
        self.name = name
        self.score = score
        self.calls = 0

    def verify(self, claim, context=None):
        self.calls += 1
        from atlas_ns.verify.composite import Verdict
        return Verdict(self.name, self.score, "", hard_block=False)


def op_cache_probe(args: dict) -> dict:
    from atlas_ns.verify.composite import CompositeVerifier

    results = []

    def fresh_stack():
        comp = CompositeVerifier(0.80, 0.35)
        p1 = _CountingPlugin("probe_a", 1.0)
        p2 = _CountingPlugin("probe_b", 1.0)
        comp.register(p1, 0.45)
        comp.register(p2, 0.35)
        return comp, p1, p2

    # cache_hit_stable
    comp, p1, p2 = fresh_stack()
    cache: dict = {}
    d1 = comp.evaluate_cached("claim-1", {"x": 1}, cache)
    d2 = comp.evaluate_cached("claim-1", {"x": 1}, cache)
    holds = d1.decision == d2.decision and p1.calls == 1 \
        and p2.calls == 1
    results.append({"case": "cache_hit_stable", "holds": holds,
                    "calls": p1.calls + p2.calls})

    # reregister_invalidates
    comp, p1, p2 = fresh_stack()
    cache = {}
    comp.evaluate_cached("claim-1", {"x": 1}, cache)
    before = p1.calls + p2.calls
    comp.register(_CountingPlugin("probe_c", 0.5), 0.20)
    comp.evaluate_cached("claim-1", {"x": 1}, cache)
    after = p1.calls + p2.calls
    results.append({"case": "reregister_invalidates",
                    "holds": after > before, "calls_before": before,
                    "calls_after": after})

    # context_changes_key
    comp, p1, p2 = fresh_stack()
    cache = {}
    comp.evaluate_cached("claim-1", {"tests": "A"}, cache)
    comp.evaluate_cached("claim-1", {"tests": "B"}, cache)
    results.append({"case": "context_changes_key",
                    "holds": p1.calls == 2 and p2.calls == 2,
                    "calls": p1.calls})

    # one_byte_mutation
    comp, p1, p2 = fresh_stack()
    cache = {}
    comp.evaluate_cached("claim-1", {"x": 1}, cache)
    comp.evaluate_cached("claim-2", {"x": 1}, cache)
    results.append({"case": "one_byte_mutation",
                    "holds": p1.calls == 2, "calls": p1.calls})

    # fresh_matches_cached
    comp, p1, p2 = fresh_stack()
    d_fresh = comp.evaluate("claim-1", {"x": 1})
    d_cached = comp.evaluate_cached("claim-1", {"x": 1}, {})
    results.append({"case": "fresh_matches_cached",
                    "holds": d_fresh.decision == d_cached.decision})
    return {"ok": True, "results": results}


def op_run_tests(args: dict) -> dict:
    stack = _stack()
    from atlas_ns.verify.plugins.programmatic import \
        ProgrammaticVerifier
    res = ProgrammaticVerifier(stack.config).run_in_sandbox(
        args["code"], args["tests"])
    return {"ok": True, "passed": res["passed"], "ran": res["ran"],
            "exit_code": res.get("exit_code"),
            "stderr_tail": res.get("stderr_tail", "")}


def op_lineage_decide(args: dict) -> dict:
    """G1-G4 con las reglas congeladas de ATLAS, ejecutadas verbatim.

    gaea_v mide y aporta las metricas; la decision la produce el
    codigo de ATLAS (read-only, mismo patron que solve/evaluate).
    Los umbrales salen del config.yaml de ATLAS, no de gv.
    """
    from atlas_ns.lineage.rules import (ExpansionMetrics, GrowthRules,
                                        decide_expansion)
    stack = _stack()
    growth = stack.config["lineage"]["growth"]
    rules = GrowthRules(
        min_fail_rate=growth["min_fail_rate"],
        min_unrecovered_rate=growth["min_unrecovered_rate"],
        diversity_floor=growth["diversity_floor"],
        min_generations_between=growth["min_generations_between"],
        ceiling_params=growth["ceiling_params"])
    metrics = ExpansionMetrics(**args["metrics"])
    decision = decide_expansion(metrics, rules)
    return {"ok": True, "expand": decision.expand,
            "causes": list(decision.causes), "checks": decision.checks,
            "rules_from": "atlas/config.yaml lineage.growth",
            "configured_ops": {"merge": stack.config["lineage"]["merge"],
                               "expand": stack.config["lineage"]["expand"]}}


OPS = {"identity": op_identity, "build_t1": op_build_t1,
       "solve": op_solve, "evaluate": op_evaluate,
       "generate": op_generate,
       "cache_probe": op_cache_probe, "echo_pair": op_echo_pair,
       "run_tests": op_run_tests, "lineage_decide": op_lineage_decide}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            op = req.get("op")
            if op not in OPS:
                raise KeyError(f"unknown op {op!r}")
            resp = OPS[op](req.get("args") or {})
        except Exception as exc:
            resp = {"ok": False, "error": f"{type(exc).__name__}: "
                                          f"{exc}"}
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
