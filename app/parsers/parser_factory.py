"""
Factory for creating provider-specific email content parsers.
"""

from typing import Dict, Type

from app.enums import EmailProvider
from app.parsers.email_content_parser import EmailContentParser
from app.parsers.gmail_content_parser import GmailContentParser


class EmailContentParserFactory:

    _parsers: Dict[EmailProvider, Type[EmailContentParser]] = {
        EmailProvider.GMAIL: GmailContentParser,
    }

    @classmethod
    def create(cls, provider: EmailProvider) -> EmailContentParser:
        parser_class = cls._parsers.get(provider)

        if not parser_class:
            raise ValueError(f"No parser implemented for provider: {provider}")

        return parser_class()
