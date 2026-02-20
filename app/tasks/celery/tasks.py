import asyncio
import uuid
from datetime import datetime, timezone
from typing import List

from app.celery_db import celery_session
from app.enums import JobStatus
from app.models.models import EmailAccount
from app.repositories.email_account import EmailAccountRepository
from app.repositories.job_repository import JobRepository
from app.services.job_service import JobService
from app.strategies.auth_data_strategy_factory import AuthDataStrategyFactory
from app.strategies.strategy_factory import EmailProviderStrategyFactory
from app.tasks.celery.celery import app


@app.task(name="ingest_email_account")
def sync_email_metadata_orchestrator(
    job_id: str, email_account_id: str, idempotency_key: str | None = None
) -> dict:
    """
    Celery task to ingest emails for an email account.

    Args:
        email_account_id: UUID of the EmailAccount to sync
        idempotency_key: Optional idempotency key to prevent duplicate runs

    Returns:
        dict: Task result with status and message
    """
    return asyncio.run(
        _sync_email_metadata_orchestrator(job_id, email_account_id, idempotency_key)
    )


async def _sync_email_metadata_orchestrator(
    job_id: uuid.UUID, email_account_id: str, idempotency_key: str | None = None
):
    """Async implementation of email ingestion."""
    email_account_uuid = uuid.UUID(email_account_id)
    strategy = None

    try:
        with celery_session() as session:
            job_repository: JobRepository = JobRepository(session)
            job_service: JobService = JobService(job_repository=job_repository)
            job_service.update_job(job_id=job_id, status=JobStatus.running)
            # Load email account
            email_account_repo = EmailAccountRepository(session=session)
            email_account: EmailAccount | None = email_account_repo.find_by_id(
                email_account_uuid
            )

            if email_account is None:
                return {
                    "status": "error",
                    "message": f"EmailAccount with id {email_account_id} not found",
                }

            # Use auth data strategy to load provider-specific auth data
            auth_data_strategy = AuthDataStrategyFactory.create(email_account.provider)
            auth_data = auth_data_strategy.load_auth_data(session, email_account_uuid)

            if auth_data is None:
                return {
                    "status": "error",
                    "message": f"No auth data found for EmailAccount {email_account_id}",
                }

            # Check if access token exists
            if not auth_data.access_token:
                return {
                    "status": "error",
                    "message": "Access token not available. Please re-authenticate.",
                }

            # Get provider-specific user identifier using the strategy
            user_identifier = auth_data_strategy.get_user_identifier(auth_data)
            if not user_identifier:
                return {
                    "status": "error",
                    "message": "User identifier not found in auth data",
                }

            # Create email provider strategy for fetching messages
            strategy = EmailProviderStrategyFactory.create(email_account.provider)

            total = 0
            # Iterate over messages in batches of 500 (AsyncGenerator)
            async for msg_ids in strategy.list_messages(
                access_token=auth_data.access_token,
                user_identifier=user_identifier,
                include_spam_trash=False,
                label_ids=["INBOX"],
            ):
                # Fetch full message data
                messages = await strategy.fetch_messages_by_ids(
                    msg_ids,
                    access_token=auth_data.access_token,
                    user_identifier=user_identifier,
                    format="metadata",
                )
                total += len(messages)
                job_service.update_job(job_id, progress_current=total)

            async for msg_ids in strategy.list_messages(
                access_token=auth_data.access_token,
                user_identifier=user_identifier,
                include_spam_trash=False,
                label_ids=["SENT"],
            ):
                # Fetch full message data
                messages = await strategy.fetch_messages_by_ids(
                    msg_ids,
                    access_token=auth_data.access_token,
                    user_identifier=user_identifier,
                    format="metadata",
                )
                total += len(messages)
                job_service.update_job(job_id, progress_current=total)

            job_service.update_job(
                job_id,
                status=JobStatus.succeeded,
                completed_at=datetime.now(timezone.utc),
            )
            return {"status": "success", "message_count": total}

    except Exception as e:
        with celery_session() as session:
            job_repo = JobRepository(session=session)
            job_service = JobService(job_repo)
            job_service.update_job(
                job_id=job_id, status=JobStatus.failed, error_message=str(e)
            )
        return {"status": "error", "message": str(e)}
    finally:
        if strategy:
            await strategy.close()
