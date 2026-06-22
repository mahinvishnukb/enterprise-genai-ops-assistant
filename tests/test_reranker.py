from app.rag.chunking import Chunk
from app.rag.reranker import rerank


def test_rerank_promotes_lexically_relevant_chunk_over_weak_vector_match():
    relevant = Chunk(doc_id="hr", chunk_id="hr::0", text="Employees receive 20 days of paid annual leave.", position=0)
    irrelevant = Chunk(doc_id="ops", chunk_id="ops::0", text="Shipment delays increased due to port congestion.", position=0)

    # Simulate the embedder having (wrongly) scored the irrelevant chunk
    # slightly higher than the relevant one on the first pass.
    candidates = [(irrelevant, 0.42), (relevant, 0.40)]

    hits = rerank("how many days of annual leave do employees get?", candidates, top_k=2)

    assert hits[0][0].doc_id == "hr"


def test_rerank_returns_at_most_top_k():
    chunks = [Chunk(doc_id="d", chunk_id=f"d::{i}", text=f"chunk number {i} about leave policy", position=i) for i in range(10)]
    candidates = [(c, 0.5) for c in chunks]

    hits = rerank("leave policy", candidates, top_k=3)

    assert len(hits) == 3


def test_rerank_empty_candidates_returns_empty():
    assert rerank("anything", [], top_k=4) == []


def test_rerank_falls_back_to_vector_order_when_query_has_no_content_words():
    chunk_a = Chunk(doc_id="a", chunk_id="a::0", text="alpha", position=0)
    chunk_b = Chunk(doc_id="b", chunk_id="b::0", text="beta", position=0)
    candidates = [(chunk_a, 0.9), (chunk_b, 0.1)]

    # "what is this" is entirely stopwords after tokenization
    hits = rerank("what is this", candidates, top_k=2)

    assert hits[0][0].doc_id == "a"
