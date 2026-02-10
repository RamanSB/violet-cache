import asyncio
import json
import random
from typing import Any, Dict, List


import httpx
from aiolimiter import AsyncLimiter
from sqlmodel import Session

from app.client.gmail import GmailClient
from app.db import engine
from app.repositories.google_auth import GoogleAuthDataRepository

BASE_URL = "https://gmail.googleapis.com/gmail/v1"
OAUTH_ACCESS_TOKEN = ""
MY_GOOGLE_USER_ID = ""

HEADERS = {
    "Authorization": f"Bearer {OAUTH_ACCESS_TOKEN}",
    "Accept": "application/json",
}

RETRYABLE_STATUS = {403, 429, 500, 502, 503, 504}


async def get_with_backoff(
    client: httpx.AsyncClient, url: str, *, max_retries: int = 8
) -> httpx.Response:
    """
    Retries on Gmail rate limits / transient errors with exponential backoff + jitter.
    """
    last_exc = None
    for attempt in range(max_retries):
        try:
            r = await client.get(url, headers=HEADERS)
            if r.status_code < 400:
                return r

            # Gmail often returns 403 for rate-limit exceeded (rateLimitExceeded)
            if r.status_code in RETRYABLE_STATUS:
                delay = min(60.0, (2**attempt) * 0.5) + random.random() * 0.25
                await asyncio.sleep(delay)
                continue

            r.raise_for_status()

        except (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_exc = e
            delay = min(60.0, (2**attempt) * 0.5) + random.random() * 0.25
            await asyncio.sleep(delay)

    if last_exc:
        raise last_exc
    raise RuntimeError("Retries exhausted")


async def fetch_message(
    client: httpx.AsyncClient,
    user_id: str,
    msg_id: str,
) -> Dict[str, Any]:
    # Pull less data if you don’t need full payload:
    # format=metadata is usually enough, adjust as needed.
    url = f"{BASE_URL}/users/{user_id}/messages/{msg_id}?format=metadata"
    r = await get_with_backoff(client, url)
    return r.json()


async def fetch_messages_by_ids(
    message_ids: List[str],
    *,
    user_id: str = MY_GOOGLE_USER_ID,
    concurrency: int = 20,  # max in-flight requests
    rps: int = 50,  # max requests per second (tune)
) -> List[Dict[str, Any]]:
    sem = asyncio.Semaphore(concurrency)
    limiter = AsyncLimiter(rps, time_period=1)  # rps per 1 second window

    async with httpx.AsyncClient(timeout=30.0) as client:

        async def one(mid: str) -> Dict[str, Any]:
            async with sem:
                async with limiter:
                    return await fetch_message(client, user_id, mid)

        # gather schedules all coroutines; limiter+sem prevents flooding
        coros = [one(mid) for mid in message_ids]
        return await asyncio.gather(*coros)


async def test_email_fetch():
    MY_USER_ID_PK = "6594e29d-2651-4346-8b68-65d50ec278a6"
    with Session(engine) as session:
        google_auth_repo = GoogleAuthDataRepository(session)
        google_auth_data = google_auth_repo.find_by_user_id(MY_USER_ID_PK)
        headers = {
            "Authorization": f"Bearer {google_auth_data.access_token}",
            "Content-Type": "application/json",
        }
        gmail_client = GmailClient()

        try:
            message_ids = await gmail_client.list_messages(
                google_user_id=google_auth_data.google_user_id,
                headers=headers,
                # q="in:spam OR in:trash",
                include_spam_trash=False,
            )

            sample_msg_ids = message_ids[:200]

            email_messages = await gmail_client.fetch_messages_by_ids(
                message_ids=sample_msg_ids,
                headers=headers,
                google_user_id=google_auth_data.google_user_id,
            )

            with open(
                "/Users/raman/Documents/Development/Projects/notes-lab/app/data/json/all_emails_full_format.json",
                "w",
            ) as file:
                json.dump(email_messages, file)

        finally:
            await gmail_client.close()


if __name__ == "__main__":
    # import pathlib

    # ids_path = pathlib.Path("app/data/json/message_ids.json")
    # out_path = pathlib.Path("app/data/json/all_emails_metadata.json")

    # message_ids = json.loads(ids_path.read_text())

    # # start small first
    # sample = message_ids[:500]

    # results = asyncio.run(fetch_messages_by_ids(sample, concurrency=15, rps=50))
    # out_path.write_text(json.dumps(results, indent=2))
    # print(f"Wrote {len(results)} messages to {out_path}")
    asyncio.run(test_email_fetch())
