from typing import Dict, List
from app.models.models import EmailChunk
from app.repositories.email_chunk import EmailChunkRepository
from app.schema.dto.prepared_email_chunk import PreparedEmailChunk


class EmailChunkService:

    def __init__(self, email_chunk_repo: EmailChunkRepository):
        self.email_chunk_repo = email_chunk_repo

    def batch_insert_email_chunks(
        self, prepared_email_chunks: List[PreparedEmailChunk]
    ):
        email_chunks: List[EmailChunk] = self._convert_prepared_email_chunks(
            prepared_email_chunks
        )
        self.email_chunk_repo.batch_insert_email_chunk(rows=email_chunks)

    def _convert_prepared_email_chunks(
        self, prepared_email_chunks: List[PreparedEmailChunk]
    ) -> List[EmailChunk]:
        return [
            EmailChunk(
                email_id=chunk.email_id,
                thread_id=chunk.thread_id,
                message_index=chunk.message_index,
                message_count_in_thread=chunk.message_count_in_thread,
                chunk_index=chunk.chunk_index,
                chunk_count_for_message=chunk.chunk_count_for_message,
                subject=chunk.subject,
                sender=chunk.sender,
                sent_at=chunk.sent_at,
                chunk_text=chunk.chunk_text,
                embedding_text=chunk.embedding_text,
                char_count=chunk.char_count,
                chunking_strategy=chunk.chunking_strategy,
                chunking_version=chunk.chunking_version,
                normalizer_version=chunk.normalizer_version,
                metadata=chunk.metadata,
                is_embedded=False,
            )
            for chunk in prepared_email_chunks
        ]
