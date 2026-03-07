import uuid
from fastapi import status
from sqlmodel import Boolean, Field, SQLModel, TIMESTAMP, UniqueConstraint
from sqlmodel.main import EmailStr
from datetime import timezone, datetime

from app.enums import EmailProvider, JobPhase, JobStatus, JobType, ResourceType


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
    __tablename__ = "user"

    email: EmailStr = Field(unique=True)
    first_name: str | None = Field(default=None, nullable=True)
    last_name: str | None = Field(default=None, nullable=True)
    is_registered: bool = Field()


class EmailAccount(BaseModel, table=True):
    __tablename__ = "email_account"
    user_id: uuid.UUID = Field(foreign_key="user.id")
    email: EmailStr = Field(unique=True)
    provider: EmailProvider


class GoogleAuthData(BaseModel, table=True):
    __tablename__ = "google_auth_data"
    # Denormalized for quick lookups; User is derivable via EmailAccount
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True
    )

    # Email Account ID
    email_account_id: uuid.UUID = Field(foreign_key="email_account.id")

    google_user_id: str = Field(default=None, nullable=True, unique=True)

    # Token Fields
    access_token: str | None
    refresh_token: str | None
    expires_at: datetime | None = Field(sa_type=TIMESTAMP(timezone=True))
    refresh_token_expires_at: datetime | None = Field(sa_type=TIMESTAMP(timezone=True))


class Email(BaseModel, table=True):
    __table_args__ = (UniqueConstraint("email_account_id", "external_id"),)
    user_id: uuid.UUID = Field(default=None, foreign_key="user.id")
    email_account_id: uuid.UUID = Field(default=None, foreign_key="email_account.id")
    external_id: str
    snippet: str
    thread_id: str
    sender: EmailStr
    receiver: str | None  # Can be multiple emails store the entire sring
    cc: str | None
    subject: str | None
    date_received: datetime
    # label_ids: [str]
    size: int


class EmailContent(BaseModel, table=True):
    __tablename__ = "email_content"
    email_id: str = Field(default=None, foreign_key="email.id")
    mime_type: str | None
    text_plain: str | None
    text_html: str | None
    normalized_text: str | None


class WorkflowJob(BaseModel, table=True):
    celery_task_id: uuid.UUID | None
    job_type: JobType
    status: JobStatus
    phase: JobPhase | None
    resource_type: ResourceType
    progress_current: int = Field(default=0)
    progress_total: int = Field(default=0)
    error_message: str = Field(default=None, nullable=True)
    resource_id: uuid.UUID | None = Field(default=None, nullable=True)
