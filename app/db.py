from audioop import getsample
from typing import Annotated
from fastapi import Depends
from sqlmodel import SQLModel, create_engine, Session

from app.config import get_settings, settings

settings = get_settings()

engine = create_engine(
    settings.database_url, echo=True, echo_pool=False, pool_pre_ping=True
)


def create_db_and_tables():
    from . import models

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
