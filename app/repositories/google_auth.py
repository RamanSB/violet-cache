from sqlmodel import Session, select, or_
from app.models.models import GoogleAuthData
import uuid
from datetime import datetime


class GoogleAuthDataRepository:
    """Repository for GoogleAuthData model database operations."""

    def __init__(self, session: Session):
        self.session = session

    def find_by_google_user_id(self, google_user_id: str) -> GoogleAuthData | None:
        """Find GoogleAuthData by Google user ID."""
        return self.session.exec(
            select(GoogleAuthData).where(
                GoogleAuthData.google_user_id == google_user_id
            )
        ).first()

    def find_by_user_id(self, user_id: uuid.UUID) -> GoogleAuthData | None:
        """Find GoogleAuthData by user ID."""
        return self.session.exec(
            select(GoogleAuthData).where(GoogleAuthData.user_id == user_id)
        ).first()

    def find_by_user_or_google_id(
        self, user_id: uuid.UUID | None = None, google_user_id: str | None = None
    ) -> GoogleAuthData | None:
        """Find GoogleAuthData by either user_id or google_user_id."""
        if not user_id and not google_user_id:
            return None

        conditions = []
        if user_id:
            conditions.append(GoogleAuthData.user_id == user_id)
        if google_user_id:
            conditions.append(GoogleAuthData.google_user_id == google_user_id)

        return self.session.exec(select(GoogleAuthData).where(or_(*conditions))).first()

    def create(
        self,
        user_id: uuid.UUID,
        google_user_id: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        expires_at: datetime | None = None,
        refresh_token_expires_at: datetime | None = None,
    ) -> GoogleAuthData:
        """Create a new GoogleAuthData record."""
        google_auth_data = GoogleAuthData(
            user_id=user_id,
            google_user_id=google_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            refresh_token_expires_at=refresh_token_expires_at,
        )
        self.session.add(google_auth_data)
        self.session.commit()
        self.session.refresh(google_auth_data)
        return google_auth_data

    def update(self, google_auth_data: GoogleAuthData) -> GoogleAuthData:
        """Update an existing GoogleAuthData record."""
        self.session.add(google_auth_data)
        self.session.commit()
        self.session.refresh(google_auth_data)
        return google_auth_data
