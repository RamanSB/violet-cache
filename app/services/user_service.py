"""Service layer for user operations."""

from app.repositories.user import UserRepository
from app.models.models import User


class UserService:
    """Service layer for user operations."""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def register_email(self, email: str) -> User:
        """
        Register a new email address.

        Args:
            email: Email address to register

        Returns:
            User: Created user object

        Raises:
            ValueError: If email is already registered
        """
        existing = self.user_repo.find_by_email(email)
        if existing:
            raise ValueError(
                "Please check your inbox for a verification link to confirm your email address."
            )

        user = self.user_repo.create(email=email, is_registered=False)
        return user
