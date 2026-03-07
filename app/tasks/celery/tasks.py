import asyncio
import uuid
from datetime import datetime, timezone
from typing import List

from app.celery_db import celery_session
from app.parsers.parser_factory import EmailContentParserFactory
from app.repositories import email_repository
from app.repositories.email_repository import EmailRepository
from app.schema.schemas import ParsedEmailContent
from app.services.email_ingestion import email_ingestion
from app.services.email_ingestion.email_ingestion import EmailIngestionService
from app.services.email_ingestion.filters.rules import should_keep_email_metadata
from app.enums import JobPhase, JobStatus
from app.models.models import Email, EmailAccount
from app.repositories.email_account import EmailAccountRepository
from app.repositories.job_repository import JobRepository
from app.services.job_service import JobService
from app.strategies.auth_data_strategy_factory import AuthDataStrategyFactory
from app.strategies.strategy_factory import EmailProviderStrategyFactory
from app.tasks.celery.celery import app


# Move to utils
def _attach_context(m: dict, user_id: str, email_account_id: str) -> dict:
    m["user_id"] = str(user_id)
    m["email_account_id"] = str(email_account_id)
    return m


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

    try:
        with celery_session() as session:
            email_repository: EmailRepository = EmailRepository(session=session)
            email_ingestion_service = EmailIngestionService(
                email_repository=email_repository
            )
            job_repository: JobRepository = JobRepository(session)
            job_service: JobService = JobService(job_repository=job_repository)
            job_service.update_job(
                job_id=job_id,
                status=JobStatus.running,
                phase=JobPhase.METADATA_DISCOVERY,
            )
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


@app.task(name="thread_expansion")
def expand_emails_per_thread(job_id: str, email_account_id: str):
    return asyncio.run(
        _expand_emails_per_thread(job_id=job_id, email_account_id=email_account_id)
    )


async def _expand_emails_per_thread(*, job_id: str, email_account_id: str):
    strategy = None
    try:
        with celery_session() as session:
            email_repository: EmailRepository = EmailRepository(session=session)
            email_ingestion_service = EmailIngestionService(
                email_repository=email_repository
            )
            job_repository: JobRepository = JobRepository(session)
            job_service: JobService = JobService(job_repository=job_repository)

            # Mark job as running in THREAD_EXPANSION phase
            job_service.update_job(
                job_id=job_id,
                status=JobStatus.running,
                phase=JobPhase.THREAD_EXPANSION,
            )

            # Load email account
            email_account_repo = EmailAccountRepository(session=session)
            email_account_uuid = uuid.UUID(email_account_id)
            email_account: EmailAccount | None = email_account_repo.find_by_id(
                email_account_uuid
            )

            if email_account is None:
                return {
                    "status": "error",
                    "message": f"EmailAccount with id {email_account_id} not found",
                }

            # Load provider-specific auth data
            auth_data_strategy = AuthDataStrategyFactory.create(email_account.provider)
            auth_data = auth_data_strategy.load_auth_data(session, email_account_uuid)

            if auth_data is None:
                return {
                    "status": "error",
                    "message": f"No auth data found for EmailAccount {email_account_id}",
                }

            if not auth_data.access_token:
                return {
                    "status": "error",
                    "message": f"Access token not available. Please re-authenticate {email_account.provider}.",
                }

            user_identifier = auth_data_strategy.get_user_identifier(auth_data)
            if not user_identifier:
                return {
                    "status": "error",
                    "message": "User identifier not found in auth data",
                }

            # Create provider strategy (will delegate to the appropriate client, e.g. GmailClient)
            strategy = EmailProviderStrategyFactory.create(email_account.provider)

            total_messages = 0
            offset = 0
            limit = 500
            unique_thread_count = email_repository.get_distinct_thread_count(
                email_account_id=email_account_id
            )

            while offset < unique_thread_count:
                thread_ids = email_repository.get_distinct_thread_ids(
                    user_id=email_account.user_id,
                    email_account_id=email_account.id,
                    offset=offset,
                    limit=limit,
                )

                if not thread_ids:
                    break

                # Fetch all messages for these thread IDs via the provider strategy
                messages = await strategy.fetch_messages_by_thread_ids(
                    thread_ids,
                    access_token=auth_data.access_token,
                    user_identifier=user_identifier,
                    format="metadata",
                )

                # Attach context so the ingestion service can map to Email rows
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

                email_ingestion_service.batch_upsert_email_metadata(data=kept)
                total_messages += len(messages)

                job_service.update_job(job_id, progress_current=total_messages)

                offset += len(thread_ids)

            job_service.update_job(
                job_id,
                status=JobStatus.succeeded,
                completed_at=datetime.now(timezone.utc),
                progress_total=total_messages,
            )

            return {
                "status": "success",
                "message_count": total_messages,
            }

    except Exception as ex:
        with celery_session() as session:
            job_repo = JobRepository(session=session)
            job_service = JobService(job_repo)
            job_service.update_job(
                job_id=job_id, status=JobStatus.failed, error_message=str(ex)
            )
        return {"status": "error", "message": str(ex)}

    finally:
        if strategy:
            await strategy.close()


