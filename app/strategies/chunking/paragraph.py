import re
from typing import List

from app.strategies.chunking.base import ChunkPiece, Chunkifier


class ParagraphChunkifier(Chunkifier):
    """
    Paragraph-aware chunker.

    Strategy:
    - split on blank lines
    - keep paragraph boundaries where possible
    - merge paragraphs until target size
    - if a paragraph is too large, fall back to fixed-size word windows
    """

    strategy_name = "paragraph"
    strategy_version = "v1"

    def __init__(self, target_size: int = 400, overlap: int = 50):
        if target_size <= 0:
            raise ValueError("target_size must be > 0")
        if overlap < 0:
            raise ValueError("overlap must be >= 0")
        if overlap >= target_size:
            raise ValueError("overlap must be smaller than target_size")

        self.target_size = target_size
        self.overlap = overlap

    def chunk(self, text: str) -> List[ChunkPiece]:
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            return []

        paragraphs = self._split_paragraphs(cleaned_text)
        if not paragraphs:
            return []

        chunks: list[str] = []
        current_parts: list[str] = []
        current_token_count = 0

        for paragraph in paragraphs:
            paragraph_token_count = self._token_count(paragraph)

            # If a single paragraph is too large, flush current and split paragraph.
            if paragraph_token_count > self.target_size:
                if current_parts:
                    chunks.append("\n\n".join(current_parts).strip())
                    current_parts = []
                    current_token_count = 0

                oversized_chunks = self._split_large_paragraph(paragraph)
                chunks.extend(oversized_chunks)
                continue

            # If adding paragraph exceeds target, flush current chunk first.
            if current_parts and (
                current_token_count + paragraph_token_count > self.target_size
            ):
                chunks.append("\n\n".join(current_parts).strip())
                current_parts = []
                current_token_count = 0

            current_parts.append(paragraph)
            current_token_count += paragraph_token_count

        if current_parts:
            chunks.append("\n\n".join(current_parts).strip())

        # Optional lightweight overlap by carrying tail words from previous chunk.
        overlapped_chunks = self._apply_overlap(chunks)

        return [
            ChunkPiece(
                text=chunk_text,
                chunk_index=i,
                chunk_count=len(overlapped_chunks),
                char_count=len(chunk_text),
            )
            for i, chunk_text in enumerate(overlapped_chunks)
        ]

    def _split_paragraphs(self, text: str) -> list[str]:
        raw_parts = re.split(r"\n\s*\n", text)
        return [part.strip() for part in raw_parts if part and part.strip()]

    def _token_count(self, text: str) -> int:
        return len(text.split())

    def _split_large_paragraph(self, paragraph: str) -> list[str]:
        words = paragraph.split()
        if not words:
            return []

        chunks: list[str] = []
        step = self.target_size - self.overlap
        start = 0

        while start < len(words):
            end = min(start + self.target_size, len(words))
            chunk_text = " ".join(words[start:end]).strip()
            if chunk_text:
                chunks.append(chunk_text)

            if end >= len(words):
                break

            start += step

        return chunks

    def _apply_overlap(self, chunks: list[str]) -> list[str]:
        if not chunks or self.overlap == 0:
            return chunks

        result: list[str] = []
        previous_words: list[str] = []

        for index, chunk in enumerate(chunks):
            words = chunk.split()

            if index == 0:
                result.append(chunk)
            else:
                overlap_words = (
                    previous_words[-self.overlap :] if previous_words else []
                )
                if overlap_words:
                    merged = " ".join(overlap_words + words).strip()
                    result.append(merged)
                else:
                    result.append(chunk)

            previous_words = words

        return result
