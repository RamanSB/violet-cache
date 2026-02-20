"""Service layer for EmailAccount operations."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from celery.result import AsyncResult
from app.repositories.email_account import EmailAccountRepository
from app.repositories.user import UserRepository
from app.repositories.google_auth import GoogleAuthDataRepository
from app.models.models import EmailAccount, GoogleAuthData
from app.enums import EmailProvider
from app.tasks.celery.tasks import sync_email_metadata_orchestrator


class EmailAccountService:
    """Service layer for EmailAccount operations."""

    def __init__(
        self,
        email_account_repo: EmailAccountRepository,
        user_repo: UserRepository,
        google_auth_repo: GoogleAuthDataRepository,
    ):
        self.email_account_repo = email_account_repo
        self.user_repo = user_repo
        self.google_auth_repo = google_auth_repo

    def create_email_account(
        self, user_id: uuid.UUID, email: str, provider: EmailProvider
    ) -> EmailAccount:
        """
        Create a new EmailAccount for a user.

        Args:
            user_id: ID of the user who owns this email account
            email: Email address
            provider: Email provider (GMAIL, OUTLOOK, etc.)

        Returns:
            EmailAccount: Created EmailAccount object

        Raises:
            ValueError: If user doesn't exist or email account already exists for this user
        """
        # Verify user exists
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise ValueError(f"User with id {user_id} does not exist")

        # Check if email account already exists for this user
        existing = self.email_account_repo.find_by_user_and_email(user_id, email)
        if existing:
            return existing

        # Create new email account
        email_account = self.email_account_repo.create(
            user_id=user_id, email=email, provider=provider
        )
        return email_account

    def get_or_create_email_account(
        self, user_id: uuid.UUID, email: str, provider: EmailProvider
    ) -> EmailAccount:
        """
        Get existing EmailAccount or create a new one for a user.

        Args:
            user_id: ID of the user who owns this email account
            email: Email address
            provider: Email provider (GMAIL, OUTLOOK, etc.)

        Returns:
            EmailAccount: Existing or newly created EmailAccount object
        """
        # Check if email account already exists for this user
        existing = self.email_account_repo.find_by_user_and_email(user_id, email)
        if existing:
            return existing

        # Create new email account
        return self.create_email_account(user_id, email, provider)

    def check_auth_credentials_valid(
        self, email_account_id: uuid.UUID
    ) -> tuple[bool, Optional[str]]:
        """
        Check if the email account's auth credentials are valid (refresh token not expired).

        Args:
            email_account_id: ID of the EmailAccount to check

        Returns:
            tuple: (is_valid, error_message)
            - is_valid: True if credentials are valid, False otherwise
            - error_message: None if valid, error message if invalid
        """
        email_account = self.email_account_repo.find_by_id(email_account_id)
        if not email_account:
            return False, f"EmailAccount with id {email_account_id} not found"

        # Get auth data for this email account
        google_auth_data = self.google_auth_repo.find_by_email_account_id(
            email_account_id
        )

        if not google_auth_data:
            return False, "No authentication data found for this email account"

        # Check if refresh token exists
        if not google_auth_data.refresh_token:
            return False, "Refresh token not available. Please re-authenticate."

        # Check if refresh token has expired
        if google_auth_data.refresh_token_expires_at:
            now = datetime.now(timezone.utc)
            if google_auth_data.refresh_token_expires_at < now:
                return (
                    False,
                    "Refresh token has expired. Please re-authenticate your email account.",
                )

        # Check if access token exists (might need refresh)
        if not google_auth_data.access_token:
            # Access token might be expired but refresh token is valid
            # This is acceptable - we can refresh it
            pass

        return True, None

    def start_email_account_sync(
        self,
        job_id: uuid.UUID,
        email_account_id: uuid.UUID,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        """
        Start email sync job for an email account.

        Args:
            email_account_id: ID of the EmailAccount to sync
            idempotency_key: Optional key to prevent duplicate job submissions

        Returns:
            dict: Job status with task_id and status

        Raises:
            ValueError: If email account not found or credentials invalid
        """
        # Verify email account exists
        email_account = self.email_account_repo.find_by_id(email_account_id)
        if not email_account:
            raise ValueError(f"EmailAccount with id {email_account_id} not found")

        # Check if credentials are valid
        is_valid, error_message = self.check_auth_credentials_valid(email_account_id)
        if not is_valid:
            raise ValueError(error_message or "Credentials are invalid")

        # # Generate idempotency key if not provided
        # if not idempotency_key:
        #     idempotency_key = (
        #         f"sync_{email_account_id}_{int(datetime.now(timezone.utc).timestamp())}"
        #     )

        # Submit Celery task
        task = sync_email_metadata_orchestrator.delay(
            str(email_account_id), idempotency_key=idempotency_key
        )

        return {
            "task_id": task.id,
            "status": "pending",
            "idempotency_key": idempotency_key,
            "email_account_id": str(email_account_id),
        }

    def get_sync_job_status(self, task_id: str) -> dict:
        """
        Get the status of a sync job.

        Args:
            task_id: Celery task ID

        Returns:
            dict: Job status information
        """
        task_result = AsyncResult(task_id)

        response = {
            "task_id": task_id,
            "status": task_result.state.lower(),  # PENDING, SUCCESS, FAILURE, etc.
        }

        if task_result.ready():
            if task_result.successful():
                response["result"] = task_result.result
                response["status"] = "completed"
            else:
                response["error"] = str(task_result.info)
                response["status"] = "failed"
        else:
            response["status"] = "pending"

        return response
