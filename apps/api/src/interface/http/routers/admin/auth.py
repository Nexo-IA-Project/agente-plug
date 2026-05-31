from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from jose import JWTError
from pydantic import BaseModel

from interface.http.deps.admin_auth import AdminAuth, require_admin
from shared.adapters.db.repositories.identity_repo import IdentityRepository
from shared.adapters.db.repositories.membership_repo import MembershipRepository
from shared.adapters.db.session import session_scope
from shared.adapters.kb.jwt_handler import create_access_token, verify_password, verify_token
from shared.config.settings import get_settings

router = APIRouter(tags=["admin-auth"])

_COOKIE_NAME = "nexoia_token"


class LoginRequest(BaseModel):
    email: str
    password: str
    account_id: int | None = None  # ignorado — mantido só para compatibilidade


class AccountOption(BaseModel):
    membership_id: str
    account_id: str
    account_name: str
    role: str
    is_owner: bool


class LoginResultResponse(BaseModel):
    status: str  # "authenticated" | "choose_account" | "must_change_password"
    access_token: str | None = None
    pre_auth_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    accounts: list[AccountOption] | None = None
    must_change_password: bool = False


class SelectAccountRequest(BaseModel):
    account_id: str


def _full_token(identity: Any, view: Any, settings: Any) -> str:
    return create_access_token(
        data={
            "sub": identity.email,
            "identity_id": identity.id,
            "user_id": identity.id,
            "user_name": identity.name,
            "account_id": str(view.account_id),
            "membership_id": view.membership_id,
            "role": view.role.value,
            "must_change_password": identity.must_change_password,
        },
        secret=settings.jwt_secret,
        expire_minutes=settings.jwt_expire_minutes,
    )


def _pre_auth_token(identity: Any, settings: Any) -> str:
    return create_access_token(
        data={
            "sub": identity.email,
            "identity_id": identity.id,
            "user_id": identity.id,
            "user_name": identity.name,
            "scope": "pre_auth",
            "must_change_password": identity.must_change_password,
        },
        secret=settings.jwt_secret,
        expire_minutes=10,
    )


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


@router.post("/auth/login", response_model=LoginResultResponse)
async def login(body: LoginRequest, request: Request, response: Response) -> LoginResultResponse:
    settings = get_settings()
    async with get_db() as session:
        identity = await IdentityRepository(session).get_by_email(body.email)
        if identity is None or not verify_password(body.password, identity.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not identity.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive",
            )

        views = await MembershipRepository(session).list_active_by_identity(identity.id)
        await IdentityRepository(session).touch_last_login(identity.id)
        await session.commit()

    if identity.must_change_password:
        return LoginResultResponse(
            status="must_change_password",
            pre_auth_token=_pre_auth_token(identity, settings),
            must_change_password=True,
        )
    if not views:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem acesso a nenhuma empresa",
        )
    if len(views) == 1:
        token = _full_token(identity, views[0], settings)
        max_age = settings.jwt_expire_minutes * 60
        response.set_cookie(
            key=_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            max_age=max_age,
            path="/",
        )
        asyncio.create_task(  # noqa: RUF006
            _save_auth_audit(
                account_id=str(views[0].account_id),
                user_id=identity.id,
                user_email=identity.email,
                ip=_extract_login_ip(request),
                action="Login",
                user_agent=request.headers.get("user-agent", ""),
            )
        )
        return LoginResultResponse(status="authenticated", access_token=token, expires_in=max_age)
    return LoginResultResponse(
        status="choose_account",
        pre_auth_token=_pre_auth_token(identity, settings),
        accounts=[
            AccountOption(
                membership_id=v.membership_id,
                account_id=str(v.account_id),
                account_name=v.account_name,
                role=v.role.value,
                is_owner=v.is_owner,
            )
            for v in views
        ],
    )


async def _emit_for_account(
    identity_id: str, account_id_raw: str, request: Request, response: Response
) -> LoginResultResponse:
    from uuid import UUID as _UUID

    settings = get_settings()
    try:
        account_uuid = _UUID(account_id_raw)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail="Invalid account_id") from e

    async with get_db() as session:
        identity = await IdentityRepository(session).get_by_id(identity_id)
        if identity is None or not identity.is_active:
            raise HTTPException(status_code=401, detail="Invalid identity")
        views = await MembershipRepository(session).list_active_by_identity(identity_id)
    match = next((v for v in views if str(v.account_id) == str(account_uuid)), None)
    if match is None:
        raise HTTPException(status_code=403, detail="Sem vínculo ativo com esta empresa")
    token = _full_token(identity, match, settings)
    max_age = settings.jwt_expire_minutes * 60
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    return LoginResultResponse(status="authenticated", access_token=token, expires_in=max_age)


@router.post("/auth/select-account", response_model=LoginResultResponse)
async def select_account(
    body: SelectAccountRequest,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    nexoia_token: str | None = Cookie(default=None),
) -> LoginResultResponse:
    token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif nexoia_token:
        token = nexoia_token
    if not token:
        raise HTTPException(status_code=401, detail="Missing credentials")
    try:
        payload = verify_token(token, secret=get_settings().jwt_secret)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    identity_id = payload.get("identity_id") or payload.get("user_id", "")
    return await _emit_for_account(identity_id, body.account_id, request, response)


@router.post("/auth/switch-account", response_model=LoginResultResponse)
async def switch_account(
    body: SelectAccountRequest,
    request: Request,
    response: Response,
    auth: AdminAuth = Depends(require_admin),
) -> LoginResultResponse:
    return await _emit_for_account(auth.identity_id, body.account_id, request, response)


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
