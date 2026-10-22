"""ATLAS scaffolder: creates the contracted tree; never overwrites.

Idempotent: existing files are kept (the 4 implemented anchors and
their tests are copied from the specification package BEFORE running
this script). Run from the repo root: python3 scripts/scaffold.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STUBS: dict[str, str] = {
"atlas_ns/bridge/hephaestus.py": (
    "HEPHAESTUS bridge (#9): subprocess wrapper over build/heph speaking "
    "JSON-lines on stdin/stdout — ops {generate, tokenize, health}; "
    "timeout + bounded backoff + health-check; fail-loud if the binary "
    "is missing (bridge-check certifies the contract)."),

"atlas_ns/learning/active_learning.py": (
    "Active learning (#15): queue of verifier abstentions + user "
    "feedback -> locally labeled examples (JSONL); consumed by the RFT "
    "cycle. No external labeling services."),

"atlas_ns/learning/curriculum.py": (
    "Curriculum from failures (#14): taxonomy of verifier failures over "
    "the profile suite -> ranks categories by dominant failure mass; "
    "emits the next selfplay focus. Deterministic ordering."),

"atlas_ns/learning/diversity_guard.py": (
    "Diversity guard (#16, inherited from NS): distinct-n / self-BLEU "
    "style diversity over RFT outputs; floor enforced as part of RFT "
    "fitness — anti reward-hacking guard (no degenerate 'never "
    "contradict' policies)."),

"atlas_ns/learning/rft.py": (
    "RFT loop (FASE 5): STaR by rejection sampling — generate N "
    "candidates, composite verifier filters, SFT (LoRA, CPU 0.5B; NS "
    "nano for smoke) over successes; diversity floor + curriculum + "
    "active-learning queue integrated; every round audited."),

"atlas_ns/mcts/retrieval.py": (
    "Hybrid retrieval (#2, #4): pure-Python BM25 over profile docs + "
    "symbolic-graph expansion with per-triplet citations; declares "
    "contradictions between sources instead of hiding them."),

"atlas_ns/mcts/search.py": (
    "MCTS with verifier pruning (FASE 4): ToT/MCTS over the profile "
    "domain; node evaluation = CompositeVerifier.evaluate (memoized); "
    "UCT on verified reward; prune_below floor; anytime budgets "
    "{fast, standard, deep} with best partial answer always available "
    "(#18)."),

"atlas_ns/mcts/selfplay.py": (
    "Self-play (#13): generates tasks with integrated tests -> solves "
    "-> executes tests in sandbox -> clean RFT corpus by construction. "
    "Demo profile: code_qa (code QA with verified tests)."),

"atlas_ns/memory/episodic.py": (
    "Episodic memory (#1): {task -> plan -> result -> lesson} records "
    "with pure-Python BM25 retrieval; PII scrubbing happens BEFORE "
    "insert; graph snapshots versioned with diffs (mejora #3)."),

"atlas_ns/orchestrator/runner.py": (
    "Orchestrator runner (FASE 3): materializes machine.step — executes "
    "actions, calls tools under permissions, feeds the audit chain, "
    "persists TaskRecords and restores them after crashes."),

"atlas_ns/safety/fencing.py": (
    "Prompt-injection fencing (#10): every external text (web, files, "
    "tool outputs) enters wrapped in <untrusted> fences; the "
    "orchestrator never interprets tool commands from fenced text."),

"atlas_ns/safety/permissions.py": (
    "Tool permissions (#11): {readonly, write, execute} per tool, "
    "checked before dispatch and audited into the chain; config-driven "
    "with fail-closed defaults."),

"atlas_ns/safety/pii.py": (
    "PII scrubber (#24): local regex + dictionaries (emails, phones, "
    "card-like ids) applied BEFORE personal text enters memory/graph; "
    "audited with counts, never with contents."),

"atlas_ns/verify/plugins/programmatic.py": (
    "Programmatic verifier (#5): regex contracts, JSON-schema "
    "(jsonschema), sandboxed test execution (subprocess: no network, "
    "timeout, disposable temp dir) — score from executed evidence."),

"atlas_ns/verify/plugins/symbolic.py": (
    "Symbolic verifier (#3): networkx query over the profile graph — "
    "contradiction with a cited triplet is a hard_block; supports "
    "supports/contradicts/unknown verdicts with evidence."),

"atlas_ns/verify/plugins/probe.py": (
    "Truth-probe bridge (#6): CASSANDRA probe when the sibling repo is "
    "present (uses its published tau*); recalibration job on model "
    "change; reports 'probe: unavailable' honestly when absent."),

"scripts/mcp_server.py": (
    "MCP server (#21, FASE 1): minimal stdio JSON-RPC exposing "
    "atlas.generate and atlas.verify (the composite verifier as a "
    "tool for external agents); every call audited."),

"atlas_ns/lineage/expand.py": (
    "Expansion planner: block-stacking / Net2Net width growth "
    "(Net2Net/LLaMA-Pro style) governed by lineage.rules.decide_expansion. "
    "On CPU: DRY-RUN only — emits the expansion plan + GPU command into "
    "docs/lineage_plan.md; never trains beyond ceiling."),

"atlas_ns/lineage/registry.py": (
    "Genealogy register: append_generation({gen, parents, merge, fitness, "
    "growth_decision, hashes}) extending the promotion_log culture; "
    "render() prints the lineage tree."),

"atlas_ns/bench/three_column.py": (
    "Three-column benchmark (#22): per profile {nano-solo, ATLAS, "
    "cloud-reference} x {accuracy, cost/task, latency}; cloud column "
    "requires explicit config.bench.cloud_reference and is labeled "
    "'reference only'. Writes docs/bench_{profile}.md from real runs."),

"atlas_ns/fit/hardware.py": (
    "Auto-fitting (#23): probe cores/RAM -> recommend {profile mode, "
    "mcts budget, quant mode}; used by runner at startup; deterministic."),

"scripts/run_task.py": (
    "CLI: --config --profile --task --budget [--with-crash-test]; runs "
    "the orchestrator; crash-test kills itself mid-task and verifies "
    "resume (#17)."),

"scripts/bridge_check.py": "CLI: resolves and certifies the HEPHAESTUS bridge.",

"scripts/rft_round.py": "CLI: --config --round; one RFT cycle with guards.",

"scripts/lineage_round.py": (
    "CLI: --config --round; fitness population -> decide_expansion -> "
    "merge (real) / expand (dry-run plan) -> registry append."),

"scripts/bench.py": "CLI: --config --profile; renders the three columns.",

"scripts/audit_verify.py": "CLI: --logs logs/audit.jsonl; chain.verify() exit code.",

"scripts/chat.py": "REPL: task-oriented chat over the active profile with abstention.",
}


CLI = "\n\ndef main() -> None:\n    raise NotImplementedError(\"skeleton stub: implementation pending\")\n\n\nif __name__ == \"__main__\":\n    main()\n"


def main() -> None:
    created, kept = [], []
    for rel in ["atlas_ns/orchestrator", "atlas_ns/verify/plugins",
                "atlas_ns/audit", "atlas_ns/mcts", "atlas_ns/profiles/code_qa/data",
                "atlas_ns/profiles/finance_docs", "atlas_ns/safety",
                "atlas_ns/learning", "atlas_ns/lineage", "atlas_ns/bridge",
                "atlas_ns/memory", "atlas_ns/bench", "atlas_ns/fit",
                "scripts", "docs", "logs", "profiles/code_qa",
                "profiles/finance_docs"]:
        (ROOT / rel).mkdir(parents=True, exist_ok=True)
    for pkg in ["atlas_ns", "atlas_ns/orchestrator", "atlas_ns/verify",
                "atlas_ns/verify/plugins", "atlas_ns/audit", "atlas_ns/mcts",
                "atlas_ns/profiles", "atlas_ns/safety", "atlas_ns/learning",
                "atlas_ns/lineage", "atlas_ns/bridge", "atlas_ns/memory",
                "atlas_ns/bench", "atlas_ns/fit"]:
        p = ROOT / pkg / "__init__.py"
        if not p.exists():
            p.write_text('"""ATLAS package."""\n')
            created.append(str(p.relative_to(ROOT)))
    for rel, contract in STUBS.items():
        t = ROOT / rel
        if t.exists():
            kept.append(rel)
            continue
        t.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith((".md",)):
            t.write_text(f"# {contract}\n")
            created.append(rel)
            continue
        t.write_text(f'"""{contract}"""\n' + (CLI if rel.startswith("scripts/") else ""),
                     encoding="utf-8")
        created.append(rel)
    print("created:")
    for r in created:
        print(f" + {r}")
    if kept:
        print("kept existing:")
        for r in kept:
            print(f" = {r}")
    anchors = ["atlas_ns/verify/composite.py", "atlas_ns/audit/chain.py",
               "atlas_ns/orchestrator/machine.py", "atlas_ns/lineage/rules.py",
               "tests/test_verify_composite.py", "tests/test_audit_chain.py",
               "tests/test_orchestrator_machine.py", "tests/test_lineage_rules.py",
               "tests/test_structure.py", "config.yaml", "Makefile"]
    print("anchors:")
    for rel in anchors:
        ok = (ROOT / rel).is_file()
        print(f" {'ok' if ok else '!!'} {rel}: "
              f"{'present' if ok else 'MISSING: copy from the specification package'}")
    print("\nnext: make setup && make test")


if __name__ == "__main__":
    main()
