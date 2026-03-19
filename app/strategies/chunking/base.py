from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from app.schema.dto.prepared_email_chunk import ChunkPiece


class Chunkifier(ABC):
    """
    Base interface for chunking strategies.

    Implementations should:
    - accept a single body of text
    - return ordered chunk pieces
    - expose strategy metadata for persistence/debugging
    """

    strategy_name: str
    strategy_version: str

    @abstractmethod
    def chunk(self, text: str) -> List[ChunkPiece]:
        raise NotImplementedError
