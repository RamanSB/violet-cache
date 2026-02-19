from sqlmodel import Session, select
import uuid
from app.models.models import EmailAccount
from app.enums import EmailProvider


class EmailAccountRepository:
    """Repository for EmailAccount model database operations."""

    def __init__(self, session: Session):
        self.session = session

    def find_by_email(self, email: str) -> EmailAccount | None:
        """Find an EmailAccount by email address."""
        return self.session.exec(
            select(EmailAccount).where(EmailAccount.email == email)
        ).first()

    def find_by_user_id(self, user_id: uuid.UUID) -> list[EmailAccount]:
        """Find all EmailAccounts for a user."""
        return list(
            self.session.exec(
                select(EmailAccount).where(EmailAccount.user_id == user_id)
            ).all()
        )

    def find_by_user_and_email(
        self, user_id: uuid.UUID, email: str
    ) -> EmailAccount | None:
        """Find an EmailAccount by user_id and email."""
        return self.session.exec(
            select(EmailAccount).where(
                EmailAccount.user_id == user_id, EmailAccount.email == email
            )
        ).first()

    def find_by_user_and_provider(
        self, user_id: uuid.UUID, provider: EmailProvider
    ) -> list[EmailAccount]:
        """Find all EmailAccounts for a user with a specific provider."""
        return list(
            self.session.exec(
                select(EmailAccount).where(
                    EmailAccount.user_id == user_id, EmailAccount.provider == provider
                )
            ).all()
        )

    def create(
        self,
        user_id: uuid.UUID,
        email: str,
        provider: EmailProvider,
    ) -> EmailAccount:
        """Create a new EmailAccount."""
        email_account = EmailAccount(
            user_id=user_id,
            email=email,
            provider=provider,
        )
        self.session.add(email_account)
        self.session.commit()
        self.session.refresh(email_account)
        return email_account

    def update(self, email_account: EmailAccount) -> EmailAccount:
        """Update an existing EmailAccount."""
        self.session.add(email_account)
        self.session.commit()
        self.session.refresh(email_account)
        return email_account

    def find_by_id(self, email_account_id: uuid.UUID) -> EmailAccount | None:
        """Find an EmailAccount by ID."""
        return self.session.get(EmailAccount, email_account_id)
