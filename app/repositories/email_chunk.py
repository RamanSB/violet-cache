from typing import List
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session

from app.models.models import EmailChunk


class EmailChunkRepository:
    def __init__(self, session: Session):
        self.session = session

    def batch_upsert_email_chunks(self, rows: List[dict]) -> None:
        if not rows:
            return

        stmt = insert(EmailChunk).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["email_id", "chunk_index", "chunking_version"],
            set_={
                "thread_id": stmt.excluded.thread_id,
                "message_index": stmt.excluded.message_index,
                "message_count_in_thread": stmt.excluded.message_count_in_thread,
                "chunk_count_for_message": stmt.excluded.chunk_count_for_message,
                "subject": stmt.excluded.subject,
                "sender": stmt.excluded.sender,
                "sent_at": stmt.excluded.sent_at,
                "chunk_text": stmt.excluded.chunk_text,
                "embedding_text": stmt.excluded.embedding_text,
                "char_count": stmt.excluded.char_count,
                "token_count": stmt.excluded.token_count,
                "chunking_strategy": stmt.excluded.chunking_strategy,
                "normalizer_version": stmt.excluded.normalizer_version,
                "meta": stmt.excluded.meta,
                "is_embedded": stmt.excluded.is_embedded,
            },
        )
        self.session.exec(stmt)
        self.session.commit()
