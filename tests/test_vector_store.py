from app.rag.chunking import chunk_text
from app.rag.vector_store import InMemoryVectorStore


def test_in_memory_store_returns_most_relevant_chunk_first():
    store = InMemoryVectorStore()
    leave_doc = chunk_text("hr_policy", "Employees get 20 days of paid leave per year under the leave policy.")
    shipping_doc = chunk_text("ops_report", "Shipment delays increased due to port congestion last quarter.")
    store.add(leave_doc + shipping_doc)

    hits = store.query("what is the leave policy", top_k=1)

    assert len(hits) == 1
    assert hits[0][0].doc_id == "hr_policy"


def test_in_memory_store_empty_query_returns_nothing():
    store = InMemoryVectorStore()
    assert store.query("anything") == []
