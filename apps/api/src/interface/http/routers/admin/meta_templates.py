from __future__ import annotations

from typing import Annotated
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from interface.http.deps.admin_auth import AdminAuth, require_admin
from interface.http.schemas.meta_templates import (
    CreateTemplateRequest,
    MetaTemplateResponse,
    UploadMediaResponse,
)
from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository
from shared.adapters.db.session import session_scope
from shared.adapters.meta.template_client import MetaTemplateClient
from shared.adapters.storage.r2 import R2Storage
from shared.application.use_cases.meta_templates.create_template import (
    CreateTemplate,
    CreateTemplateInput,
)
from shared.application.use_cases.meta_templates.delete_template import (
    DeleteTemplate,
    MetaTemplateInUse,
)
from shared.application.use_cases.meta_templates.list_templates import ListTemplates
from shared.application.use_cases.meta_templates.upload_template_media import (
    UploadTemplateMedia,
    UploadTemplateMediaInput,
)
from shared.config.settings import get_settings

router = APIRouter(tags=["admin-meta-templates"])


def _to_response(model) -> MetaTemplateResponse:
    return MetaTemplateResponse(
        id=model.id,
        name=model.name,
        category=model.category,
        language=model.language,
        status=model.status,
        components=model.components or [],
        media_url=model.media_url,
        media_kind=model.media_kind,
        rejection_reason=model.rejection_reason,
        meta_template_id=model.meta_template_id,
        created_at=model.created_at,
    )


async def _get_meta_client_and_waba(auth: AdminAuth) -> tuple[MetaTemplateClient, str]:
    settings = get_settings()
    fernet = Fernet(settings.integration_credentials_key.encode())
    async with session_scope() as session:
        repo = AccountConfigRepository(session=session, fernet=fernet)
        config = await repo.get(account_id=auth.account_id)
    client = MetaTemplateClient.from_account_config(config)
    waba_id = config.integration.meta_waba_id or settings.meta_waba_id or ""
    return client, waba_id


async def _flow_usage_check(account_id: UUID, template_name: str) -> list[dict]:
    """Retorna lista de flows que usam o template (id, name, step_position)."""
    from sqlalchemy import select

    from shared.adapters.db.models import FollowupFlowModel, FollowupStepModel

    async with session_scope() as session:
        result = await session.execute(
            select(
                FollowupFlowModel.id,
                FollowupFlowModel.name,
                FollowupStepModel.position,
            )
            .join(FollowupStepModel, FollowupStepModel.flow_id == FollowupFlowModel.id)
            .where(FollowupFlowModel.account_id == account_id)
            .where(FollowupStepModel.meta_template_name == template_name)
        )
        return [
            {"id": str(row.id), "name": row.name, "step_position": row.position}
            for row in result.all()
        ]


@router.post(
    "/meta-templates/upload-media",
    response_model=UploadMediaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_media(
    file: Annotated[UploadFile, File()],
    kind: Annotated[str, Form()],
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> UploadMediaResponse:
    if kind not in {"IMAGE", "VIDEO", "DOCUMENT"}:
        raise HTTPException(
            status_code=422, detail={"code": "MEDIA_KIND_INVALID"}
        )
    data = await file.read()
    storage = R2Storage.from_settings(get_settings())
    use_case = UploadTemplateMedia(storage=storage)
    try:
        out = await use_case.execute(UploadTemplateMediaInput(
            account_id=auth.account_id,
            kind=kind,  # type: ignore[arg-type]
            data=data,
            mime=file.content_type or "application/octet-stream",
            original_filename=file.filename or "upload",
        ))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from exc
    return UploadMediaResponse(
        media_url=out.media_url,
        media_object_key=out.media_object_key,
        media_kind=out.media_kind,
        sha256=out.sha256,
        size=out.size,
    )


@router.post(
    "/meta-templates",
    response_model=MetaTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    body: CreateTemplateRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> MetaTemplateResponse:
    client, waba_id = await _get_meta_client_and_waba(auth)
    if not waba_id:
        raise HTTPException(status_code=422, detail="META_WABA_ID não configurado")
    settings = get_settings()
    if not settings.meta_app_id:
        raise HTTPException(status_code=422, detail="META_APP_ID não configurado")

    storage = R2Storage.from_settings(settings)
    async with session_scope() as session:
        repo = MetaTemplateRepository(session=session)
        use_case = CreateTemplate(repo=repo, meta_client=client, storage=storage)
        try:
            record = await use_case.execute(CreateTemplateInput(
                account_id=auth.account_id,
                waba_id=waba_id,
                app_id=settings.meta_app_id,
                name=body.name,
                category=body.category,
                language=body.language,
                components=body.components,
                media_url=body.media_url,
                media_object_key=body.media_object_key,
                media_kind=body.media_kind,
            ))
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "META_TEMPLATE_VALIDATION_FAILED", "detail": str(exc)},
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail={"code": "META_API_ERROR", "detail": str(exc)},
            ) from exc

        return _to_response(record)


@router.get("/meta-templates", response_model=list[MetaTemplateResponse])
async def list_templates(
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> list[MetaTemplateResponse]:
    client, waba_id = await _get_meta_client_and_waba(auth)
    async with session_scope() as session:
        repo = MetaTemplateRepository(session=session)
        records = await ListTemplates(repo=repo, meta_client=client).execute(
            account_id=auth.account_id, waba_id=waba_id,
        )
    return [_to_response(r) for r in records]


@router.delete("/meta-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    client, waba_id = await _get_meta_client_and_waba(auth)
    storage = R2Storage.from_settings(get_settings())
    async with session_scope() as session:
        repo = MetaTemplateRepository(session=session)
        use_case = DeleteTemplate(
            repo=repo, meta_client=client, storage=storage,
            flow_usage_check=_flow_usage_check,
        )
        try:
            await use_case.execute(
                account_id=auth.account_id, template_id=template_id, waba_id=waba_id,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="META_TEMPLATE_NOT_FOUND") from exc
        except MetaTemplateInUse as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "META_TEMPLATE_IN_USE", "flows": exc.flows},
            ) from exc
