"""Email provider strategy implementations."""

from app.strategies.gmail_strategy import GmailStrategy
from app.strategies.email_provider_strategy import EmailProviderStrategy
from app.strategies.auth_data_strategy import AuthDataStrategy, AuthData
from app.strategies.gmail_auth_data_strategy import GmailAuthDataStrategy
from app.strategies.strategy_factory import EmailProviderStrategyFactory
from app.strategies.auth_data_strategy_factory import AuthDataStrategyFactory

__all__ = [
    "GmailStrategy",
    "EmailProviderStrategy",
    "AuthDataStrategy",
    "AuthData",
    "GmailAuthDataStrategy",
    "EmailProviderStrategyFactory",
    "AuthDataStrategyFactory",
]
