from sqlmodel import Session, select
import uuid
from app.models.models import User


class UserRepository:
    """Repository for User model database operations."""

    def __init__(self, session: Session):
        self.session = session

    def find_by_email(self, email: str) -> User | None:
        """Find a user by email."""
        return self.session.exec(select(User).where(User.email == email)).first()

    def create(
        self,
        email: str,
        first_name: str | None = None,
        last_name: str | None = None,
        is_registered: bool = True,
    ) -> User:
        """Create a new user."""
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_registered=is_registered,
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def update(self, user: User) -> User:
        """Update an existing user."""
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def find_by_id(self, user_id: uuid.UUID) -> User | None:
        """Find a user by ID."""
        return self.session.get(User, user_id)
