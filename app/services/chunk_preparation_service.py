from datetime import datetime
from typing import Dict, List, Tuple
import uuid
from app.models.models import Email, EmailAccount, EmailContent
from app.repositories.email_account import EmailAccountRepository
from app.repositories.email_content_repository import EmailContentRepository
from app.repositories.email_repository import EmailRepository
from app.schema.dto.prepared_email_chunk import PreparedEmailChunk
from app.strategies.chunking.base import Chunkifier, ChunkPiece
from app.logging import get_logger

logger = get_logger(__name__)


class ChunkPreparationService:

    def __init__(
        self,
        email_account_repository: EmailAccountRepository,
        email_repository: EmailRepository,
        chunkifier: Chunkifier,
    ):
        self._email_account_repo = email_account_repository
        self._email_repo = email_repository
        # self._email_content_repo = email_content_repository
        self._chunkifier = chunkifier

    def prepare_chunks_for_email_account(
        self, email_account_id: str, filter_thread_ids: List[str] | None = None
    ) -> Dict[str, List[PreparedEmailChunk]]:
        """
        Prepare chunks for embedding service for a given email account.

        Args:
            filter_thread_ids: Used to filter thread ids we shall chunk emails for (used for testing)

        Returns:
            Dict of List of prepared chunks keyed by thread id.
        """
        # TODO: Move this top level fetching of threads in to the celery task and parallelise with asyncio.
        email_account: EmailAccount = self._email_account_repo.find_by_email_account_id(
            email_account_id=uuid.UUID(email_account_id)
        )
        distinct_thread_count: int = self._email_repo.get_distinct_thread_count(
            email_account_id=email_account.id
        )
        filter_thread_ids_set = set(filter_thread_ids or [])

        # Stream thread ids in batches to avoid loading all into memory
        offset = 0
        limit = 500
        total_processed = 0
        chunks_by_thread_id: Dict[str, List[PreparedEmailChunk]] = {}
        while total_processed < distinct_thread_count:
            distinct_thread_ids = self._email_repo.get_distinct_thread_ids(
                email_account_id=email_account.id,
                user_id=email_account.user_id,
                offset=offset,
                limit=limit,
                only_multi_message_threads=False,
            )
            if not distinct_thread_ids:
                break

            for thread_id in distinct_thread_ids:
                if filter_thread_ids_set and thread_id not in filter_thread_ids_set:
                    continue
                thread_chunks = self.prepare_chunks_for_thread(
                    thread_id=thread_id, user_id=email_account.user_id
                )
                logger.info(
                    f"Generated {len(thread_chunks)} chunks for thread_id: {thread_id}"
                )
                chunks_by_thread_id[thread_id] = thread_chunks

            processed_count = len(distinct_thread_ids)
            total_processed += processed_count
            offset += processed_count
        return chunks_by_thread_id

    def prepare_chunks_for_thread(
        self, *, thread_id: str, user_id: uuid.UUID
    ) -> List[PreparedEmailChunk]:
        email_with_content: List[Tuple[Email, EmailContent]] = (
            self._email_repo.get_emails_by_thread_id(
                thread_id=thread_id,
                user_id=user_id,
            )
        )
        msg_count = len(email_with_content)

        all_chunks = []
        for idx, (email, content) in enumerate(email_with_content):
            if not content.normalized_text:
                logger.info(
                    f"skip {email.id} for thread {email.thread_id} - no content from {email.sender} | subject: {email.subject} "
                )
                continue
            email_chunks = self.prepare_chunks_for_email(
                email=email,
                content=content.normalized_text,
                message_idx=idx,
                message_count=msg_count,
            )
            logger.info(
                f"Thread {thread_id} | Message ({email.id}) generated {len(email_chunks)} chunks"
            )
            all_chunks.extend(email_chunks)
        logger.info(
            f"Thread {thread_id} [msg_count={msg_count} | chunk_count={len(all_chunks)}]"
        )
        return all_chunks

    def prepare_chunks_for_email(
        self, *, email: Email, content: str, message_idx: int, message_count: int
    ) -> List[PreparedEmailChunk]:
        prepared_chunks: List[PreparedEmailChunk] = []
        chunks: List[ChunkPiece] = self._chunkifier.chunk(content)
        # Enrich metadata after.
        for chunk in chunks:
            prepared_chunk = PreparedEmailChunk(
                email_id=email.id,
                thread_id=email.thread_id,
                message_index=message_idx,
                message_count_in_thread=message_count,
                chunk_index=chunk.chunk_index,
                chunk_count_for_message=chunk.chunk_count,
                subject=email.subject,
                sender=email.sender,
                sent_at=email.date_received,
                chunk_text=chunk.text,
                embedding_text=self._build_embedding_text(
                    subject=email.subject,
                    sender=email.sender,
                    sent_at=email.date_received,
                    message_index=message_idx,
                    message_count=message_count,
                    chunk_text=chunk.text,
                ),  # Not yet
                char_count=chunk.char_count,
                chunking_strategy=self._chunkifier.strategy_name,
                chunking_version=self._chunkifier.strategy_version,
                normalizer_version="v1",
                metadata={
                    "user_id": str(email.user_id),
                },
            )
            prepared_chunks.append(prepared_chunk)

        return prepared_chunks

    def _build_embedding_text(
        self,
        *,
        subject: str | None,
        sender: str | None,
        sent_at: datetime,
        message_index: int,
        message_count: int,
        chunk_text: str,
    ) -> str:
        parts = []

        if subject:
            parts.append(f"Subject: {subject}")
        if sender:
            parts.append(f"From: {sender}")
        if sent_at:
            parts.append(f"Sent at: {sent_at.isoformat()}")

        parts.append(f"Message {message_index + 1} of {message_count} in thread")
        parts.append("")
        parts.append(chunk_text)

        return "\n".join(parts).strip()
