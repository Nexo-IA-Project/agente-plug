from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from shared.adapters.db.models import UserModel
from shared.adapters.db.session import session_scope
from shared.adapters.kb.jwt_handler import create_access_token, verify_password
from shared.config.settings import get_settings

router = APIRouter(tags=["admin-auth"])

_COOKIE_NAME = "nexoia_token"


class LoginRequest(BaseModel):
    email: str
    password: str
    account_id: int | None = None  # ignorado — mantido só para compatibilidade


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def get_db():
    return session_scope()


@router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest, response: Response) -> LoginResponse:
    settings = get_settings()

    async with get_db() as session:
        result = await session.execute(select(UserModel).where(UserModel.email == body.email))
        user = result.scalar_one_or_none()

        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive",
            )

        user.last_login_at = datetime.now(UTC)
        await session.flush()

        snapshot = {
            "id": user.id,
            "email": user.email,
            "account_id": user.account_id,
            "role": user.role,
            "must_change_password": user.must_change_password,
        }
        await session.commit()

    max_age = settings.jwt_expire_minutes * 60
    token = create_access_token(
        data={
            "sub": snapshot["email"],
            "account_id": snapshot["account_id"],
            "role": snapshot["role"],
            "user_id": snapshot["id"],
            "must_change_password": snapshot["must_change_password"],
        },
        secret=settings.jwt_secret,
        expire_minutes=settings.jwt_expire_minutes,
    )
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    return LoginResponse(access_token=token, expires_in=max_age)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path="/", samesite="lax")
