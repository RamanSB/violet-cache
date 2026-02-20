"""Strategy pattern for email provider implementations."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List
from app.enums import EmailProvider


class EmailProviderStrategy(ABC):
    """Abstract base class for email provider strategies."""

    @abstractmethod
    def get_provider(self) -> EmailProvider:
        """Return the email provider this strategy handles."""
        pass

    @abstractmethod
    async def list_messages(
        self,
        *,
        access_token: str,
        user_identifier: str,
        max_results_per_page: int = 500,
        include_spam_trash: bool = False,
        label_ids: List[str] = [],
    ) -> AsyncIterator[List[str]]:
        """
        List message IDs from the email provider.

        Args:
            access_token: OAuth access token
            user_identifier: Provider-specific user identifier (e.g., google_user_id)
            max_results_per_page: Maximum results per page
            include_spam_trash: Whether to include spam/trash messages

        Returns:
            List of message IDs
        """
        pass

    @abstractmethod
    async def fetch_messages_by_ids(
        self,
        message_ids: List[str],
        *,
        access_token: str,
        user_identifier: str,
        format: str | None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch full message data by message IDs.

        Args:
            message_ids: List of message IDs to fetch
            access_token: OAuth access token
            user_identifier: Provider-specific user identifier

        Returns:
            List of message dictionaries
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any open connections/resources."""
        pass
