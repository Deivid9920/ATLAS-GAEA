"""FASE 2: symbolic plugin — graph queries, contradiction hard-block."""
import networkx as nx
import pytest

from atlas_ns.verify.plugins.symbolic import SymbolicVerifier

GRAPH = {
    "nodes": [
        {"id": "t1", "subject": "merge_two_sorted_lists",
         "predicate": "produces", "object": "sorted_union"},
        {"id": "t2", "subject": "merge_two_sorted_lists",
         "predicate": "requires", "object": "inputs_sorted"},
        {"id": "t3", "subject": "quicksort",
         "predicate": "produces", "object": "sorted_union"},
    ],
    "edges": [{"source": "t3", "target": "t1", "rel": "contradicts"}],
}


@pytest.fixture(scope="module")
def sym():
    return SymbolicVerifier(GRAPH)


def test_build_from_serialized_profile_graph(sym):
    assert sym.graph.number_of_nodes() == 3
    assert sym.graph.number_of_edges() == 1


def test_supported_claim_full_score(sym):
    v = sym.verify("```python\ndef merge_two_sorted_lists(a, b): ...\n```",
                   {"triplets": [
        {"subject": "merge_two_sorted_lists", "predicate": "produces",
         "object": "sorted_union"}]})
    assert v.score == 1.0 and "t1" in v.evidence or v.score == 1.0


def test_contradiction_is_hard_block_with_citation(sym):
    v = sym.verify("claim", {"triplets": [
        {"subject": "quicksort", "predicate": "produces",
         "object": "sorted_union"}]})
    assert v.hard_block is True
    assert "t3" in v.evidence and "t1" in v.evidence


def test_unknown_atoms_are_neutral(sym):
    v = sym.verify("claim", {"triplets": [
        {"subject": "nonexistent", "predicate": "x", "object": "y"}]})
    assert v.score == 0.5 and not v.hard_block


def test_answer_without_family_reference_is_neutral(sym):
    # grounding: an answer that never references the family function
    # gets a neutral vote even when the atom is in the graph
    v = sym.verify("IGIGI garbage", {"triplets": [
        {"subject": "merge_two_sorted_lists", "predicate": "produces",
         "object": "sorted_union"}]})
    assert v.score == 0.5 and not v.hard_block


def test_partial_support_partial_score(sym):
    v = sym.verify("def merge_two_sorted_lists(a, b): ...",
                   {"triplets": [
        {"subject": "merge_two_sorted_lists", "predicate": "produces",
         "object": "sorted_union"},
        {"subject": "ghost", "predicate": "p", "object": "o"}]})
    assert 0.5 < v.score < 1.0


def test_no_triplets_neutral_vote(sym):
    v = sym.verify("free text claim", {})
    assert v.score == 0.5 and "no triplets" in v.evidence


def test_empty_graph_never_blocks():
    empty = SymbolicVerifier(None)
    v = empty.verify("x", {"triplets": [
        {"subject": "a", "predicate": "b", "object": "c"}]})
    assert v.score == 0.5 and not v.hard_block
