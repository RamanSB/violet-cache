"""Gmail-specific auth data strategy."""

import uuid
from sqlmodel import Session
from app.enums import EmailProvider
from app.models.models import GoogleAuthData
from app.repositories.google_auth import GoogleAuthDataRepository
from app.strategies.auth_data_strategy import AuthDataStrategy, AuthData


class GmailAuthDataStrategy(AuthDataStrategy):
    """Strategy for retrieving Gmail auth data."""

    def get_provider(self) -> EmailProvider:
        """Return Gmail provider."""
        return EmailProvider.GMAIL

    def load_auth_data(
        self, session: Session, email_account_id: uuid.UUID
    ) -> GoogleAuthData | None:
        """
        Load GoogleAuthData for the email account.

        Args:
            session: Database session
            email_account_id: UUID of the EmailAccount

        Returns:
            GoogleAuthData instance or None if not found
        """
        repo = GoogleAuthDataRepository(session=session)
        return repo.find_by_email_account_id(email_account_id)

    def get_user_identifier(self, auth_data: GoogleAuthData) -> str | None:
        """
        Extract google_user_id from GoogleAuthData.

        Args:
            auth_data: GoogleAuthData instance

        Returns:
            google_user_id string or None
        """
        return auth_data.google_user_id
