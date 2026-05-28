from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from interface.http.deps.admin_auth import AdminAuth, require_admin_role
from interface.http.deps.admin_deps import AdminDeps, get_admin_deps
from shared.domain.entities.knowledge_document import KnowledgeDocument

router = APIRouter(tags=["admin-documents"])

_BACKGROUND_TASKS: set[asyncio.Task] = set()


class DocumentOut(BaseModel):
    id: str
    filename: str
    mime_type: str
    file_size_bytes: int
    status: str
    chunk_count: int
    tags: list[str]
    created_by: str
    created_at: str
    updated_at: str

    @classmethod
    def from_entity(cls, doc: KnowledgeDocument) -> DocumentOut:
        return cls(
            id=doc.id,
            filename=doc.filename,
            mime_type=doc.mime_type,
            file_size_bytes=doc.file_size_bytes,
            status=doc.status.value,
            chunk_count=doc.chunk_count,
            tags=doc.tags,
            created_by=doc.created_by,
            created_at=doc.created_at.isoformat() if doc.created_at else "",
            updated_at=doc.updated_at.isoformat() if doc.updated_at else "",
        )


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    offset: int = 0,
    limit: int = 20,
    deps: AdminDeps = Depends(get_admin_deps),  # noqa: B008
) -> list[DocumentOut]:
    docs = await deps.listar(account_id=deps.account_id, offset=offset, limit=limit)
    return [DocumentOut.from_entity(d) for d in docs]


@router.post("/documents/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),  # noqa: B008
    tags: str = Form(default=""),
    deps: AdminDeps = Depends(get_admin_deps),  # noqa: B008
) -> dict:
    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    max_bytes = deps.settings.kb_max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds max size of {deps.settings.kb_max_file_size_mb}MB",
        )

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    doc = KnowledgeDocument(
        account_id=deps.account_id,
        filename=file.filename or "unknown",
        mime_type=mime_type,
        file_size_bytes=len(content),
        created_by=deps.user_email,
        tags=tag_list,
    )
    await deps.doc_repo.save(doc)

    task = asyncio.create_task(
        deps.ingerir(doc_id=doc.id, content=content, account_id=deps.account_id)
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    return {"doc_id": doc.id, "status": "processing"}


@router.get("/documents/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: str,
    deps: AdminDeps = Depends(get_admin_deps),  # noqa: B008
) -> DocumentOut:
    doc = await deps.doc_repo.get(doc_id, deps.account_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentOut.from_entity(doc)


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str,
    deps: AdminDeps = Depends(get_admin_deps),  # noqa: B008
    _auth: AdminAuth = Depends(require_admin_role),  # noqa: B008
) -> None:
    await deps.deletar(doc_id=doc_id, account_id=deps.account_id)


@router.post("/documents/{doc_id}/reindex", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def reindex_document(
    doc_id: str,
    deps: AdminDeps = Depends(get_admin_deps),  # noqa: B008
) -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Reindex requires re-upload. Use /documents/upload.",
    )
