"""Factory for creating auth data strategies."""

from app.enums import EmailProvider
from app.strategies.auth_data_strategy import AuthDataStrategy
from app.strategies.gmail_auth_data_strategy import GmailAuthDataStrategy


class AuthDataStrategyFactory:
    """Factory to create appropriate auth data strategy instances."""

    _strategies: dict[EmailProvider, type[AuthDataStrategy]] = {
        EmailProvider.GMAIL: GmailAuthDataStrategy,
        # Add more providers here as they're implemented
        # EmailProvider.OUTLOOK: OutlookAuthDataStrategy,
    }

    @classmethod
    def create(cls, provider: EmailProvider) -> AuthDataStrategy:
        """
        Create an auth data strategy instance for the given provider.

        Args:
            provider: Email provider enum

        Returns:
            Auth data strategy instance for the provider

        Raises:
            ValueError: If provider is not supported
        """
        strategy_class = cls._strategies.get(provider)
        if not strategy_class:
            raise ValueError(f"Unsupported email provider for auth data: {provider}")

        return strategy_class()
