import secrets
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
import httpx
from app.config import settings
from urllib.parse import urlencode

from app.db import SessionDep
from app.services.google_oauth_service import GoogleOAuthService

router = APIRouter(prefix="/auth/google")

GOOGLE_OAUTH_ENDPOINT: str = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_TOKEN_ENDPOINT: str = "https://oauth2.googleapis.com/token"
GOOGLE_OAUTH_REQUIRED_SCOPES: str = (
    "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/gmail.readonly"
)


@router.get("/login/", tags=["login"], response_class=RedirectResponse)
def google_auth_login():
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "state": state,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "scope": GOOGLE_OAUTH_REQUIRED_SCOPES,
    }
    auth_url = f"{GOOGLE_OAUTH_ENDPOINT}?{urlencode(params)}"
    print("Google OAuth URL: ", auth_url)
    return auth_url


@router.get("/consent/", tags=["callback"])
def google_consent_redirect(request: Request, session: SessionDep):
    query_params = request.query_params
    error = query_params.get("error")
    if error:
        print("Error while attempting to get authorisation (Google): ", error)
        return Response(status_code=403, content="User denied consent.")

    code = query_params.get("code")
    if not code:
        return Response(status_code=400, content="Authorization code not provided.")

    payload = {
        "code": code,
        "grant_type": "authorization_code",
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "redirect_uri": settings.google_oauth_redirect_uri,
    }

    # Make POST request to exchange code for tokens
    r = httpx.post(url=GOOGLE_OAUTH_TOKEN_ENDPOINT, data=payload)

    if r.status_code == 200:
        tokens = r.json()

        # Validate scopes
        token_scopes = set(tokens["scope"].split())
        required_scopes = set(GOOGLE_OAUTH_REQUIRED_SCOPES.split())
        if not required_scopes.issubset(token_scopes):
            missing_scopes = required_scopes - token_scopes
            print(f"Required scopes were not permitted: {list(missing_scopes)}")
            return Response(
                status_code=400,
                content=f"Required scopes were not permitted: {list(missing_scopes)}",
            )

        # Use service layer
        oauth_service = GoogleOAuthService(session)

        # Get or create user from Google user info (Wrap both Create and Update Auth in Atomic Txn)
        try:
            user = oauth_service.get_or_create_user_from_google(tokens["access_token"])
        except httpx.HTTPError as e:
            print(f"Error fetching user info from Google: {e}")
            return Response(
                status_code=500, content="Failed to fetch user information from Google."
            )

        # Save or update auth data
        oauth_service.save_or_update_google_auth(
            user_id=user.id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=tokens.get("expires_in", 3600),
            refresh_token_expires_in=tokens["refresh_token_expires_in"],
        )

        return RedirectResponse(url="http://localhost:8000/auth/google/success")
    else:
        error_response = (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else {"error": r.text}
        )
        return Response(
            status_code=400,
            content=f"Failed to exchange code for tokens: {error_response}",
        )
