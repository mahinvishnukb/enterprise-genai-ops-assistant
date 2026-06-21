from app.rag.chunking import chunk_text
from app.rag.embeddings import HashingEmbedder, cosine_similarity


def test_chunk_text_respects_overlap():
    text = " ".join(f"word{i}" for i in range(500))
    chunks = chunk_text("doc1", text, chunk_size=100, overlap=20)

    assert len(chunks) > 1
    # consecutive chunks should share the overlapping words
    first_tail = chunks[0].text.split()[-20:]
    second_head = chunks[1].text.split()[:20]
    assert first_tail == second_head


def test_chunk_text_empty_string():
    assert chunk_text("doc1", "") == []


def test_hashing_embedder_is_deterministic():
    embedder = HashingEmbedder(dim=64)
    v1 = embedder.embed("leave policy onboarding")
    v2 = embedder.embed("leave policy onboarding")
    assert v1 == v2
    assert len(v1) == 64


def test_cosine_similarity_prefers_overlapping_vocabulary():
    embedder = HashingEmbedder(dim=64)
    query = embedder.embed("what is the leave policy")
    relevant = embedder.embed("the leave policy allows 20 days of paid leave")
    irrelevant = embedder.embed("shipment delays in the logistics network")

    assert cosine_similarity(query, relevant) > cosine_similarity(query, irrelevant)
