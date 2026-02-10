import asyncio
from typing import List
from app.tasks.celery.celery import app

from app.celery_db import celery_session
from app.client.gmail import GmailClient
from app.enums import EmailProvider
from app.models.models import GoogleAuthData
from app.repositories.google_auth import GoogleAuthDataRepository


@app.task(name="ingest_user_email")
def ingest_user_email_ids(user_id: str, email_provider: EmailProvider) -> None:
    asyncio.run(_ingest_user_email_ids(user_id, email_provider))


async def _ingest_user_email_ids(user_id: str, email_provider: EmailProvider):
    # TODO: use a strategy pattern based on email provider.
    with celery_session() as session:
        google_auth_repo = GoogleAuthDataRepository(session=session)
        google_auth_data: GoogleAuthData | None = google_auth_repo.find_by_user_id(
            user_id
        )

        if google_auth_data is None:
            print(f"Unable to find Google Auth Data for user_id: {user_id}")
            return

        access_token = google_auth_data.access_token
        google_user_id = google_auth_data.google_user_id
        gmail_client: GmailClient = GmailClient()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        try:
            message_ids: List[str] = await gmail_client.list_messages(
                google_user_id=google_user_id,
                headers=headers,
                params={"includeSpamTrash": "false"},
            )

            messages = await gmail_client.fetch_messages_by_ids(
                message_ids, headers=headers, google_user_id=google_user_id
            )

            # TODO: Persist messages to DB.
            print("...")

        finally:
            await gmail_client.close()
