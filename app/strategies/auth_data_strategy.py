"""Strategy pattern for auth data retrieval."""

from abc import ABC, abstractmethod
from typing import Protocol
import uuid
from datetime import datetime
from sqlmodel import Session
from app.enums import EmailProvider


class AuthData(Protocol):
    """Protocol for auth data models - common interface that all provider auth data must implement."""

    email_account_id: uuid.UUID
    access_token: str | None
    refresh_token: str | None
    expires_at: datetime | None
    refresh_token_expires_at: datetime | None


class AuthDataStrategy(ABC):
    """Abstract base class for auth data retrieval strategies."""

    @abstractmethod
    def get_provider(self) -> EmailProvider:
        """Return the email provider this strategy handles."""
        pass

    @abstractmethod
    def load_auth_data(
        self, session: Session, email_account_id: uuid.UUID
    ) -> AuthData | None:
        """
        Load auth data for an email account.

        Args:
            session: Database session
            email_account_id: UUID of the EmailAccount

        Returns:
            AuthData instance or None if not found
        """
        pass

    @abstractmethod
    def get_user_identifier(self, auth_data: AuthData) -> str | None:
        """
        Extract provider-specific user identifier from auth data.

        Args:
            auth_data: Auth data instance

        Returns:
            Provider-specific user identifier (e.g., google_user_id, outlook_user_id)
        """
        pass