@app.task(name="fetch_email_content")
def fetch_email_content(job_id: str, email_account_id: str):
    asyncio.run(_fetch_email_content(job_id=job_id, email_account_id=email_account_id))


async def _fetch_email_content(job_id: str, email_account_id: str) -> None:
    """
    - Load emails from DB in batches of 500
    - Fetch Email Content
    - Parse email content from payload (https://developers.google.com/workspace/gmail/api/reference/rest/v1/Format?_gl=1*1ptuhwr*_up*MQ..*_ga*NzM0MDIyMjIwLjE3NzI3NjcwMDc.*_ga_SM8HXJ53K2*czE3NzI3NjcwMDckbzEkZzAkdDE3NzI3NjcwMDckajYwJGwwJGgw)
    - Use BeautifulSoup / Go though the individual mime parts in payload and normalize text.
    - Store in DB
    """
    strategy = None
    try:
        with celery_session() as session:
            email_repository: EmailRepository = EmailRepository(session=session)
            # NOTE: EmailIngestionService will be extended to handle content writes.
            email_ingestion_service = EmailIngestionService(
                email_repository=email_repository
            )
            job_repository: JobRepository = JobRepository(session)
            job_service: JobService = JobService(job_repository=job_repository)

            # Mark job as running in CONTENT_FETCH phase
            job_service.update_job(
                job_id=job_id,
                status=JobStatus.running,
                phase=JobPhase.CONTENT_FETCH,
            )

            # Load email account
            email_account_repo = EmailAccountRepository(session=session)
            email_account_uuid = uuid.UUID(email_account_id)
            email_account: EmailAccount | None = email_account_repo.find_by_id(
                email_account_uuid
            )

            if email_account is None:
                return {
                    "status": "error",
                    "message": f"EmailAccount with id {email_account_id} not found",
                }

            # Load provider-specific auth data
            auth_data_strategy = AuthDataStrategyFactory.create(email_account.provider)
            auth_data = auth_data_strategy.load_auth_data(session, email_account_uuid)

            if auth_data is None:
                return {
                    "status": "error",
                    "message": f"No auth data found for EmailAccount {email_account_id}",
                }

            if not auth_data.access_token:
                return {
                    "status": "error",
                    "message": f"Access token not available. Please re-authenticate {email_account.provider}.",
                }

            user_identifier = auth_data_strategy.get_user_identifier(auth_data)
            if not user_identifier:
                return {
                    "status": "error",
                    "message": "User identifier not found in auth data",
                }

            # Provider-specific strategy (e.g., Gmail) for fetching full message content
            strategy = EmailProviderStrategyFactory.create(email_account.provider)
            email_parser = EmailContentParserFactory.create(email_account.provider)

            # Total number of unique Email rows for this account
            total_messages = email_repository.get_email_count(
                email_account_id=email_account_uuid
            )

            offset = 0
            batch_size = 100
            processed = 0

            # Read emails in batches of 500 using offset; stop when offset exceeds total_messages.
            while offset < total_messages:
                emails_batch = email_repository.get_emails_batch(
                    email_account_id=email_account_uuid,
                    offset=offset,
                    limit=batch_size,
                )

                if not emails_batch:
                    break

                message_ids = [email.external_id for email in emails_batch]

                # Fetch full message content for this batch
                messages = await strategy.fetch_messages_by_ids(
                    message_ids,
                    access_token=auth_data.access_token,
                    user_identifier=user_identifier,
                    format="full",
                )

                for message in messages:
                    parsed_email: ParsedEmailContent = email_parser.parse(message)

                # TODO: Parse MIME parts and persist EmailContent via EmailIngestionService.
                processed += len(messages)

                job_service.update_job(job_id, progress_current=processed)

                offset += len(emails_batch)

            job_service.update_job(
                job_id=job_id,
                status=JobStatus.succeeded,
                completed_at=datetime.now(timezone.utc),
                progress_total=processed,
            )

            return {
                "status": "success",
                "message_count": processed,
            }

    except Exception as ex:
        with celery_session() as session:
            job_repo = JobRepository(session=session)
            job_service = JobService(job_repo)
            job_service.update_job(
                job_id=job_id, status=JobStatus.failed, error_message=str(ex)
            )
        return {"status": "error", "message": str(ex)}

    finally:
        if strategy:
            await strategy.close()
