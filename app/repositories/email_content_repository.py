from typing import Iterable
from sqlalchemy import Result
from sqlmodel import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.models import EmailContent


class EmailContentRepository:

    def __init__(self, session: Session):
        self.session = session

    def batch_upsert_email_content(self, *, rows: Iterable[EmailContent]):
        stmt = pg_insert(EmailContent).values(rows).on_conflict_do_nothing()
        res: Result = self.session.exec(stmt)
        self.session.commit()
