# apps/api/src/interface/http/routers/admin/settings.py
from __future__ import annotations

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, status

from interface.http.deps.admin_auth import AdminAuth
from interface.http.deps.permissions import require_permission
from interface.http.schemas.admin_settings import (
    AccountSettingsResponse,
    AccountSettingsUpdateRequest,
)
from shared.adapters.db.repositories.account_config_repo import (
    AccountConfigRepository,
    _mask,
)
from shared.adapters.db.session import session_scope
from shared.application.use_cases.admin.get_account_config import GetAccountConfig
from shared.application.use_cases.admin.update_account_config import UpdateAccountConfig
from shared.config.settings import get_settings
from shared.config.single_tenant import get_default_account_uuid
from shared.domain.entities.account_config import (
    AccountConfig,
    AccountConfigPatch,
)

router = APIRouter(tags=["admin-settings"])


def _to_response(config: AccountConfig) -> AccountSettingsResponse:
    i = config.integration
    b = config.behavior
    mb = config.message_buffer
    return AccountSettingsResponse(
        chatnexo_base_url=i.chatnexo_base_url,
        chatnexo_api_key=_mask(i.chatnexo_api_key),
        chatnexo_account_id=i.chatnexo_account_id,
        chatnexo_inbox_id=i.chatnexo_inbox_id,
        hubla_webhook_secret=_mask(i.hubla_webhook_secret),
        meta_api_key=_mask(i.meta_api_key),
        meta_waba_id=i.meta_waba_id,
        meta_app_id=i.meta_app_id,
        alert_whatsapp_target=i.alert_whatsapp_target,
        idle_ping_minutes=b.idle_ping_minutes,
        idle_close_minutes=b.idle_close_minutes,
        intent_confidence_threshold=b.intent_confidence_threshold,
        message_buffer_wait_seconds=b.message_buffer_wait_seconds,
        refund_deadline_days=b.refund_deadline_days,
        welcome_d1_delay_hours=b.welcome_d1_delay_hours,
        ai_memory_messages=b.ai_memory_messages,
        message_buffer_enabled=mb.enabled,
        message_buffer_outgoing_url=mb.outgoing_url,
        message_buffer_api_key=_mask(mb.api_key or ""),
        message_buffer_tenant_id=mb.tenant_id,
    )


@router.get("/settings", response_model=AccountSettingsResponse)
async def get_settings_endpoint(
    auth: AdminAuth = Depends(require_permission("settings.view")),
) -> AccountSettingsResponse:
    s = get_settings()
    fernet = Fernet(s.integration_credentials_key.encode())
    async with session_scope() as session:
        account_id = auth.account_id or await get_default_account_uuid(session)
        repo = AccountConfigRepository(session=session, fernet=fernet)
        uc = GetAccountConfig(repo=repo)
        config = await uc.execute(account_id=account_id)
    return _to_response(config)


@router.get("/settings/hubla-webhook-token")
async def get_hubla_webhook_token(
    auth: AdminAuth = Depends(require_permission("settings.view")),
) -> dict[str, str]:
    """Retorna o secret real (não mascarado) usado pra autenticar webhooks da Hubla.

    Usado pelo card de configuração no painel pra montar a URL completa
    com ?token=... que o operador cola na Hubla.
    """
    s = get_settings()
    fernet = Fernet(s.integration_credentials_key.encode())
    async with session_scope() as session:
        account_id = auth.account_id or await get_default_account_uuid(session)
        repo = AccountConfigRepository(session=session, fernet=fernet)
        config = await repo.get(account_id=account_id)
    return {"token": config.integration.hubla_webhook_secret or ""}


@router.put("/settings", response_model=AccountSettingsResponse)
async def update_settings_endpoint(
    body: AccountSettingsUpdateRequest,
    auth: AdminAuth = Depends(require_permission("settings.edit_credentials")),
) -> AccountSettingsResponse:
    s = get_settings()
    fernet = Fernet(s.integration_credentials_key.encode())
    patch = AccountConfigPatch(
        chatnexo_base_url=body.chatnexo_base_url,
        chatnexo_api_key=body.chatnexo_api_key,
        chatnexo_account_id=body.chatnexo_account_id,
        chatnexo_inbox_id=body.chatnexo_inbox_id,
        hubla_webhook_secret=body.hubla_webhook_secret,
        meta_api_key=body.meta_api_key,
        meta_waba_id=body.meta_waba_id,
        meta_app_id=body.meta_app_id,
        alert_whatsapp_target=body.alert_whatsapp_target,
        idle_ping_minutes=body.idle_ping_minutes,
        idle_close_minutes=body.idle_close_minutes,
        intent_confidence_threshold=body.intent_confidence_threshold,
        message_buffer_wait_seconds=body.message_buffer_wait_seconds,
        refund_deadline_days=body.refund_deadline_days,
        welcome_d1_delay_hours=body.welcome_d1_delay_hours,
        ai_memory_messages=body.ai_memory_messages,
        message_buffer_enabled=body.message_buffer_enabled,
        message_buffer_outgoing_url=body.message_buffer_outgoing_url,
        message_buffer_api_key=body.message_buffer_api_key,
        message_buffer_tenant_id=body.message_buffer_tenant_id,
    )
    try:
        async with session_scope() as session:
            account_id = auth.account_id or await get_default_account_uuid(session)
            repo = AccountConfigRepository(session=session, fernet=fernet)
            uc = UpdateAccountConfig(repo=repo)
            config = await uc.execute(account_id=account_id, patch=patch)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return _to_response(config)
