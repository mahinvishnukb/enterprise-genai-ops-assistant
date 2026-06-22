"""
RERANKER — second-stage relevance scoring over the vector store's initial
candidates.

Why this exists: a single embedding pass is high recall but low precision —
the HashingEmbedder's bag-of-words vectors here (or even a real neural
embedding) can rank a chunk that shares one or two stray tokens above a
chunk that actually answers the question, especially when the query is
short or the embedding space is coarse. Left alone, that means the
"context" stuffed into the LLM prompt may not actually contain the answer,
and the model fills the gap by hallucinating something plausible-sounding
instead of saying it doesn't know.

The standard production fix (Cohere Rerank, cross-encoders, BM25 fusion) has
the same two-stage shape no matter how fancy the model is: retrieve a wider
candidate set first (optimize for recall), then re-score that smaller
candidate set with a second, more precise signal (optimize for precision),
and only keep the top few after that second pass.

This module implements a lightweight lexical re-ranker (term-overlap /
BM25-lite scoring) so it has zero extra dependencies and runs in
microseconds — consistent with the rest of this RAG demo. It is a deliberate
drop-in seam: swapping in a real cross-encoder (e.g.
`cross-encoder/ms-marco-MiniLM-L-6-v2` via sentence-transformers, or the
Cohere Rerank API) only requires changing what `rerank()` does internally;
every caller already treats it as "candidates in, fewer + better-ordered
candidates out."
"""
import math
import re
from collections import Counter

from app.rag.chunking import Chunk
from app.rag.embeddings import STOPWORDS

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


def _lexical_score(query_tokens: Counter, chunk_tokens: Counter) -> float:
    """Term-overlap weighted by query term frequency, normalized by chunk
    length so long chunks don't win purely by containing more words."""
    if not chunk_tokens:
        return 0.0
    overlap = sum(min(count, chunk_tokens.get(term, 0)) for term, count in query_tokens.items())
    if overlap == 0:
        return 0.0
    chunk_len = sum(chunk_tokens.values())
    return overlap / math.sqrt(chunk_len)


def rerank(
    question: str,
    candidates: list[tuple[Chunk, float]],
    top_k: int = 4,
    vector_weight: float = 0.5,
    lexical_weight: float = 0.5,
) -> list[tuple[Chunk, float]]:
    """Re-score `candidates` (chunk, vector_similarity) pairs by blending the
    original vector score with a lexical relevance score, then return the
    best `top_k`, re-sorted and re-scored.

    Blending (rather than replacing) the vector score keeps semantic matches
    that use different wording than the query, while the lexical term still
    pulls a chunk that literally contains the question's keywords back
    toward the top — which is exactly the failure mode that causes a
    knowledge agent to confidently answer from the wrong chunk.
    """
    if not candidates:
        return []

    query_tokens = Counter(_tokenize(question))
    if not query_tokens:
        # Nothing left after stripping stopwords (e.g. "what is this?") —
        # fall back to the vector ranking as-is.
        return candidates[:top_k]

    rescored = []
    for chunk, vec_score in candidates:
        chunk_tokens = Counter(_tokenize(chunk.text))
        lex_score = _lexical_score(query_tokens, chunk_tokens)
        # Saturating curve maps [0, inf) -> [0, 1) so the lexical signal is
        # comparable in magnitude to cosine similarity instead of swamping it.
        lex_score_norm = lex_score / (lex_score + 1.0)
        blended = vector_weight * max(vec_score, 0.0) + lexical_weight * lex_score_norm
        rescored.append((chunk, blended))

    rescored.sort(key=lambda pair: pair[1], reverse=True)
    return rescored[:top_k]
