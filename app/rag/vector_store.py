"""
VECTOR STORE — where embeddings live and get searched. The interface is two
methods: add(chunks) and query(text, top_k). Everything above this layer
(KnowledgeAgent) never knows or cares which backend is underneath.

Two backends:
  - ChromaVectorStore: real ChromaDB, used when the `chromadb` package is
    installed (it is, per requirements.txt, once you `pip install -r
    requirements.txt` — this is the one to point to on your resume / in the
    interview as "the production vector DB").
  - InMemoryVectorStore: pure-Python/numpy cosine-similarity search. Zero
    extra dependencies, so it's the automatic fallback if chromadb isn't
    installed (e.g. a fast CI job, or this sandbox). Same interface, so
    nothing else in the codebase changes when the import fails.

This try/except-at-import-time pattern (a "feature-detected" dependency) is
worth being able to explain: it lets the same code degrade gracefully
instead of hard-crashing in a leaner environment.
"""
from app.rag.embeddings import Embedder, HashingEmbedder, cosine_similarity
from app.rag.chunking import Chunk

try:
    import chromadb

    _HAS_CHROMA = True
except ImportError:
    _HAS_CHROMA = False


class VectorStore:
    def add(self, chunks: list[Chunk]) -> None:
        raise NotImplementedError

    def query(self, text: str, top_k: int = 4) -> list[tuple[Chunk, float]]:
        raise NotImplementedError

    def delete(self, doc_id: str) -> None:
        """Remove every chunk belonging to `doc_id`. Callers use this to make
        re-ingesting a document idempotent (see KnowledgeAgent.ingest) —
        without it, re-running auto-ingest on every server restart silently
        duplicates the same chunks in the store on every boot, which both
        inflates chunk counts and increases the odds that retrieval surfaces
        several near-duplicate copies of the same passage instead of more
        useful context."""
        raise NotImplementedError


class InMemoryVectorStore(VectorStore):
    def __init__(self, embedder: Embedder | None = None):
        self.embedder = embedder or HashingEmbedder()
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []

    def add(self, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            self._chunks.append(chunk)
            self._vectors.append(self.embedder.embed(chunk.text))

    def delete(self, doc_id: str) -> None:
        kept = [(c, v) for c, v in zip(self._chunks, self._vectors) if c.doc_id != doc_id]
        self._chunks = [c for c, _ in kept]
        self._vectors = [v for _, v in kept]

    def query(self, text: str, top_k: int = 4) -> list[tuple[Chunk, float]]:
        if not self._chunks:
            return []
        query_vec = self.embedder.embed(text)
        scored = [
            (chunk, cosine_similarity(query_vec, vec))
            for chunk, vec in zip(self._chunks, self._vectors)
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]


class ChromaVectorStore(VectorStore):
    def __init__(self, collection_name: str = "enterprise_docs", embedder: Embedder | None = None,
                 persist_dir: str = "./chroma_store"):
        if not _HAS_CHROMA:
            raise RuntimeError("chromadb is not installed; use InMemoryVectorStore instead")
        self.embedder = embedder or HashingEmbedder()
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(collection_name)

    def add(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        self._collection.add(
            ids=[c.chunk_id for c in chunks],
            embeddings=[self.embedder.embed(c.text) for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[{"doc_id": c.doc_id, "position": c.position} for c in chunks],
        )

    def delete(self, doc_id: str) -> None:
        try:
            self._collection.delete(where={"doc_id": doc_id})
        except Exception:
            # Chroma raises if the collection has zero matching rows in some
            # versions; deleting "nothing" should be a harmless no-op here.
            pass

    def query(self, text: str, top_k: int = 4) -> list[tuple[Chunk, float]]:
        result = self._collection.query(query_embeddings=[self.embedder.embed(text)], n_results=top_k)
        out = []
        for doc_text, meta, dist in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            chunk = Chunk(doc_id=meta["doc_id"], chunk_id=f"{meta['doc_id']}::{meta['position']}",
                          text=doc_text, position=meta["position"])
            out.append((chunk, 1 - dist))
        return out


def get_vector_store(persist_dir: str = "./chroma_store") -> VectorStore:
    """Factory: prefer Chroma when available, fall back otherwise."""
    if _HAS_CHROMA:
        try:
            return ChromaVectorStore(persist_dir=persist_dir)
        except Exception:
            pass
    return InMemoryVectorStore()
