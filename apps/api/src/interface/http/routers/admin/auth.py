from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from shared.adapters.db.models import UserModel
from shared.adapters.db.session import session_scope
from shared.adapters.kb.jwt_handler import create_access_token, verify_password, verify_token
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


def get_db() -> Any:
    return session_scope()


def _extract_login_ip(request: Request) -> str:
    cf = request.headers.get("CF-Connecting-IP")
    if cf:
        return cf.strip()
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


async def _save_auth_audit(
    *,
    account_id: str,
    user_id: str,
    user_email: str,
    ip: str,
    action: str = "Login",
    user_agent: str = "",
) -> None:
    from uuid import UUID as _UUID

    from shared.adapters.db.repositories.audit_repo import SqlAuditRepository
    from shared.adapters.db.session import session_scope
    from shared.adapters.geo.ip_api import IpApiGeoService
    from shared.domain.entities.audit_event import AuditEvent

    event_id = uuid4()
    try:
        _account_id = _UUID(str(account_id)) if account_id else None
        if _account_id is None:
            return
        event = AuditEvent(
            id=event_id,
            account_id=_account_id,
            actor=user_email,
            user_id=user_id or None,
            user_name=user_email,
            action=action,
            resource_type="auth",
            resource_id=None,
            ip_address=ip or None,
            geo_city=None,
            geo_country=None,
            geo_region=None,
            metadata={"user_agent": user_agent} if user_agent else {},
        )
        async with session_scope() as session:
            repo = SqlAuditRepository(session=session)
            await repo.save(event)
        if ip:
            geo = IpApiGeoService()
            result = await geo.lookup(ip)
            if result:
                async with session_scope() as session:
                    repo = SqlAuditRepository(session=session)
                    await repo.update_geo(
                        event_id, city=result.city, country=result.country, region=result.region
                    )
    except Exception:
        pass


@router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response) -> LoginResponse:
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
            "name": user.name,
            "account_id": user.account_id,
            "role": user.role,
            "must_change_password": user.must_change_password,
        }
        await session.commit()

    _login_task = asyncio.create_task(
        _save_auth_audit(
            account_id=str(snapshot["account_id"]),
            user_id=str(snapshot["id"]),
            user_email=snapshot["email"],
            ip=_extract_login_ip(request),
            action="Login",
            user_agent=request.headers.get("user-agent", ""),
        )
    )
    del _login_task

    max_age = settings.jwt_expire_minutes * 60
    token = create_access_token(
        data={
            "sub": snapshot["email"],
            "account_id": str(snapshot["account_id"]),
            "role": snapshot["role"],
            "user_id": snapshot["id"],
            "user_name": snapshot["name"],
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
async def logout(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    nexoia_token: str | None = Cookie(default=None),
) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path="/", samesite="lax")
    token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif nexoia_token:
        token = nexoia_token
    if token:
        try:
            settings = get_settings()
            payload = verify_token(token, secret=settings.jwt_secret)
            _logout_task = asyncio.create_task(
                _save_auth_audit(
                    account_id=str(payload.get("account_id", "")),
                    user_id=str(payload.get("user_id", "")),
                    user_email=payload.get("sub", ""),
                    ip=_extract_login_ip(request),
                    action="Logout",
                    user_agent=request.headers.get("user-agent", ""),
                )
            )
            del _logout_task
        except Exception:
            pass
