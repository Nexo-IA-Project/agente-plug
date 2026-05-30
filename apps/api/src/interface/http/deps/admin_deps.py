from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import Cookie, Header, HTTPException, status
from jose import JWTError
from openai import AsyncOpenAI

from shared.adapters.db.repositories.chunk_repo import ChunkRepository
from shared.adapters.db.repositories.document_repo import DocumentRepository
from shared.adapters.db.repositories.usage_log_repo import UsageLogRepository
from shared.adapters.db.session import session_scope
from shared.adapters.kb.chunker import TextChunker
from shared.adapters.kb.jwt_handler import verify_token
from shared.adapters.kb.openai_embeddings import OpenAIEmbeddingsAdapter
from shared.adapters.kb.text_extractor import TextExtractor
from shared.application.resolve_openai_key import resolve_openai_key
from shared.application.use_cases.kb.buscar_chunks import BuscarChunks
from shared.application.use_cases.kb.deletar_documento import DeletarDocumento
from shared.application.use_cases.kb.ingerir_documento import IngerirDocumento
from shared.application.use_cases.kb.listar_documentos import ListarDocumentos
from shared.config.settings import Settings, get_settings
from shared.config.single_tenant import get_default_account_uuid


@dataclass
class AdminDeps:
    account_id: UUID
    user_email: str
    user_role: str
    settings: Settings
    doc_repo: DocumentRepository
    ingerir: Callable
    listar: Callable
    deletar: Callable
    buscar: Callable


async def get_admin_deps(
    authorization: str | None = Header(default=None),
    nexoia_token: str | None = Cookie(default=None),
) -> AsyncIterator[AdminDeps]:
    token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif nexoia_token:
        token = nexoia_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()

    try:
        payload = verify_token(token, secret=settings.jwt_secret)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # account_id agora é UUID. Tokens legados carregavam inteiro — parse tolerante,
    # com fallback resolvido dentro da sessão (single-tenant).
    raw_acc = payload.get("account_id")
    try:
        token_account_id: UUID | None = UUID(str(raw_acc)) if raw_acc is not None else None
    except (ValueError, TypeError):
        token_account_id = None
    user_email: str = payload["sub"]
    user_role: str = payload.get("role", "viewer")

    extractor = TextExtractor()
    chunker = TextChunker(
        chunk_size=settings.kb_chunk_size,
        overlap=settings.kb_chunk_overlap,
    )

    async with session_scope() as session:
        openai_client = AsyncOpenAI(api_key=await resolve_openai_key(session))
        embeddings = OpenAIEmbeddingsAdapter(openai_client, model=settings.kb_embedding_model)
        account_id = token_account_id or await get_default_account_uuid(session)
        doc_repo = DocumentRepository(session)
        chunk_repo = ChunkRepository(session)
        usage_repo = UsageLogRepository(session)

        ingerir_uc = IngerirDocumento(
            doc_repo=doc_repo,
            chunk_repo=chunk_repo,
            extractor=extractor,
            chunker=chunker,
            embeddings=embeddings,
        )
        listar_uc = ListarDocumentos(doc_repo=doc_repo)
        deletar_uc = DeletarDocumento(doc_repo=doc_repo, chunk_repo=chunk_repo)
        buscar_uc = BuscarChunks(
            chunk_repo=chunk_repo,
            embeddings=embeddings,
            usage_repo=usage_repo,
        )

        yield AdminDeps(
            account_id=account_id,
            user_email=user_email,
            user_role=user_role,
            settings=settings,
            doc_repo=doc_repo,
            ingerir=ingerir_uc.execute,
            listar=listar_uc.execute,
            deletar=deletar_uc.execute,
            buscar=buscar_uc.execute,
        )
