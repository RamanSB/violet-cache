"""Gmail-specific email provider strategy implementation."""

from typing import Any, Dict, List
from app.enums import EmailProvider
from app.strategies.email_provider_strategy import EmailProviderStrategy
from app.client.gmail import GmailClient


class GmailStrategy(EmailProviderStrategy):
    """Strategy implementation for Gmail provider."""

    def __init__(self):
        self._client = GmailClient()

    def get_provider(self) -> EmailProvider:
        """Return Gmail provider."""
        return EmailProvider.GMAIL

    async def list_messages(
        self,
        *,
        access_token: str,
        user_identifier: str,
        max_results_per_page: int = 500,
        include_spam_trash: bool = False,
    ) -> List[str]:
        """List Gmail message IDs."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        return await self._client.list_messages(
            google_user_id=user_identifier,
            headers=headers,
            max_results_per_page=max_results_per_page,
            include_spam_trash=include_spam_trash,
        )

    async def fetch_messages_by_ids(
        self,
        message_ids: List[str],
        *,
        access_token: str,
        user_identifier: str,
    ) -> List[Dict[str, Any]]:
        """Fetch Gmail messages by IDs."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        return await self._client.fetch_messages_by_ids(
            message_ids,
            headers=headers,
            google_user_id=user_identifier,
        )

    async def close(self) -> None:
        """Close Gmail client connections."""
        await self._client.close()
