from typing import List, Tuple
import uuid
from app.models.models import Email, EmailAccount, EmailContent
from app.repositories.email_account import EmailAccountRepository
from app.repositories.email_content_repository import EmailContentRepository
from app.repositories.email_repository import EmailRepository


class ChunkPreparationService:

    def __init__(
        self,
        email_account_repository: EmailAccountRepository,
        email_repository: EmailRepository,
        email_content_repository: EmailContentRepository,
    ):
        self._email_account_repo = email_account_repository
        self._email_repo = email_repository
        self._email_content_repo = email_content_repository

    def prepare_chunks_for_email_account(self, email: str):
        """
        Placeholder method to prepare chunks for all emails belonging to a specific email account.
        """
        email_account: EmailAccount = self._email_account_repo.find_by_email(
            email=email
        )
        distinct_thread_count: int = self._email_repo.get_distinct_thread_count(
            email_account_id=email_account.id
        )

        # Stream thread ids in batches to avoid loading all into memory
        offset = 0
        limit = 500
        total_processed = 0

        while total_processed < distinct_thread_count:
            distinct_thread_ids = self._email_repo.get_distinct_thread_ids(
                email_account_id=email_account.id,
                user_id=email_account.user_id,
                offset=offset,
                limit=limit,
                only_multi_message_threads=True,
            )
            if not distinct_thread_ids:
                break

            for thread_id in distinct_thread_ids:
                self.prepare_chunks_for_thread(
                    thread_id=thread_id, user_id=email_account.user_id
                )

            processed_count = len(distinct_thread_ids)
            total_processed += processed_count
            offset += processed_count

    def prepare_chunks_for_thread(self, *, thread_id: str, user_id: uuid.UUID):
        email_with_content: List[Tuple[Email, EmailContent]] = (
            self._email_repo.get_email_by_thread_id(
                thread_id=thread_id, user_id=user_id
            )
        )

    def prepare_chunks_for_email(self, email_id):
        """
        Placeholder method to prepare chunks for a single email.
        """
        pass
