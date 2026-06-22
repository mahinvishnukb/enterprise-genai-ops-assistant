"""
KnowledgeAgent — answers questions over uploaded enterprise documents
(PDF/DOCX/PPT/CSV). This is the "RAG" feature end to end:

  ingest(doc_id, text):  chunk_text -> embed each chunk -> store in vector DB
                          (idempotent: replaces any prior chunks for the same
                          doc_id first, so restarting the app or re-uploading
                          a file never silently duplicates chunks)
  answer(question):      embed the question -> vector_store.query (wide
                          top-N candidate pull) -> rerank() blends the
                          original vector score with a lexical-overlap score
                          to pick the best top-k -> if even the best
                          candidate isn't relevant enough, refuse rather than
                          guess -> stuff the surviving chunks into the prompt
                          -> ask the LLM to answer using ONLY that context ->
                          return answer + which chunks were used

The "only using that context" instruction in the system prompt is the
difference between RAG and just asking a model to hallucinate from its
training data — it's what makes the answer grounded in *your* documents and
auditable (you can show exactly which chunk the answer came from). The
reranking + relevance-floor steps below exist for the same reason: a single
embedding pass is recall-oriented and will happily hand the LLM four chunks
even when none of them are actually relevant, and a model handed weak
context tends to paper over the gap with a fluent-sounding guess instead of
admitting it doesn't know.
"""
from app.core.llm_client import LLMClient
from app.rag.chunking import chunk_text
from app.rag.reranker import rerank
from app.rag.vector_store import VectorStore, get_vector_store

SYSTEM_PROMPT = (
    "You are an enterprise knowledge assistant. Answer the user's question "
    "using ONLY the provided context chunks. If the answer is not contained "
    "in the context, say you don't have enough information. Be concise."
)

# How many extra candidates to pull from the vector store before reranking.
# A wider net here means the lexical reranker has more to work with, which
# improves the odds that the chunk actually containing the answer survives
# into the final top_k even if the (toy) embedder under-ranked it initially.
CANDIDATE_MULTIPLIER = 3

# Blended rerank score below this means "not actually relevant" — refuse
# instead of stuffing weak context into the prompt and inviting a
# hallucinated answer.
MIN_RELEVANCE = 0.08


class KnowledgeAgent:
    def __init__(self, vector_store: VectorStore | None = None, llm: LLMClient | None = None):
        self.vector_store = vector_store or get_vector_store()
        self.llm = llm or LLMClient()

    def ingest(self, doc_id: str, text: str) -> int:
        """Chunk + embed + store a document. Returns number of chunks created.

        Idempotent by doc_id: any chunks previously stored under this doc_id
        are removed first. Without this, re-ingesting the same document
        (e.g. the built-in sample docs reloaded on every server restart)
        keeps appending duplicate chunks forever.
        """
        chunks = chunk_text(doc_id, text)
        self.vector_store.delete(doc_id)
        self.vector_store.add(chunks)
        return len(chunks)

    def answer(self, question: str, top_k: int = 4) -> dict:
        candidate_k = max(top_k * CANDIDATE_MULTIPLIER, top_k)
        candidates = self.vector_store.query(question, top_k=candidate_k)
        if not candidates:
            return {
                "answer": "No documents have been ingested yet, so I have no context to answer from.",
                "sources": [],
            }

        hits = rerank(question, candidates, top_k=top_k)
        if not hits or hits[0][1] < MIN_RELEVANCE:
            return {
                "answer": (
                    "I couldn't find anything in the ingested documents relevant enough to "
                    "answer that confidently. Try rephrasing, or upload a document that covers "
                    "this topic."
                ),
                "sources": [],
            }

        context = "\n\n---\n\n".join(chunk.text for chunk, _score in hits)
        user_prompt = f"Context:\n{context}\n\nQuestion: {question}"
        answer_text = self.llm.chat(system=SYSTEM_PROMPT, user=user_prompt)

        return {
            "answer": answer_text,
            "sources": [
                {"doc_id": chunk.doc_id, "chunk_id": chunk.chunk_id, "score": round(score, 4)}
                for chunk, score in hits
            ],
        }
