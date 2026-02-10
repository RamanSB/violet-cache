from contextlib import contextmanager
from sqlmodel import Session, create_engine

from app.config import get_settings

settings = get_settings()

db_engine = create_engine(settings.database_url, pool_pre_ping=True)


@contextmanager
def celery_session():
    with Session(db_engine) as session:
        yield session
