"""Pure helper functions for Google OAuth URL generation (no database access)."""

from urllib.parse import urlencode
from app.config import get_settings


class GoogleOAuthHelper:
    """Pure helper class for Google OAuth URL generation."""

    GOOGLE_OAUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    REQUIRED_SCOPES = (
        "openid https://www.googleapis.com/auth/userinfo.email "
        "https://www.googleapis.com/auth/userinfo.profile "
        "https://www.googleapis.com/auth/gmail.readonly"
    )

    @staticmethod
    def generate_auth_url(redirect_uri: str, state: str) -> str:
        """Generate Google OAuth authorization URL."""
        settings = get_settings()
        params = {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "scope": GoogleOAuthHelper.REQUIRED_SCOPES,
        }
        return f"{GoogleOAuthHelper.GOOGLE_OAUTH_ENDPOINT}?{urlencode(params)}"
