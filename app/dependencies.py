from typing import Annotated
from fastapi import Depends
from app.db import SessionDep
from app.repositories.user import UserRepository
from app.repositories.google_auth import GoogleAuthDataRepository
from app.services.google_oauth_service import GoogleOAuthService
from app.services.user_service import UserService


def get_user_repository(session: SessionDep) -> UserRepository:
    """Dependency to get UserRepository instance."""
    return UserRepository(session)


def get_google_auth_repository(session: SessionDep) -> GoogleAuthDataRepository:
    """Dependency to get GoogleAuthDataRepository instance."""
    return GoogleAuthDataRepository(session)


def get_user_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    """Dependency to get UserService instance."""
    return UserService(user_repo)


def get_google_oauth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    google_auth_repo: Annotated[
        GoogleAuthDataRepository, Depends(get_google_auth_repository)
    ],
) -> GoogleOAuthService:
    """Dependency to get GoogleOAuthService instance."""
    return GoogleOAuthService(user_repo, google_auth_repo)


# Type aliases for cleaner route signatures
UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]
GoogleAuthRepositoryDep = Annotated[
    GoogleAuthDataRepository, Depends(get_google_auth_repository)
]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
GoogleOAuthServiceDep = Annotated[GoogleOAuthService, Depends(get_google_oauth_service)]
