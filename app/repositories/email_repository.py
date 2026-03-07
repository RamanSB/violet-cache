from typing import Iterable, List
from sqlmodel import Session, select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Result
import uuid

from app.models.models import Email


class EmailRepository:
    def __init__(self, session: Session):
        self.session = session

    def batch_upsert_metadata(self, rows: Iterable[Email]) -> int:
        stmt = (
            pg_insert(Email)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["external_id", "email_account_id"])
        )
        res: Result = self.session.exec(stmt)
        self.session.commit()
        # return res.rowcount

    def get_email_count(self, *, email_account_id: uuid.UUID) -> int:
        """Return total number of Email rows for the given account."""
        stmt = select(func.count(Email.id)).where(
            Email.email_account_id == email_account_id
        )
        result = self.session.exec(stmt).first()
        return int(result or 0)

    def get_emails_batch(
        self,
        *,
        email_account_id: uuid.UUID,
        offset: int = 0,
        limit: int = 500,
    ) -> List[Email]:
        """
        Return a page of Email rows for the given account.
        """
        stmt = (
            select(Email)
            .where(Email.email_account_id == email_account_id)
            .order_by(Email.created_at)
            .offset(offset)
            .limit(limit)
        )
        results = self.session.exec(stmt).all()
        return list(results)

    def get_distinct_thread_count(self, *, email_account_id: uuid.UUID):
        stmt = select(func.count(func.distinct(Email.thread_id))).where(
            Email.email_account_id == email_account_id
        )
        thread_count = self.session.exec(stmt)
        return thread_count.first()

    def get_distinct_thread_ids(
        self,
        *,
        user_id: uuid.UUID,
        email_account_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 500,
        only_multi_message_threads: bool = False,
    ) -> List[str]:
        """
        Return a page of distinct thread_ids for Email rows.

        Args:
            user_id: Owner of the emails.
            email_account_id: Optional filter by specific email account.
            offset: Offset into the distinct thread_id result set.
            limit: Maximum number of thread_ids to return.
            only_multi_message_threads: If True, only include threads with >1 messages.
        """
        stmt = select(Email.thread_id).where(Email.user_id == user_id)

        if email_account_id is not None:
            stmt = stmt.where(Email.email_account_id == email_account_id)

        if only_multi_message_threads:
            stmt = (
                stmt.group_by(Email.thread_id)
                .having(func.count(Email.id) > 1)
                .order_by(func.count(Email.id).desc())
            )
        else:
            stmt = stmt.group_by(Email.thread_id)

        stmt = stmt.offset(offset).limit(limit)

        results = self.session.exec(stmt).all()
        # results is a list of scalar thread_id values
        return list(results)
