from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from shared.adapters.db.models import AdminUserModel
from shared.adapters.db.session import session_scope
from shared.adapters.kb.jwt_handler import create_access_token, verify_password
from shared.config.settings import get_settings

router = APIRouter(tags=["admin-auth"])

_COOKIE_NAME = "nexoia_token"


class LoginRequest(BaseModel):
    email: str
    password: str
    account_id: int


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


def get_db():
    """Return the async context manager for a DB session."""
    return session_scope()


@router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest, response: Response) -> LoginResponse:
    settings = get_settings()

    async with get_db() as session:
        result = await session.execute(
            select(AdminUserModel)
            .where(AdminUserModel.account_id == body.account_id)
            .where(AdminUserModel.email == body.email)
        )
        user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    max_age = settings.jwt_expire_minutes * 60
    token = create_access_token(
        data={
            "sub": user.email,
            "account_id": user.account_id,
            "role": user.role,
            "user_id": str(user.id),
        },
        secret=settings.jwt_secret,
        expire_minutes=settings.jwt_expire_minutes,
    )
    # HttpOnly: JS cannot read this cookie — XSS cannot steal the token
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    return LoginResponse(
        access_token=token,
        expires_in=max_age,
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path="/", samesite="lax")
