"""
KnowledgeAgent — answers questions over uploaded enterprise documents
(PDF/DOCX/PPT/CSV). This is the "RAG" feature end to end:

  ingest(doc_id, text):  chunk_text -> embed each chunk -> store in vector DB
  answer(question):      embed the question -> vector_store.query (top-k
                          nearest chunks) -> stuff those chunks into the
                          prompt -> ask the LLM to answer using ONLY that
                          context -> return answer + which chunks were used

The "only using that context" instruction in the system prompt is the
difference between RAG and just asking a model to hallucinate from its
training data — it's what makes the answer grounded in *your* documents and
auditable (you can show exactly which chunk the answer came from).
"""
from app.core.llm_client import LLMClient
from app.rag.chunking import chunk_text
from app.rag.vector_store import VectorStore, get_vector_store

SYSTEM_PROMPT = (
    "You are an enterprise knowledge assistant. Answer the user's question "
    "using ONLY the provided context chunks. If the answer is not contained "
    "in the context, say you don't have enough information. Be concise."
)


class KnowledgeAgent:
    def __init__(self, vector_store: VectorStore | None = None, llm: LLMClient | None = None):
        self.vector_store = vector_store or get_vector_store()
        self.llm = llm or LLMClient()

    def ingest(self, doc_id: str, text: str) -> int:
        """Chunk + embed + store a document. Returns number of chunks created."""
        chunks = chunk_text(doc_id, text)
        self.vector_store.add(chunks)
        return len(chunks)

    def answer(self, question: str, top_k: int = 4) -> dict:
        hits = self.vector_store.query(question, top_k=top_k)
        if not hits:
            return {
                "answer": "No documents have been ingested yet, so I have no context to answer from.",
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
