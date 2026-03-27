from typing import List
import uuid
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

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

    def get_chunk_by_ids(self, chunk_ids: List[str]) -> List[EmailChunk]:
        if not chunk_ids:
            return []

        stmt = select(EmailChunk).where(EmailChunk.id.in_(chunk_ids))
        result = self.session.exec(stmt).all()
        return result

    def get_chunks_by_thread_id(self, thread_id: str) -> List[EmailChunk]:
        if not thread_id:
            return []

        stmt = select(EmailChunk).where(EmailChunk.thread_id == thread_id)
        result = self.session.exec(stmt).all()
        return result

    # NOTE: Change `email_id` param to `email_account_id` once email_account-level filtering is supported.

    def get_unembedded_chunks(
        self, email_id: str, offset: int = 0, limit: int = 100
    ) -> List[EmailChunk]:
        """
        Retrieve unembedded chunks for a given email.
        TODO: Change `email_id` to `email_account_id` when refactoring.
        """
        stmt = (
            select(EmailChunk)
            .where(
                EmailChunk.email_id == email_id,
                EmailChunk.is_embedded == False,
            )
            .offset(offset)
            .limit(limit)
        )
        return self.session.exec(stmt).all()

    def get_embedded_chunks(
        self, email_id: str, offset: int = 0, limit: int = 100
    ) -> List[EmailChunk]:
        """
        Retrieve embedded chunks for a given email.
        TODO: Change `email_id` to `email_account_id` when refactoring.
        """
        stmt = (
            select(EmailChunk)
            .where(
                EmailChunk.email_id == email_id,
                EmailChunk.is_embedded == True,
            )
            .offset(offset)
            .limit(limit)
        )
        return self.session.exec(stmt).all()

    def get_all_chunks(
        self, email_id: str, offset: int = 0, limit: int = 100
    ) -> List[EmailChunk]:
        """
        Retrieve all chunks for a given email.
        TODO: Change `email_id` to `email_account_id` when refactoring.
        """
        stmt = (
            select(EmailChunk)
            .where(EmailChunk.email_id == email_id)
            .offset(offset)
            .limit(limit)
        )
        return self.session.exec(stmt).all()
