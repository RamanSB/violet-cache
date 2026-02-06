from datetime import datetime, timedelta, timezone
import httpx
import uuid
from app.config import get_settings
from app.repositories.user import UserRepository
from app.repositories.google_auth import GoogleAuthDataRepository
from app.models.models import User, GoogleAuthData


class GoogleOAuthService:
    """Service layer for Google OAuth operations."""

    GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"
    GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    REQUIRED_SCOPES = (
        "openid https://www.googleapis.com/auth/userinfo.email "
        "https://www.googleapis.com/auth/userinfo.profile "
        "https://www.googleapis.com/auth/gmail.readonly"
    )

    def __init__(
        self,
        user_repo: UserRepository,
        google_auth_repo: GoogleAuthDataRepository,
    ):
        self.user_repo = user_repo
        self.google_auth_repo = google_auth_repo
        self.settings = get_settings()

    def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> dict:
        """
        Exchange authorization code for access and refresh tokens.

        Returns:
            dict: Token response from Google containing access_token, refresh_token, etc.

        Raises:
            httpx.HTTPError: If the token exchange request fails.
        """
        payload = {
            "code": code,
            "grant_type": "authorization_code",
            "client_id": self.settings.google_oauth_client_id,
            "client_secret": self.settings.google_oauth_client_secret,
            "redirect_uri": redirect_uri,
        }

        response = httpx.post(url=self.GOOGLE_TOKEN_ENDPOINT, data=payload)
        response.raise_for_status()
        return response.json()

    def handle_oauth_callback(
        self, code: str, redirect_uri: str
    ) -> tuple[User, GoogleAuthData]:
        """
        Handle complete OAuth callback flow: exchange code, validate scopes,
        get/create user, and save auth data.

        Returns:
            tuple: (User, GoogleAuthData)

        Raises:
            httpx.HTTPError: If token exchange or user info fetch fails.
            ValueError: If required scopes are missing.
        """
        # Exchange code for tokens
        tokens = self.exchange_code_for_tokens(code, redirect_uri)

        # Validate scopes
        token_scopes = tokens.get("scope", "")
        is_valid, missing_scopes = self.validate_scopes(token_scopes)
        if not is_valid:
            raise ValueError(f"Required scopes were not permitted: {missing_scopes}")

        # Get or create user from Google user info
        user = self.get_or_create_user_from_google(tokens["access_token"])

        # Extract google_user_id from user info (needed for save_or_update_google_auth)
        user_info = self.fetch_user_info_from_google(tokens["access_token"])
        google_user_id = user_info["id"]

        # Save or update auth data
        google_auth_data = self.save_or_update_google_auth(
            user_id=user.id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=tokens.get("expires_in", 3600),
            refresh_token_expires_in=tokens.get("refresh_token_expires_in", 0),
            google_user_id=google_user_id,
        )

        return user, google_auth_data

    def validate_scopes(self, token_scopes: str) -> tuple[bool, list[str]]:
        """Validate that required scopes are present in token response."""
        token_scopes_set = set(token_scopes.split())
        required_scopes_set = set(self.REQUIRED_SCOPES.split())
        missing_scopes = required_scopes_set - token_scopes_set
        return (len(missing_scopes) == 0, list(missing_scopes))

    def fetch_user_info_from_google(self, access_token: str) -> dict:
        """Fetch user information from Google using access token."""
        response = httpx.get(
            self.GOOGLE_USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()

    def get_or_create_user_from_google(self, access_token: str) -> User:
        """Fetch user info from Google and create/find user in DB."""
        user_info = self.fetch_user_info_from_google(access_token)

        # Find or create user using repository
        user = self.user_repo.find_by_email(user_info["email"])

        if user:
            user.is_registered = True
            user = self.user_repo.update(user)
        else:
            user = self.user_repo.create(
                email=user_info["email"],
                first_name=user_info.get("given_name"),
                last_name=user_info.get("family_name"),
                is_registered=True,
            )

        # Find or create GoogleAuthData using repository
        google_auth_data = self.google_auth_repo.find_by_google_user_id(user_info["id"])

        if not google_auth_data:
            self.google_auth_repo.create(
                google_user_id=user_info["id"],
                user_id=user.id,
            )
        else:
            if google_auth_data.user_id != user.id:
                google_auth_data.user_id = user.id
                self.google_auth_repo.update(google_auth_data)

        return user

    def save_or_update_google_auth(
        self,
        user_id: uuid.UUID,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        refresh_token_expires_in: int,
        google_user_id: str | None = None,
    ) -> GoogleAuthData:
        """Save or update Google auth tokens for a user."""
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        refresh_token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=refresh_token_expires_in
        )

        existing_auth = self.google_auth_repo.find_by_user_or_google_id(
            user_id=user_id, google_user_id=google_user_id
        )

        if existing_auth:
            existing_auth.google_user_id = (
                google_user_id or existing_auth.google_user_id
            )
            existing_auth.access_token = access_token
            existing_auth.refresh_token = refresh_token
            existing_auth.refresh_token_expires_at = refresh_token_expires_at
            existing_auth.expires_at = expires_at
            return self.google_auth_repo.update(existing_auth)
        else:
            return self.google_auth_repo.create(
                user_id=user_id,
                google_user_id=google_user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                refresh_token_expires_at=refresh_token_expires_at,
            )

    def refresh_access_token(self, google_user_id: str) -> GoogleAuthData:
        """Refresh the access token using a Google user ID."""
        google_auth_data = self.google_auth_repo.find_by_google_user_id(google_user_id)

        if not google_auth_data:
            raise ValueError(
                f"GoogleAuthData not found for google_user_id: {google_user_id}"
            )

        payload = {
            "client_id": self.settings.google_oauth_client_id,
            "client_secret": self.settings.google_oauth_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": google_auth_data.refresh_token,
        }

        response = httpx.post(self.GOOGLE_TOKEN_ENDPOINT, data=payload)
        response.raise_for_status()
        tokens = response.json()

        google_auth_data.access_token = tokens["access_token"]

        if "expires_in" in tokens:
            google_auth_data.expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=tokens["expires_in"]
            )

        if "refresh_token" in tokens:
            google_auth_data.refresh_token = tokens["refresh_token"]

        return self.google_auth_repo.update(google_auth_data)
