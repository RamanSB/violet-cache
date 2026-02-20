from typing import Annotated
from fastapi import Depends
from app.db import SessionDep
from app.repositories.job_repository import JobRepository
from app.repositories.user import UserRepository
from app.repositories.google_auth import GoogleAuthDataRepository
from app.repositories.email_account import EmailAccountRepository
from app.services.google_oauth_service import GoogleOAuthService
from app.services.job_service import JobService
from app.services.user_service import UserService
from app.services.email_account_service import EmailAccountService


def get_job_repository(session: SessionDep) -> JobRepository:
    return JobRepository(session)


def get_user_repository(session: SessionDep) -> UserRepository:
    """Dependency to get UserRepository instance."""
    return UserRepository(session)


def get_google_auth_repository(session: SessionDep) -> GoogleAuthDataRepository:
    """Dependency to get GoogleAuthDataRepository instance."""
    return GoogleAuthDataRepository(session)


def get_email_account_repository(session: SessionDep) -> EmailAccountRepository:
    """Dependency to get EmailAccountRepository instance."""
    return EmailAccountRepository(session)


def get_user_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    """Dependency to get UserService instance."""
    return UserService(user_repo)


def get_job_service(
    job_repo: Annotated[JobRepository, Depends(get_job_repository)],
) -> JobService:
    return JobService(job_repo)


def get_email_account_service(
    email_account_repo: Annotated[
        EmailAccountRepository, Depends(get_email_account_repository)
    ],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    google_auth_repo: Annotated[
        GoogleAuthDataRepository, Depends(get_google_auth_repository)
    ],
) -> EmailAccountService:
    """Dependency to get EmailAccountService instance."""
    return EmailAccountService(email_account_repo, user_repo, google_auth_repo)


def get_google_oauth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    google_auth_repo: Annotated[
        GoogleAuthDataRepository, Depends(get_google_auth_repository)
    ],
    email_account_service: Annotated[
        EmailAccountService, Depends(get_email_account_service)
    ],
) -> GoogleOAuthService:
    """Dependency to get GoogleOAuthService instance."""
    return GoogleOAuthService(user_repo, google_auth_repo, email_account_service)


# Type aliases for cleaner route signatures
JobRepositoryDep = Annotated[JobRepository, Depends(get_job_repository)]
UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]
GoogleAuthRepositoryDep = Annotated[
    GoogleAuthDataRepository, Depends(get_google_auth_repository)
]
EmailAccountRepositoryDep = Annotated[
    EmailAccountRepository, Depends(get_email_account_repository)
]
JobServiceDep = Annotated[JobService, Depends(get_job_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
EmailAccountServiceDep = Annotated[
    EmailAccountService, Depends(get_email_account_service)
]
GoogleOAuthServiceDep = Annotated[GoogleOAuthService, Depends(get_google_oauth_service)]
