from app.strategies.chunking.base import Chunkifier
from app.strategies.chunking.fixed_token import FixedTokenChunkifier
from app.strategies.chunking.paragraph import ParagraphChunkifier


def build_chunkifier(
    strategy: str,
    *,
    chunk_size: int = 400,
    overlap: int = 50,
) -> Chunkifier:
    normalized = strategy.strip().lower()

    if normalized in {"fixed", "fixed_token", "token"}:
        return FixedTokenChunkifier(chunk_size=chunk_size, overlap=overlap)

    if normalized in {"paragraph", "paragraphs"}:
        return ParagraphChunkifier(target_size=chunk_size, overlap=overlap)

    raise ValueError(f"Unsupported chunking strategy: {strategy}")
