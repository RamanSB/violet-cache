from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from pydantic import BaseModel


class ChunkPiece(BaseModel):
    text: str
    chunk_index: int
    chunk_count: int
    char_count: int


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
