import uuid
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, EmailStr
from sqlmodel import SQLModel

from app.dependencies import (
    EmailAccountRepositoryDep,
    EmailAccountServiceDep,
    JobServiceDep,
    UserServiceDep,
)
from app.enums import JobType, ResourceType, HARDCODED_USER_ID
from app.models.models import EmailAccount, WorkflowJob
from app.repositories.email_account import EmailAccountRepository


router = APIRouter()


@router.get("/")
def root():
    return {"message": "Hello World!"}


class RegistrationRequest(SQLModel):
    email: EmailStr


@router.post("/auth/register")
def register_email(req: RegistrationRequest, user_service: UserServiceDep):
    """
    Register a new email address.

    Validates request and delegates all business logic to the service.
    """
    try:
        user = user_service.register_email(req.email)
        return user
    except ValueError as e:
        # Email already registered
        raise HTTPException(status_code=409, detail=str(e))


# TODO: Replace with JWT token extraction


@router.get("/email-accounts/")
def get_email_accounts(
    req: Request, email_account_repository: EmailAccountRepositoryDep
):
    """
    Lists all email accounts associated with the registered user.
    TODO: Extract user_id from JWT token instead of using hardcoded value.
    """
    try:
        # TODO: Extract user_id from JWT token in Authorization header
        email_accounts = email_account_repository.find_by_user_id(
            user_id=HARDCODED_USER_ID
        )
        return email_accounts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email-accounts/{email_account_id}/sync", response_model=WorkflowJob)
def sync_email_account(
    email_account_id: str,
    email_account_service: EmailAccountServiceDep,
    job_service: JobServiceDep,
    idempotency_key: str | None = Query(
        None, description="Optional idempotency key to prevent duplicate sync jobs"
    ),
):
    """
    Sync emails for an email account.

    1) Verifies existence of Email Account
    2) Checks if there is already a running sync job
    3) Checks if credentials are valid (refresh token not expired)
       - If expired, returns error suggesting re-authentication
    4) Begins ingestion job using strategy pattern based on provider
    5) Returns job status with task_id and idempotency

    Args:
        email_account_id: UUID of the EmailAccount to sync
        idempotency_key: Optional key to prevent duplicate job submissions

    Returns:
        SyncJobResponse with task_id, status, and idempotency_key
    """
    try:
        email_account_uuid = uuid.UUID(email_account_id)

        active_job, created = job_service.get_or_create_active_job(
            resource_type=ResourceType.email_account,
            resource_id=email_account_id,
            job_type=JobType.mailbox_sync,
        )

        # Start sync job (this will check credentials internally) if job not already created.
        if created:
            job_status = email_account_service.start_email_account_sync(
                active_job.id,
                email_account_id=email_account_uuid,
                idempotency_key=idempotency_key,
            )

        return active_job
        # return WorkflowJob(
        #     task_id=job_status["task_id"],
        #     status=job_status["status"],
        #     idempotency_key=job_status["idempotency_key"],
        #     email_account_id=job_status["email_account_id"],
        #     message="Sync job started successfully",
        # )

    except ValueError as e:
        # Credentials expired or invalid
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start sync job: {str(e)}"
        )


class JobStatusResponse(SQLModel):
    """Response model for job status check."""

    task_id: str
    status: str
    result: dict | None = None
    error: str | None = None


@router.get("/sync-jobs/{task_id}/status", response_model=JobStatusResponse)
def get_sync_job_status(task_id: str, email_account_service: EmailAccountServiceDep):
    """
    Get the status of a sync job.

    Args:
        task_id: Celery task ID returned from sync endpoint

    Returns:
        JobStatusResponse with current job status
    """
    try:
        status = email_account_service.get_sync_job_status(task_id)
        return JobStatusResponse(
            task_id=status["task_id"],
            status=status["status"],
            result=status.get("result"),
            error=status.get("error"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get job status: {str(e)}"
        )
