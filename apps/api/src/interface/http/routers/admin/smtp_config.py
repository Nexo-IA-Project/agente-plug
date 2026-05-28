from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from interface.http.deps.admin_auth import AdminAuth, require_admin_role
from shared.adapters.db.repositories.smtp_config_repo import SmtpConfigRepository
from shared.adapters.db.session import session_scope
from shared.adapters.email.smtp_email_service import SmtpEmailService

router = APIRouter(tags=["admin-smtp"])


class SmtpConfigResponse(BaseModel):
    host: str
    port: int
    username: str
    use_tls: bool
    from_name: str
    from_email: EmailStr
    has_password: bool


class SmtpConfigRequest(BaseModel):
    host: str = Field(min_length=1, max_length=200)
    port: int = Field(ge=1, le=65535)
    username: str = Field(min_length=1, max_length=200)
    password: str | None = None
    use_tls: bool
    from_name: str = Field(min_length=1, max_length=100)
    from_email: EmailStr


class TestEmailRequest(BaseModel):
    to: EmailStr


@router.get("/smtp-config", response_model=SmtpConfigResponse | None)
async def get_config(
    auth: AdminAuth = Depends(require_admin_role),
) -> SmtpConfigResponse | None:
    async with session_scope() as s:
        repo = SmtpConfigRepository(s)
        cfg = await repo.get(account_id=auth.account_id)
        if cfg is None:
            return None
        return SmtpConfigResponse(
            host=cfg.host,
            port=cfg.port,
            username=cfg.username,
            use_tls=cfg.use_tls,
            from_name=cfg.from_name,
            from_email=cfg.from_email,
            has_password=True,
        )


@router.put("/smtp-config", response_model=SmtpConfigResponse)
async def upsert_config(
    body: SmtpConfigRequest,
    auth: AdminAuth = Depends(require_admin_role),
) -> SmtpConfigResponse:
    async with session_scope() as s:
        repo = SmtpConfigRepository(s)
        existing = await repo.get(account_id=auth.account_id)

        if not body.password:
            if existing is None:
                raise HTTPException(status_code=422, detail="Password required for new config")
            password_to_store = repo.decrypt_password(existing.encrypted_password)
        else:
            password_to_store = body.password

        cfg = await repo.upsert(
            account_id=auth.account_id,
            host=body.host,
            port=body.port,
            username=body.username,
            password_plaintext=password_to_store,
            use_tls=body.use_tls,
            from_name=body.from_name,
            from_email=body.from_email,
        )
        await s.commit()
        return SmtpConfigResponse(
            host=cfg.host,
            port=cfg.port,
            username=cfg.username,
            use_tls=cfg.use_tls,
            from_name=cfg.from_name,
            from_email=cfg.from_email,
            has_password=True,
        )


@router.post("/smtp-config/test")
async def test_smtp(
    body: TestEmailRequest,
    auth: AdminAuth = Depends(require_admin_role),
) -> dict[Literal["ok"], bool]:
    async with session_scope() as s:
        repo = SmtpConfigRepository(s)
        svc = SmtpEmailService(repo=repo)
        try:
            await svc.send_email(
                account_id=auth.account_id,
                to=body.to,
                subject="Teste de configuração SMTP — NexoIA",
                body_html="<p>Este é um email de teste. Sua configuração SMTP está funcionando.</p>",
            )
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"SMTP test failed: {e}") from e
    return {"ok": True}
