from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PreparedEmailChunk(BaseModel):
    email_id: UUID
    thread_id: str

    message_index: int
    message_count_in_thread: int

    chunk_index: int
    chunk_count_for_message: int

    subject: str | None = None
    sender: str | None = None
    sent_at: datetime | None = None

    chunk_text: str
    embedding_text: str
    char_count: int

    chunking_strategy: str
    chunking_version: str
    normalizer_version: str

    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkPiece(BaseModel):
    text: str
    chunk_index: int
    chunk_count: int
    char_count: int
