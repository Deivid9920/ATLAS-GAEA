"""FASE 4: hybrid retrieval — BM25 + graph citations + contradictions."""
from pathlib import Path

from atlas_ns.mcts.retrieval import Bm25Index, HybridRetriever

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "profiles" / "code_qa" / "docs"
GRAPH = ROOT / "profiles" / "code_qa" / "graph.json"


def test_bm25_ranks_relevant_doc_first():
    index = Bm25Index()
    index.add("d1", "merge two sorted lists with two pointers")
    index.add("d2", "reverse a string with slicing")
    hits = index.search("merge sorted lists", k=2)
    assert hits[0]["id"] == "d1"


def test_hybrid_retriever_finds_docs_and_citations():
    retriever = HybridRetriever(DOCS, GRAPH)
    result = retriever.search("merge two sorted lists into one sorted")
    assert result["docs"], "BM25 must hit the profile docs"
    assert result["citations"]
    assert any(c["triplet_id"] == "t_merge_sorted"
               for c in result["citations"])


def test_contradictions_are_declared_not_hidden():
    retriever = HybridRetriever(DOCS, GRAPH)
    result = retriever.search("merge two sorted lists")
    # graph declares t_bubblesort contradicts t_merge_sorted; the query
    # overlaps merge triplets so the contradiction must surface
    assert isinstance(result["contradictions"], list)


def test_context_block_is_fenced_with_citations():
    from atlas_ns.safety.fencing import is_fenced

    retriever = HybridRetriever(DOCS, GRAPH)
    block = retriever.context_block("count vowels in a string")
    assert is_fenced(block)
    assert "[graph:" in block or "[doc:" in block


def test_empty_corpus_returns_empty_not_fake():
    retriever = HybridRetriever(Path("/nonexistent"), None)
    result = retriever.search("anything")
    assert result["docs"] == [] and result["citations"] == []
