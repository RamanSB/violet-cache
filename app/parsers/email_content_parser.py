from abc import ABC, abstractmethod
from typing import Any, Dict

from app.schema.schemas import ParsedEmailContent


class EmailContentParser(ABC):
    """
    Base class for provider-specific email content parsers.
    """

    @abstractmethod
    def parse(self, message: Dict[str, Any]) -> ParsedEmailContent:
        """
        Parse a provider message payload into canonical email content.

        Args:
            message: Provider-specific message object

        Returns:
            ParsedEmailContent
        """
        pass
