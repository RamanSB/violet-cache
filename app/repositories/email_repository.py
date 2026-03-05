from typing import Iterable
from sqlmodel import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Result

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
