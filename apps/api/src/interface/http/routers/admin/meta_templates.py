from __future__ import annotations

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, status

from interface.http.deps.admin_auth import AdminAuth, require_admin
from interface.http.schemas.meta_templates import (
    CreateTemplateRequest,
    MetaTemplateResponse,
    TemplateComponentResponse,
)
from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
from shared.adapters.db.session import session_scope
from shared.adapters.meta.template_client import MetaTemplateClient
from shared.config.settings import get_settings

router = APIRouter(tags=["admin-meta-templates"])


def _to_response(t) -> MetaTemplateResponse:
    return MetaTemplateResponse(
        id=t.id,
        name=t.name,
        category=t.category,
        language=t.language,
        status=t.status,
        components=[
            TemplateComponentResponse(
                type=c.type,
                format=c.format,
                text=c.text,
                buttons=c.buttons,
            )
            for c in t.components
        ],
        rejection_reason=t.rejection_reason,
    )


async def _get_client(auth: AdminAuth) -> tuple[MetaTemplateClient, str]:
    settings = get_settings()
    fernet = Fernet(settings.integration_credentials_key.encode())
    async with session_scope() as session:
        repo = AccountConfigRepository(session=session, fernet=fernet)
        config = await repo.get(account_id=auth.account_id)
    client = MetaTemplateClient.from_account_config(config)
    waba_id = config.integration.meta_waba_id or settings.meta_waba_id
    return client, waba_id


@router.get("/meta-templates", response_model=list[MetaTemplateResponse])
async def list_templates(
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> list[MetaTemplateResponse]:
    client, waba_id = await _get_client(auth)
    if not waba_id:
        return []
    try:
        templates = await client.list_templates(waba_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erro ao buscar templates da Meta: {exc}",
        ) from exc
    return [_to_response(t) for t in templates]


@router.post(
    "/meta-templates",
    response_model=MetaTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    body: CreateTemplateRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> MetaTemplateResponse:
    from shared.domain.ports.meta_template import CreateTemplatePayload

    client, waba_id = await _get_client(auth)
    if not waba_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="META_WABA_ID não configurado em Settings",
        )
    payload = CreateTemplatePayload(
        name=body.name,
        category=body.category,
        language=body.language,
        components=body.components,
    )
    try:
        template = await client.create_template(waba_id, payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Erro ao criar template na Meta: {exc}",
        ) from exc
    return _to_response(template)
