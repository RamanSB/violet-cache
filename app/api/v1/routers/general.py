from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from sqlmodel import SQLModel

from app.dependencies import UserServiceDep

router = APIRouter()


@router.get("/")
def root():
    return {"message": "Hello World!"}


class RegistrationRequest(SQLModel):
    email: EmailStr


@router.post("/auth/register")
def register_email(req: RegistrationRequest, user_service: UserServiceDep):
    """
    Register a new email address.

    Validates request and delegates all business logic to the service.
    """
    try:
        user = user_service.register_email(req.email)
        return user
    except ValueError as e:
        # Email already registered
        raise HTTPException(status_code=409, detail=str(e))
