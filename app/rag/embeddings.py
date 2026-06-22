"""
EMBEDDINGS — turning text into a vector of numbers such that "similar
meaning" -> "small distance" between vectors. This is the entire trick that
makes semantic search possible: you can't grep a PDF for "leave policy" and
match a paragraph that says "time-off entitlement", but two embeddings of
those phrases land close together in vector space.

Production options (swap-in, same interface as below):
  - OpenAI `text-embedding-3-small` — best quality, costs money, needs a key.
  - sentence-transformers (`all-MiniLM-L6-v2`) — free, local, but a ~90MB
    model download on first use.

HashingEmbedder below is neither of those — it's the "feature hashing trick"
(same idea as sklearn's HashingVectorizer): hash each word into one of N
buckets, count term frequency per bucket, L2-normalize. It is deterministic,
needs zero downloads/network/API key, and runs in microseconds — which is
exactly why it's the right choice for CI and for this demo. It will never
match a neural embedding's semantic nuance (it can't tell "happy" and "glad"
are related), but cosine similarity over it still correctly favors chunks
that share vocabulary with the question, which is enough to prove the RAG
pipeline (chunk -> embed -> store -> retrieve -> answer) end-to-end.

The interface (`embed(text) -> list[float]`) is what matters for the
interview: `KnowledgeAgent` and `VectorStore` only ever call `.embed()`, so
swapping HashingEmbedder for an OpenAIEmbedder is a one-line change in
core/config.py, not a rewrite.
"""
import hashlib
import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# A tiny stopword list. Without this, function words ("the", "is", "what")
# dominate the bag-of-words counts and swamp the actual content words,
# which is especially visible at small hash dimensions where collisions
# are already eating into precision. Filtering them is the single highest
# value/effort improvement for this toy embedder.
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was",
    "what", "when", "where", "which", "who", "will", "with",
}

# Public alias — the reranker (app/rag/reranker.py) reuses the same stopword
# list so lexical-overlap scoring is consistent with how the embedder itself
# weighs content words vs. function words.
STOPWORDS = _STOPWORDS


class Embedder:
    """Interface every embedding backend implements."""

    dim: int

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class HashingEmbedder(Embedder):
    def __init__(self, dim: int = 256):
        self.dim = dim

    def _tokenize(self, text: str) -> list[str]:
        return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = self._tokenize(text)
        counts = Counter(tokens)
        for token, count in counts.items():
            bucket = int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dim
            vec[bucket] += count
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)
