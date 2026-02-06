from datetime import datetime, timedelta, timezone
from sqlmodel import Session, or_, select
import httpx
import uuid
from app.config import get_settings
from app.models.models import User, GoogleAuthData


class GoogleOAuthService:
    """Service layer for Google OAuth operations."""

    def __init__(self, session: Session):
        self.session = session

    def get_or_create_user_from_google(self, access_token: str) -> User:
        """Fetch user info from Google and create/find user in DB."""
        user_info_response = httpx.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_info_response.raise_for_status()
        user_info = user_info_response.json()

        # Find or create user first
        user = self.session.exec(
            select(User).where(User.email == user_info["email"])
        ).first()

        if user:
            user.is_registered = True
            self.session.add(user)
            self.session.commit()
            self.session.refresh(user)
        else:
            user = User(
                email=user_info["email"],
                first_name=user_info.get("given_name"),
                last_name=user_info.get("family_name"),
                is_registered=True,
            )
            self.session.add(user)
            self.session.commit()
            self.session.refresh(user)

        # Find or create GoogleAuthData and link it to the user
        google_auth_data = self.session.exec(
            select(GoogleAuthData).where(
                GoogleAuthData.google_user_id == user_info["id"]
            )
        ).first()

        if not google_auth_data:
            google_auth_data = GoogleAuthData(
                google_user_id=user_info["id"],
                user_id=user.id,  # Link to the user
            )
            self.session.add(google_auth_data)
        else:
            # Update user_id if it's not already set
            if google_auth_data.user_id != user.id:
                google_auth_data.user_id = user.id
                self.session.add(google_auth_data)

        self.session.commit()
        self.session.refresh(google_auth_data)

        return user

    def save_or_update_google_auth(
        self,
        user_id: uuid.UUID,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        refresh_token_expires_in: int,
        google_user_id: str = None,  # Add this parameter
    ) -> GoogleAuthData:
        """Save or update Google auth tokens for a user."""
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        refresh_token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=refresh_token_expires_in
        )
        existing_auth = self.session.exec(
            select(GoogleAuthData).where(
                or_(
                    GoogleAuthData.user_id == user_id,
                    GoogleAuthData.google_user_id == google_user_id,
                )
            )
        ).first()

        if existing_auth:
            existing_auth.google_user_id = google_user_id  # Update this field
            existing_auth.access_token = access_token
            existing_auth.refresh_token = refresh_token
            existing_auth.refresh_token_expires_at = refresh_token_expires_at
            existing_auth.expires_at = expires_at
            self.session.add(existing_auth)
            self.session.commit()
            self.session.refresh(existing_auth)
            return existing_auth
        else:
            google_auth_data = GoogleAuthData(
                user_id=user_id,
                google_user_id=google_user_id,  # Include this field
                access_token=access_token,
                refresh_token_expires_at=refresh_token_expires_at,
                refresh_token=refresh_token,
                expires_at=expires_at,
            )
            self.session.add(google_auth_data)
            self.session.commit()
            self.session.refresh(google_auth_data)
            return google_auth_data

    def refresh_access_token(self, google_user_id: str) -> GoogleAuthData:
        """
        Refresh the access token using a Google user ID.

        Args:
            google_user_id: The Google user ID to find the GoogleAuthData record.

        Returns:
            GoogleAuthData: Updated GoogleAuthData with new access token.

        Raises:
            ValueError: If GoogleAuthData with the google_user_id is not found.
            httpx.HTTPError: If the token refresh request fails.
        """
        # Find the GoogleAuthData record by google_user_id
        google_auth_data = self.session.exec(
            select(GoogleAuthData).where(
                GoogleAuthData.google_user_id == google_user_id
            )
        ).first()

        if not google_auth_data:
            raise ValueError(
                f"GoogleAuthData not found for google_user_id: {google_user_id}"
            )

        # Get settings for client credentials
        settings = get_settings()

        # Prepare payload for token refresh
        payload = {
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": google_auth_data.refresh_token,
        }

        # Make POST request to Google's token endpoint
        response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data=payload,
        )
        response.raise_for_status()
        tokens = response.json()

        # Update the database record with new tokens
        google_auth_data.access_token = tokens["access_token"]

        # Update expires_at if provided
        if "expires_in" in tokens:
            google_auth_data.expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=tokens["expires_in"]
            )

        # Google may return a new refresh_token (rare, but handle it)
        if "refresh_token" in tokens:
            google_auth_data.refresh_token = tokens["refresh_token"]

        self.session.add(google_auth_data)
        self.session.commit()
        self.session.refresh(google_auth_data)

        return google_auth_data
