import asyncio
import random
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
from aiolimiter import AsyncLimiter

BASE_URL = "https://gmail.googleapis.com/gmail/v1"

# NOTE: 403 is *sometimes* retryable (rate limits), but can also be auth/scope problems.
# We'll keep your set, but in production you'd ideally inspect the JSON error reason.
RETRYABLE_STATUS = {403, 429, 500, 502, 503, 504}


class GmailClient:
    """
    - No __aenter__/__aexit__.
    - You MUST call `await close()` when you're done (important for sockets).
    - `list_messages` is async (recommended), so it won't block your event loop.
      If you're only running a standalone script, a sync version is fine too.
    """

    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        rps: int = 50,
        concurrency: int = 20,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url
        self._rps = rps
        self._concurrency = concurrency
        self._timeout = timeout

        self._client = httpx.AsyncClient(timeout=self._timeout)
        self._sem = asyncio.Semaphore(self._concurrency)
        self._limiter = AsyncLimiter(self._rps, time_period=1)

    async def close(self) -> None:
        await self._client.aclose()

    async def _get_with_backoff(
        self,
        url: str,
        *,
        headers: dict,
        params: Optional[dict] = None,
        max_retries: int = 8,
    ) -> httpx.Response:
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                r = await self._client.get(url, headers=headers, params=params)
                if r.status_code < 400:
                    return r

                if r.status_code in RETRYABLE_STATUS:
                    delay = min(60.0, (2**attempt) * 0.5) + random.random() * 0.25
                    await asyncio.sleep(delay)
                    continue

                r.raise_for_status()

            except (
                httpx.ReadTimeout,
                httpx.ConnectError,
                httpx.RemoteProtocolError,
            ) as e:
                last_exc = e
                delay = min(60.0, (2**attempt) * 0.5) + random.random() * 0.25
                await asyncio.sleep(delay)

        if last_exc:
            raise last_exc
        raise RuntimeError("Retries exhausted")

    async def list_messages(
        self,
        *,
        google_user_id: str,
        headers: dict,
        max_results_per_page: int = 500,
        q: Optional[str] = None,
        include_spam_trash: bool = True,
        label_ids: List[str] = [],
    ) -> AsyncIterator[List[str]]:
        """
        Recommended: async.
        Reason: if you call this inside FastAPI/Celery async flow, a sync `httpx.Client()`
        would block the event loop.

        Returns a list of Gmail message IDs.
        """
        url = f"{self.base_url}/users/{google_user_id}/messages"
        page_token: Optional[str] = None

        while True:
            params: Dict[str, Any] = {
                "maxResults": max_results_per_page,
                # IMPORTANT: serialize boolean in a Gmail-friendly way
                "includeSpamTrash": include_spam_trash,
            }
            if label_ids:
                params["labelIds"] = label_ids
            if q:
                params["q"] = q
            if page_token:
                params["pageToken"] = page_token
            r = await self._get_with_backoff(url=url, headers=headers, params=params)
            data = r.json()

            msg_ids: List[str] = [
                msg["id"] for msg in data.get("messages", []) if msg.get("id")
            ]

            yield msg_ids

            page_token = data.get("nextPageToken")
            if not page_token:
                break

    async def fetch_messages_by_ids(
        self,
        message_ids: List[str],
        *,
        google_user_id: str,
        headers: dict,
        format: str = "full",
    ) -> List[Dict[str, Any]]:
        """
        Fetch 1 or many messages.

        IMPORTANT: For very large lists (e.g. 50k), consider a worker-queue approach
        to avoid creating 50k coroutines at once. This version is fine for a few thousand.
        """

        async def one(mid: str) -> Dict[str, Any]:
            # both gates are inside per-request:
            # - sem: max in-flight requests
            # - limiter: max requests/sec
            async with self._sem:
                async with self._limiter:
                    url = f"{self.base_url}/users/{google_user_id}/messages/{mid}?format={format}"
                    r = await self._get_with_backoff(url, headers=headers)
                    return r.json()

        coros = [one(mid) for mid in message_ids]
        return await asyncio.gather(*coros)
