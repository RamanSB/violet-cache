from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlmodel import SQLModel, select

from app.db import SessionDep
from app.models import User

router = APIRouter()


@router.get("/")
def root():
    return {"message": "Hello World!"}


class RegistrationRequest(SQLModel):
    email: EmailStr


# Onboarding
@router.post("/auth/register")
def register_email(
    # request: Request
    req: RegistrationRequest,
    session: SessionDep,
) -> Response:
    # Move this logic in to a repository class (#get_or_create_user)
    existing = session.exec(select(User).where(User.email == req.email)).first()
    if existing:
        # TODO: Send them a magic link email (if they are not yet validated)
        raise HTTPException(
            status_code=409,
            detail="Please check your inbox for a verification link to confirm your email address.",
        )

    user = User(email=req.email, is_registered=False)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
