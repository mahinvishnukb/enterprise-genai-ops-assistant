"""
CHUNKING — why it exists: embeddings work best over a few hundred words.
Embed an entire 40-page SOP as one vector and you get a single blurry
average that won't match a specific question about page 12. So you split
documents into overlapping windows ("chunks"), embed each chunk separately,
and retrieve only the chunks whose meaning is closest to the question.

The overlap (default 50 tokens) exists so a sentence that straddles a chunk
boundary still appears whole in at least one chunk — without overlap you'd
randomly lose context right at the cut point.

This is a simple word-count splitter (production systems often split on
sentence/paragraph boundaries with a tokenizer-aware length function, e.g.
tiktoken) but the core trade-off — chunk_size vs. overlap vs. number of
chunks — is identical.
"""
from dataclasses import dataclass


@dataclass
class Chunk:
    doc_id: str
    chunk_id: str
    text: str
    position: int


def chunk_text(doc_id: str, text: str, chunk_size: int = 220, overlap: int = 40) -> list[Chunk]:
    words = text.split()
    if not words:
        return []

    chunks: list[Chunk] = []
    start = 0
    position = 0
    step = max(chunk_size - overlap, 1)

    while start < len(words):
        window = words[start : start + chunk_size]
        chunk_str = " ".join(window)
        chunks.append(
            Chunk(doc_id=doc_id, chunk_id=f"{doc_id}::{position}", text=chunk_str, position=position)
        )
        position += 1
        start += step

    return chunks
