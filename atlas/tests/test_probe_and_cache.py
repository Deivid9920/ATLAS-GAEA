"""FASE 2: probe bridge honesty + cache with signature invalidation."""
import time

import pytest
import yaml

from atlas_ns.audit.chain import AuditChain
from atlas_ns.verify.cache import VerdictCache
from atlas_ns.verify.composite import CompositeVerifier, Verdict
from atlas_ns.verify.plugins.probe import ProbeVerifier
from atlas_ns.verify.plugins.programmatic import ProgrammaticVerifier
from atlas_ns.verify.plugins.symbolic import SymbolicVerifier

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


class Fake:
    def __init__(self, name, score):
        self.name, self._s = name, score

    def verify(self, claim, context):
        return Verdict(self.name, self._s, "", False)


# -- probe -----------------------------------------------------------------
def test_probe_reports_unavailable_honestly():
    probe = ProbeVerifier(repo_root=ROOT)
    state = probe.status()
    v = probe.verify("any claim", {})
    if not state["available"]:
        assert v.score == 0.5 and "unavailable" in v.evidence
    else:
        assert v.score >= 0.0  # real artifacts present: still not fabricated


def test_probe_recalibration_job_logs(tmp_path):
    # Enmienda pre-registrada (entregas/PENDIENTES_POST_RELEASE.md, fila #13 de
    # ANCHOR_CHANGES.md): tmp_path ES el repo_root — la suite no toca el log real.
    probe = ProbeVerifier(repo_root=tmp_path)
    rec = probe.recalibrate()
    assert rec["status"] in ("unavailable", "queued")
    log = tmp_path / "logs" / "probe_recalibration.jsonl"
    assert log.is_file()
    lines = log.read_text().strip().splitlines()
    assert len(lines) >= 1


def test_probe_ignores_gitkeep_stub_artifact(tmp_path):
    # Enmienda #18 (Lote 4 v1.3.0): el stub de contrato .gitkeep de
    # cassandra/artifacts/probes/ NUNCA cuenta como artefacto entrenado.
    # Con el hermano integrado, un filtro por p.suffix lo dejaba pasar
    # (un dotfile tiene Path.suffix == "") y el estado mentia
    # available=True con un artefacto fantasma.
    root = tmp_path / "fake_atlas_root"
    probes = tmp_path / "cassandra" / "artifacts" / "probes"
    probes.mkdir(parents=True)
    (probes / ".gitkeep").write_text("", encoding="utf-8")

    probe = ProbeVerifier(repo_root=root)
    state = probe.status()
    assert state["available"] is False
    assert state["reason"] == "no trained probe artifacts"
    v = probe.verify("any claim", {})
    assert v.score == 0.5 and "unavailable" in v.evidence

    # Con un bundle real junto al stub, el estado es disponible y el
    # stub no aparece listado.
    (probes / "gpt2_best.joblib").write_bytes(b"bundle")
    state = probe.status()
    assert state["available"] is True
    assert state["artifacts"] == ["gpt2_best.joblib"]


# -- composite wiring --------------------------------------------------------
def build_composite(config) -> tuple[CompositeVerifier, dict]:
    cv = CompositeVerifier(
        tau_approve=config["verifier"]["tau_approve"],
        tau_doubt=config["verifier"]["tau_doubt"])
    cv.register(ProgrammaticVerifier(config), config["verifier"]["plugins"]["programmatic"])
    cv.register(SymbolicVerifier({"nodes": [], "edges": []}),
                config["verifier"]["plugins"]["symbolic"])
    cv.register(ProbeVerifier(config, repo_root=ROOT),
                config["verifier"]["plugins"]["probe"])
    return cv, dict(config["verifier"]["plugins"])


@pytest.fixture(scope="module")
def wired():
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    return build_composite(config)


def test_vote_uses_profile_weights(wired):
    cv, weights = wired
    d = cv.evaluate("x", {"patterns": ["."], "triplets": [
        {"subject": "a", "predicate": "b", "object": "c"}]})
    # weights honored exactly: rebuild expected weighted score
    total = sum(weights.values())
    scores = {v.verifier: v.score for v in d.votes}
    expected = sum(weights[k] * scores[k] for k in weights) / total
    assert d.weighted_score == pytest.approx(expected)


def test_block_from_symbolic_contradiction(wired):
    cv, _ = wired
    graph = {
        "nodes": [{"id": "q", "subject": "bad_sort", "predicate": "produces",
                   "object": "sorted_union"},
                  {"id": "w", "subject": "merge_two_sorted_lists",
                   "predicate": "produces", "object": "sorted_union"}],
        "edges": [{"source": "q", "target": "w", "rel": "contradicts"}],
    }
    sym = [p for p in cv._plugins if p.name == "symbolic"][0]
    sym.graph = __import__("networkx").DiGraph()
    for n in graph["nodes"]:
        sym.graph.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
    for e in graph["edges"]:
        sym.graph.add_edge(e["source"], e["target"], rel=e["rel"])
    d = cv.evaluate("x", {"triplets": [
        {"subject": "bad_sort", "predicate": "produces",
         "object": "sorted_union"}]})
    assert d.decision == "block"


# -- cache (#19) ---------------------------------------------------------------
def test_cache_hit_rate_over_90pct_on_mcts_like_workload():
    cv = CompositeVerifier(0.8, 0.35)
    cv.register(Fake("programmatic", 0.9), 0.45)
    cv.register(Fake("symbolic", 0.9), 0.35)
    cv.register(Fake("probe", 0.5), 0.20)
    cache = VerdictCache(cv, capacity=1000)

    claims = [f"node-{i}" for i in range(10)]      # 10 distinct
    workload = claims * 20                          # 200 evaluations
    for c in workload:
        cache.evaluate(c, {})
    assert cache.hit_rate > 0.90
    assert cache.stats()["entries"] == 10


def test_cache_signature_invalidation():
    cv = CompositeVerifier(0.8, 0.35)
    cv.register(Fake("programmatic", 0.9), 0.45)
    cache = VerdictCache(cv, capacity=10)
    d1 = cache.evaluate("q", {})
    cv.register(Fake("symbolic", 0.9), 0.35)        # registry changed
    d2 = cache.evaluate("q", {})
    assert d2 is not d1                              # invalidated
    assert cache.stats()["entries"] == 1             # store was cleared


def test_cache_respects_capacity():
    cv = CompositeVerifier(0.8, 0.35)
    cv.register(Fake("programmatic", 0.9), 0.45)
    cache = VerdictCache(cv, capacity=5)
    for i in range(20):
        cache.evaluate(f"c{i}", {})
    assert cache.stats()["entries"] == 5
