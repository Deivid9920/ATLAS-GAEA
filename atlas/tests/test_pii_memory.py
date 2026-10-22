"""FASE 3: PII scrubbing BEFORE memory, BM25 retrieval, graph versions."""
import pytest

from atlas_ns.memory.episodic import EpisodicMemory, GraphVersions
from atlas_ns.safety.pii import PIIScrubber


# -- PII --------------------------------------------------------------------
def test_scrub_email_phone_card():
    scrubber = PIIScrubber()
    text = ("contact juan.perez@example.com or +52 55 1234 5678, "
            "card 4111 1111 1111 1111")
    clean, counts = scrubber.scrub(text)
    assert "juan.perez@example.com" not in clean
    assert "[EMAIL]" in clean and "[PHONE]" in clean and "[CARD]" in clean
    assert counts["email"] == 1 and counts["card"] == 1


def test_scrub_dictionary_terms():
    scrubber = PIIScrubber(extra_terms=["María López", "Acme Corp"])
    clean, counts = scrubber.scrub("María López works at Acme Corp")
    assert "María López" not in clean and "Acme Corp" not in clean
    assert counts["dictionary"] == 2


def test_scrub_disabled_keeps_text():
    scrubber = PIIScrubber({"safety": {"pii_scrub": False}})
    clean, counts = scrubber.scrub("mail a@b.com")
    assert clean == "mail a@b.com" and counts == {}


def test_audit_event_has_counts_not_contents():
    scrubber = PIIScrubber(extra_terms=["Secret Name"])
    _, event = scrubber.scrub_audit_event("Secret Name mailed a@b.com")
    assert event["content_in_audit"] is False
    assert "Secret Name" not in str(event)
    assert event["total"] == 2


# -- memory -------------------------------------------------------------------
def test_memory_stores_scrubbed_episodes():
    mem = EpisodicMemory({"memory": {"max_entries": 10}})
    mem.add("t1", "task from juan.perez@example.com",
            ["hephaestus", "verify"], "used card 4111 1111 1111 1111",
            "lesson: none")
    record = mem._records["t1"]
    assert "juan.perez@example.com" not in record["goal"]
    assert "4111" not in record["result"]
    assert record["pii_counts"]


def test_bm25_retrieval_ranks_relevant_first():
    mem = EpisodicMemory({"memory": {"max_entries": 10}})
    mem.add("t_sort", "merge two sorted lists task",
            ["hephaestus", "verify"], "two-pointer merge worked",
            "lesson: guard empty inputs")
    mem.add("t_tax", "quarterly tax report parsing",
            ["verify"], "schema validated",
            "lesson: always pin schema version")
    hits = mem.retrieve("merge sorted lists", k=2)
    assert hits[0]["task_id"] == "t_sort"
    assert hits[0]["bm25"] > 0


def test_memory_lru_cap():
    mem = EpisodicMemory({"memory": {"max_entries": 3}})
    for i in range(6):
        mem.add(f"t{i}", f"goal {i}", ["verify"], f"result {i}",
                f"lesson {i}")
    assert len(mem) == 3
    assert set(mem._records) == {"t3", "t4", "t5"}


# -- graph versions ---------------------------------------------------------------
def test_graph_apply_change_records_cause_and_diff():
    store = GraphVersions()
    e1 = store.apply_change(
        "selfplay task added merge triplet",
        add_nodes=[{"id": "n1", "subject": "merge", "predicate": "produces",
                    "object": "sorted"}])
    assert e1["cause"].startswith("selfplay")
    assert e1["diff"]["add_nodes"] == ["n1"]
    assert store.history[-1]["gen"] == 1


def test_graph_snapshot_hash_changes_with_content():
    store = GraphVersions()
    h0 = store.snapshot_hash()
    store.apply_change("c1", add_nodes=[{"id": "n1"}])
    h1 = store.snapshot_hash()
    store.apply_change("c2", add_nodes=[{"id": "n2"}])
    h2 = store.snapshot_hash()
    assert h0 != h1 != h2


def test_graph_duplicate_nodes_deduped():
    store = GraphVersions()
    store.apply_change("c1", add_nodes=[{"id": "n1", "x": 1}])
    entry = store.apply_change("c1 again", add_nodes=[{"id": "n1", "x": 1}])
    assert entry["diff"]["add_nodes"] == []
    assert len(store.graph["nodes"]) == 1


def test_graph_save_load_roundtrip(tmp_path):
    store = GraphVersions()
    store.apply_change("cause A", add_nodes=[{"id": "n1"}],
                       add_edges=[{"source": "n1", "target": "n1",
                                   "rel": "supports"}])
    p = tmp_path / "graph_versions.json"
    store.save(p)
    loaded = GraphVersions.load(p)
    assert loaded.snapshot_hash() == store.snapshot_hash()
    assert loaded.history[-1]["cause"] == "cause A"
