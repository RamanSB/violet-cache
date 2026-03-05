import asyncio
import uuid
from datetime import datetime, timezone
from typing import List

from app.celery_db import celery_session
from app.repositories.email_repository import EmailRepository
from app.services.email_ingestion import email_ingestion
from app.services.email_ingestion.email_ingestion import EmailIngestionService
from app.services.email_ingestion.filters.rules import should_keep_email_metadata
from app.enums import JobStatus
from app.models.models import Email, EmailAccount
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
    job_id: uuid.UUID,
    email_account_id: str,
    idempotency_key: str | None = None,
):
    """Async implementation of email ingestion."""
    email_account_uuid = uuid.UUID(email_account_id)
    strategy = None

    def _attach_context(m: dict, user_id: str, email_account_id: str) -> dict:
        m["user_id"] = str(user_id)
        m["email_account_id"] = str(email_account_id)
        return m

    try:
        with celery_session() as session:
            email_repository: EmailRepository = EmailRepository(session=session)
            email_ingestion_service = EmailIngestionService(
                email_repository=email_repository
            )
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
                    "message": f"Access token not available. Please re-authenticate {email_account.provider}.",
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
            inbox_count = 0
            retained_inbox_count = 0
            sent_count = 0
            # Iterate over messages in batches of 500 (AsyncGenerator)
            async for msg_ids in strategy.list_messages(
                access_token=auth_data.access_token,
                user_identifier=user_identifier,
                include_spam_trash=False,
                label_ids=["INBOX"],
                q="category:primary -category:promotions -category:social -category:updates",
            ):
                # Fetch full message data
                messages = await strategy.fetch_messages_by_ids(
                    msg_ids,
                    access_token=auth_data.access_token,
                    user_identifier=user_identifier,
                    format="metadata",
                )
                inbox_count += len(messages)
                kept = []
                for m in messages:
                    decision = should_keep_email_metadata(m)
                    if decision.keep:
                        _attach_context(
                            m,
                            user_id=email_account.user_id,
                            email_account_id=email_account.id,
                        )
                        kept.append(m)
                    else:
                        print(f"{decision.reason} dropping {m['snippet']}")
                print(f"Retained {len(kept)} messages in this batch")
                total += len(messages)
                retained_inbox_count += len(kept)
                email_ingestion_service.batch_upsert_email_metadata(data=kept)
                job_service.update_job(job_id, progress_current=total)

            async for msg_ids in strategy.list_messages(
                access_token=auth_data.access_token,
                user_identifier=user_identifier,
                include_spam_trash=False,
                label_ids=["SENT"],
                q="-from:(noreply@ OR no-reply@ OR do-not-reply@ OR notifications@)",
            ):
                # Fetch full message data
                messages = await strategy.fetch_messages_by_ids(
                    msg_ids,
                    access_token=auth_data.access_token,
                    user_identifier=user_identifier,
                    format="metadata",
                )
                for m in messages:
                    _attach_context(
                        m,
                        user_id=email_account.user_id,
                        email_account_id=email_account.id,
                    )
                sent_count += len(messages)
                job_service.update_job(job_id, progress_current=total)
                total += len(messages)
                email_ingestion_service.batch_upsert_email_metadata(data=messages)

            job_service.update_job(
                job_id,
                status=JobStatus.succeeded,
                completed_at=datetime.now(timezone.utc),
                progress_total=total,
            )
            print(
                f"inbox_count: {inbox_count}, retained_inbox_count: {retained_inbox_count}, sent_count: {sent_count}"
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


## TODO: Create a predicate function that decides whether we retain email or not.
## Move to a dedicated service at a later time.
