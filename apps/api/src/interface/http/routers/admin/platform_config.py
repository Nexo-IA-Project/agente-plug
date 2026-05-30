from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from interface.http.deps.admin_auth import AdminAuth, require_admin_role
from shared.adapters.db.repositories.platform_config_repo import PlatformConfigRepository
from shared.adapters.db.session import session_scope
from shared.adapters.email.smtp_email_service import SmtpEmailService

router = APIRouter(tags=["admin-platform-config"])


def _mask(value: str | None) -> str:
    if not value:
        return ""
    if len(value) < 8:
        return "****"
    return value[:8] + "****"


# ──────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────


class SmtpSettings(BaseModel):
    host: str = Field(min_length=1, max_length=200)
    port: int = Field(ge=1, le=65535)
    use_tls: bool = True
    username: str = Field(min_length=1, max_length=200)
    from_name: str = Field(min_length=1, max_length=100)
    from_email: EmailStr


class SmtpSettingsUpdate(BaseModel):
    host: str = Field(min_length=1, max_length=200)
    port: int = Field(ge=1, le=65535)
    use_tls: bool = True
    username: str = Field(min_length=1, max_length=200)
    password: str | None = None
    from_name: str = Field(min_length=1, max_length=100)
    from_email: EmailStr


class SmtpResponse(BaseModel):
    host: str | None = None
    port: int | None = None
    use_tls: bool = True
    username: str | None = None
    from_name: str | None = None
    from_email: str | None = None
    has_password: bool = False


class PlatformConfigResponse(BaseModel):
    openai_api_key: str
    openai_configured: bool
    smtp: SmtpResponse


class PlatformConfigUpdateRequest(BaseModel):
    openai_api_key: str | None = None
    smtp: SmtpSettingsUpdate | None = None


class TestEmailRequest(BaseModel):
    to: EmailStr


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────


@router.get("/platform-config", response_model=PlatformConfigResponse)
async def get_platform_config(
    auth: AdminAuth = Depends(require_admin_role),
) -> PlatformConfigResponse:
    async with session_scope() as s:
        repo = PlatformConfigRepository(s)
        cfg = await repo.get()
        openai_plain = repo.decrypt(cfg.openai_api_key)
    return PlatformConfigResponse(
        openai_api_key=_mask(openai_plain),
        openai_configured=bool(cfg.openai_api_key),
        smtp=SmtpResponse(
            host=cfg.smtp_host,
            port=cfg.smtp_port,
            use_tls=cfg.smtp_use_tls,
            username=cfg.smtp_username,
            from_name=cfg.smtp_from_name,
            from_email=cfg.smtp_from_email,
            has_password=bool(cfg.smtp_encrypted_password),
        ),
    )


@router.put("/platform-config", response_model=PlatformConfigResponse)
async def update_platform_config(
    body: PlatformConfigUpdateRequest,
    auth: AdminAuth = Depends(require_admin_role),
) -> PlatformConfigResponse:
    async with session_scope() as s:
        repo = PlatformConfigRepository(s)

        fields: dict[str, object] = {}

        # OpenAI: cifra apenas se enviado e não-vazio. "" / None → mantém atual.
        if body.openai_api_key:
            fields["openai_api_key"] = repo.encrypt(body.openai_api_key)

        if body.smtp is not None:
            smtp = body.smtp
            fields["smtp_host"] = smtp.host
            fields["smtp_port"] = smtp.port
            fields["smtp_use_tls"] = smtp.use_tls
            fields["smtp_username"] = smtp.username
            fields["smtp_from_name"] = smtp.from_name
            fields["smtp_from_email"] = smtp.from_email
            # Senha: cifra apenas se enviada e não-vazia. "" / None → mantém atual.
            if smtp.password:
                fields["smtp_encrypted_password"] = repo.encrypt(smtp.password)

        cfg = await repo.upsert(**fields)
        await s.commit()
        openai_plain = repo.decrypt(cfg.openai_api_key)

    return PlatformConfigResponse(
        openai_api_key=_mask(openai_plain),
        openai_configured=bool(cfg.openai_api_key),
        smtp=SmtpResponse(
            host=cfg.smtp_host,
            port=cfg.smtp_port,
            use_tls=cfg.smtp_use_tls,
            username=cfg.smtp_username,
            from_name=cfg.smtp_from_name,
            from_email=cfg.smtp_from_email,
            has_password=bool(cfg.smtp_encrypted_password),
        ),
    )


@router.post("/platform-config/test")
async def test_platform_smtp(
    body: TestEmailRequest,
    auth: AdminAuth = Depends(require_admin_role),
) -> dict[Literal["ok"], bool]:
    async with session_scope() as s:
        svc = SmtpEmailService(repo=PlatformConfigRepository(s))
        try:
            await svc.send_email(
                to=body.to,
                subject="Teste NexoIA",
                body_html="<p>SMTP OK</p>",
            )
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"SMTP test failed: {e}") from e
    return {"ok": True}
