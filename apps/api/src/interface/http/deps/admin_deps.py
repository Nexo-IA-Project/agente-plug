from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from fastapi import Header, HTTPException, status
from jose import JWTError
from openai import AsyncOpenAI

from nexoia.application.use_cases.kb.buscar_chunks import BuscarChunks
from nexoia.application.use_cases.kb.deletar_documento import DeletarDocumento
from nexoia.application.use_cases.kb.ingerir_documento import IngerirDocumento
from nexoia.application.use_cases.kb.listar_documentos import ListarDocumentos
from nexoia.config.settings import Settings, get_settings
from nexoia.infrastructure.db.repositories.chunk_repo import ChunkRepository
from nexoia.infrastructure.db.repositories.document_repo import DocumentRepository
from nexoia.infrastructure.db.repositories.usage_log_repo import UsageLogRepository
from nexoia.infrastructure.db.session import session_scope
from nexoia.infrastructure.kb.chunker import TextChunker
from nexoia.infrastructure.kb.jwt_handler import verify_token
from nexoia.infrastructure.kb.openai_embeddings import OpenAIEmbeddingsAdapter
from nexoia.infrastructure.kb.text_extractor import TextExtractor


@dataclass
class AdminDeps:
    account_id: int
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
) -> AsyncIterator[AdminDeps]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = verify_token(token, secret=settings.jwt_secret)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    account_id: int = payload["account_id"]
    user_email: str = payload["sub"]
    user_role: str = payload.get("role", "viewer")

    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    embeddings = OpenAIEmbeddingsAdapter(openai_client, model=settings.kb_embedding_model)
    extractor = TextExtractor()
    chunker = TextChunker(
        chunk_size=settings.kb_chunk_size,
        overlap=settings.kb_chunk_overlap,
    )

    async with session_scope() as session:
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
