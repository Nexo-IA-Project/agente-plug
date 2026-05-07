# apps/api/src/interface/http/routers/admin/settings.py
from __future__ import annotations

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, status

from interface.http.deps.admin_auth import AdminAuth, require_admin
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
from shared.domain.entities.account_config import AccountConfig, AccountConfigPatch

router = APIRouter(tags=["admin-settings"])


def _to_response(config: AccountConfig) -> AccountSettingsResponse:
    i = config.integration
    b = config.behavior
    return AccountSettingsResponse(
        chatnexo_base_url=i.chatnexo_base_url,
        chatnexo_api_key=_mask(i.chatnexo_api_key),
        hubla_webhook_secret=_mask(i.hubla_webhook_secret),
        cademi_api_url=i.cademi_api_url,
        cademi_api_key=_mask(i.cademi_api_key),
        cademi_max_retries=i.cademi_max_retries,
        cademi_retry_base_seconds=i.cademi_retry_base_seconds,
        openai_api_key=_mask(i.openai_api_key),
        meta_api_key=_mask(i.meta_api_key),
        idle_ping_minutes=b.idle_ping_minutes,
        idle_close_minutes=b.idle_close_minutes,
        intent_confidence_threshold=b.intent_confidence_threshold,
        message_buffer_wait_seconds=b.message_buffer_wait_seconds,
        refund_deadline_days=b.refund_deadline_days,
        welcome_d1_delay_hours=b.welcome_d1_delay_hours,
        loja_express_d1_delay_hours=b.loja_express_d1_delay_hours,
        loja_express_d3_delay_hours=b.loja_express_d3_delay_hours,
        loja_express_d5_delay_hours=b.loja_express_d5_delay_hours,
        loja_express_d7_delay_hours=b.loja_express_d7_delay_hours,
    )


@router.get("/settings", response_model=AccountSettingsResponse)
async def get_settings_endpoint(
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> AccountSettingsResponse:
    s = get_settings()
    fernet = Fernet(s.integration_credentials_key.encode())
    async with session_scope() as session:
        repo = AccountConfigRepository(session=session, fernet=fernet)
        uc = GetAccountConfig(repo=repo)
        config = await uc.execute(account_id=auth.account_id)
    return _to_response(config)


@router.put("/settings", response_model=AccountSettingsResponse)
async def update_settings_endpoint(
    body: AccountSettingsUpdateRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> AccountSettingsResponse:
    s = get_settings()
    fernet = Fernet(s.integration_credentials_key.encode())
    patch = AccountConfigPatch(
        chatnexo_base_url=body.chatnexo_base_url,
        chatnexo_api_key=body.chatnexo_api_key,
        hubla_webhook_secret=body.hubla_webhook_secret,
        cademi_api_url=body.cademi_api_url,
        cademi_api_key=body.cademi_api_key,
        cademi_max_retries=body.cademi_max_retries,
        cademi_retry_base_seconds=body.cademi_retry_base_seconds,
        openai_api_key=body.openai_api_key,
        meta_api_key=body.meta_api_key,
        idle_ping_minutes=body.idle_ping_minutes,
        idle_close_minutes=body.idle_close_minutes,
        intent_confidence_threshold=body.intent_confidence_threshold,
        message_buffer_wait_seconds=body.message_buffer_wait_seconds,
        refund_deadline_days=body.refund_deadline_days,
        welcome_d1_delay_hours=body.welcome_d1_delay_hours,
        loja_express_d1_delay_hours=body.loja_express_d1_delay_hours,
        loja_express_d3_delay_hours=body.loja_express_d3_delay_hours,
        loja_express_d5_delay_hours=body.loja_express_d5_delay_hours,
        loja_express_d7_delay_hours=body.loja_express_d7_delay_hours,
    )
    try:
        async with session_scope() as session:
            repo = AccountConfigRepository(session=session, fernet=fernet)
            uc = UpdateAccountConfig(repo=repo)
            config = await uc.execute(account_id=auth.account_id, patch=patch)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return _to_response(config)
