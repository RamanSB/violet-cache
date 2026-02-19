"""Factory for creating email provider strategies."""

from app.enums import EmailProvider
from app.strategies.email_provider_strategy import EmailProviderStrategy
from app.strategies.gmail_strategy import GmailStrategy


class EmailProviderStrategyFactory:
    """Factory to create appropriate email provider strategy instances."""

    _strategies: dict[EmailProvider, type[EmailProviderStrategy]] = {
        EmailProvider.GMAIL: GmailStrategy,
        # Add more providers here as they're implemented
        # EmailProvider.OUTLOOK: OutlookStrategy,
    }

    @classmethod
    def create(cls, provider: EmailProvider) -> EmailProviderStrategy:
        """
        Create a strategy instance for the given provider.

        Args:
            provider: Email provider enum

        Returns:
            Strategy instance for the provider

        Raises:
            ValueError: If provider is not supported
        """
        strategy_class = cls._strategies.get(provider)
        if not strategy_class:
            raise ValueError(f"Unsupported email provider: {provider}")

        return strategy_class()
