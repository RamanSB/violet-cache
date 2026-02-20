import secrets
import uuid
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse
import httpx
from app.config import settings
from app.dependencies import GoogleOAuthServiceDep
from app.enums import EmailProvider
from app.services.google_oauth_helper import GoogleOAuthHelper
from app.tasks.celery.tasks import sync_email_metadata_orchestrator

# TODO: Replace this hardcoded user_id with JWT token extraction from request headers
# For now, hardcoding a user_id for testing. In production, extract from JWT:
#   - Get Authorization header
#   - Decode JWT token
#   - Extract user_id from token payload
HARDCODED_USER_ID = uuid.UUID(
    "18cdd005-9931-4433-bd46-fd4223e1431f"
)  # Replace with actual user_id


router = APIRouter(prefix="/auth/google")


@router.get("/login/", tags=["login"], response_class=RedirectResponse)
def google_auth_login():
    """Generate and return Google OAuth authorization URL."""
    state = secrets.token_urlsafe(32)
    # Pure helper - can be instantiated directly (no DB access needed)
    helper = GoogleOAuthHelper()
    auth_url = helper.generate_auth_url(
        redirect_uri=settings.google_oauth_redirect_uri, state=state
    )
    print("Google OAuth URL: ", auth_url)
    return auth_url


@router.get("/consent/", tags=["callback"])
def google_consent_redirect(request: Request, oauth_service: GoogleOAuthServiceDep):
    """
    Handle Google OAuth callback and process authorization.

    Validates request parameters and delegates all business logic to the service.
    """
    query_params = request.query_params

    # Parse and validate request parameters
    error = query_params.get("error")
    if error:
        print("Error while attempting to get authorisation (Google): ", error)
        return Response(status_code=403, content="User denied consent.")

    code = query_params.get("code")
    if not code:
        return Response(status_code=400, content="Authorization code not provided.")

    # Delegate all business logic to service
    try:
        # TODO: Extract user_id from JWT token in Authorization header instead of hardcoding
        # For now, using hardcoded user_id. User must be registered first via /auth/register
        user_id = HARDCODED_USER_ID

        user, email_account, google_auth_data = oauth_service.handle_oauth_callback(
            code=code, redirect_uri=settings.google_oauth_redirect_uri, user_id=user_id
        )
        # TODO: Move email ingestion to a dedicated endpoint
        # Render a UI here on FE with a success message then move user back to home screen.
        return RedirectResponse(url="http://localhost:8000/auth/google/success")
    except ValueError as e:
        # Scope validation error
        print(f"OAuth validation error: {e}")
        return Response(status_code=400, content=str(e))
    except httpx.HTTPError as e:
        # HTTP errors from Google API calls
        print(f"Error during OAuth flow: {e}")
        return Response(
            status_code=500, content="Failed to complete OAuth flow with Google."
        )
    except Exception as e:
        # Unexpected errors
        print(f"Unexpected error during OAuth flow: {e}")
        return Response(
            status_code=500,
            content="An unexpected error occurred during authentication.",
        )
