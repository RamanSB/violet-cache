from typing import List

from app.strategies.chunking.base import ChunkPiece, Chunkifier


class FixedTokenChunkifier(Chunkifier):
    """
    Simple token-ish chunker.

    For now this uses whitespace word splitting as an approximation.
    Later you can swap this to tiktoken without changing the interface.
    """

    strategy_name = "fixed_token"
    strategy_version = "v1"

    def __init__(self, chunk_size: int = 400, overlap: int = 50):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if overlap < 0:
            raise ValueError("overlap must be >= 0")
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")

        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> List[ChunkPiece]:
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            return []

        tokens = cleaned_text.split()
        if not tokens:
            return []

        chunks: list[str] = []
        step = self.chunk_size - self.overlap
        start = 0

        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_text = " ".join(tokens[start:end]).strip()
            if chunk_text:
                chunks.append(chunk_text)

            if end >= len(tokens):
                break

            start += step

        return [
            ChunkPiece(
                text=chunk_text,
                chunk_index=i,
                chunk_count=len(chunks),
                char_count=len(chunk_text),
            )
            for i, chunk_text in enumerate(chunks)
        ]
