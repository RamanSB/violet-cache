from typing import List
from sqlalchemy.engine import Result
from sqlmodel import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.models import EmailChunk


class EmailChunkRepository:

    def __init__(self, session: Session):
        self.session = session

    def batch_insert_email_chunk(self, rows: List[EmailChunk]):
        stmt = (
            pg_insert(EmailChunk)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=["email_id", "chunk_index", "chunking_version"]
            )
        )
        res: Result = self.session.exec(stmt)
        self.session.commit()
