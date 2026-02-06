import uuid
from sqlmodel import Boolean, Field, SQLModel, TIMESTAMP
from sqlmodel.main import EmailStr
from datetime import timezone, datetime


class BaseModel(SQLModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=TIMESTAMP(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc),
        },
        sa_type=TIMESTAMP(timezone=True),
    )


class User(BaseModel, table=True):
    __table__name = "users"

    email: EmailStr = Field(unique=True)
    first_name: str | None = Field(default=None, nullable=True)
    last_name: str | None = Field(default=None, nullable=True)
    is_registered: bool = Field()


class GoogleAuthData(BaseModel, table=True):
    __tablename__ = "google_auth_data"

    user_id: uuid.UUID = Field(default=None, foreign_key="user.id")
    google_user_id: str = Field(default=None, nullable=True, unique=True)

    # Token Fields
    access_token: str | None
    refresh_token: str | None
    expires_at: datetime | None = Field(sa_type=TIMESTAMP(timezone=True))
    refresh_token_expires_at: datetime | None = Field(sa_type=TIMESTAMP(timezone=True))
