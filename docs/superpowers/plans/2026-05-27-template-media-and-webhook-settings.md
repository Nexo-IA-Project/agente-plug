# Template Media in Postgres + Webhook URL in /settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o storage R2 externo por BYTEA no Postgres (com endpoint público pra servir), adicionar preview de mídia inline no `/onboarding`, e mostrar URL+instruções do webhook Hubla na `/settings`.

**Architecture:** 3 fases. Fase 1 backend: tabela `meta_template_media` (BYTEA + dedup sha256), endpoint `POST /admin/meta-templates/upload-media` refatorado, endpoint público `GET /public/media/{id}`, remoção do adapter R2 + StoragePort. Fase 2 frontend onboarding: hook + `TemplatePreview` (bolha WhatsApp inline) + thumbnail no `StepItem`. Fase 3 settings: card webhook URL+instruções.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, Next.js 15, Tailwind, hashlib, pytest.

**Spec:** `docs/superpowers/specs/2026-05-27-template-media-and-webhook-settings-design.md`

**Branch:** `feat/step-sequence-and-media` (mesma branch da Spec A já implementada — abre **1 PR único** após Task 16).

---

## Fase 1 — Backend: storage no Postgres + endpoint público

### Task 1: Settings — adicionar `public_base_url`

**Files:**
- Modify: `apps/api/src/shared/config/settings.py`
- Modify: `apps/api/.env.example`
- Modify: `/home/fabio/www/agente-plug/.env.local` (apenas se for dev local — pular se não tiver acesso)

- [ ] **Step 1: Adicionar `public_base_url` em `Settings`**

Localizar a classe `Settings` em `apps/api/src/shared/config/settings.py` e adicionar o campo (próximo a outras URLs/configs públicas):

```python
public_base_url: str = "http://localhost:8000"
```

Default `http://localhost:8000` permite dev sem `.env.local` configurado.

- [ ] **Step 2: Adicionar a chave em `.env.example`**

Procurar onde estão as variáveis tipo `CHATNEXO_BASE_URL`/`META_*` em `apps/api/.env.example` e adicionar (mesmo bloco):

```
PUBLIC_BASE_URL=
```

- [ ] **Step 3: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/api/src/shared/config/settings.py apps/api/.env.example
git commit -m "feat(config): adiciona PUBLIC_BASE_URL para o endpoint público de mídia"
```

> O usuário vai colocar o valor real em `.env.local` (dev: `https://api-flow-dev.ianexo.com.br`; prod: `https://api-flow.ianexo.com.br`). Não é responsabilidade desta task.

---

### Task 2: Modelo SQLAlchemy `MetaTemplateMediaModel` + migration Alembic

**Files:**
- Modify: `apps/api/src/shared/adapters/db/models.py`
- Create: `apps/api/migrations/versions/<rev>_meta_template_media_table.py`

- [ ] **Step 1: Adicionar `MetaTemplateMediaModel` em `models.py`**

No final do arquivo (após o último model existente), inserir:

```python
class MetaTemplateMediaModel(Base):
    """Storage de bytes de mídia (imagem/vídeo/documento) usada em templates Meta.

    BYTEA + dedup por sha256. Servido publicamente via GET /public/media/{id}.
    """

    __tablename__ = "meta_template_media"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    mime: Mapped[str] = mapped_column(String(128), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        UniqueConstraint("account_id", "sha256", name="uq_meta_template_media_account_sha"),
        CheckConstraint(
            "kind IN ('IMAGE', 'VIDEO', 'DOCUMENT')",
            name="ck_meta_template_media_kind",
        ),
    )
```

Garantir que `LargeBinary`, `UniqueConstraint`, `CheckConstraint`, `String`, `Integer`, `DateTime`, `ForeignKey`, `Mapped`, `mapped_column`, `UUID`, `datetime`, `UTC`, `uuid` estão importados no topo do arquivo (alguns já estão; adicionar `LargeBinary`, `CheckConstraint` se ausentes).

- [ ] **Step 2: Gerar revision Alembic**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run alembic revision -m "meta template media table"
```

Anotar o `<rev>` gerado e confirmar `down_revision` aponta pro head atual:

```bash
uv run alembic heads
```

(Esperado: `9f07c98d5b22` — head da Spec A.)

- [ ] **Step 3: Implementar `upgrade()` e `downgrade()` no revision file**

Editar o arquivo gerado em `apps/api/migrations/versions/<rev>_meta_template_media_table.py`:

```python
"""meta template media table

Revision ID: <rev>
Revises: 9f07c98d5b22
Create Date: 2026-05-27

Cria tabela meta_template_media (BYTEA + dedup por sha256) para armazenar
mídia de templates Meta no nosso Postgres em vez de R2 externo.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "<rev>"
down_revision = "9f07c98d5b22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meta_template_media",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "account_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("mime", sa.String(128), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "account_id", "sha256", name="uq_meta_template_media_account_sha"
        ),
        sa.CheckConstraint(
            "kind IN ('IMAGE', 'VIDEO', 'DOCUMENT')",
            name="ck_meta_template_media_kind",
        ),
    )


def downgrade() -> None:
    op.drop_table("meta_template_media")
```

Substituir `<rev>` pelo valor real gerado.

- [ ] **Step 4: Rodar migration localmente**

```bash
cd /home/fabio/www/agente-plug && docker compose up -d postgres 2>&1 | tail -2
cd /home/fabio/www/agente-plug/apps/api && uv run alembic upgrade heads
```

Esperado: sem erro, com log da revision nova.

- [ ] **Step 5: Validar tabela criada**

```bash
docker compose exec -T postgres psql -U postgres -d agente_plug -c "
  \d meta_template_media
" 2>&1 | tail -20
```

Se o banco local for outro nome, ajustar. Confirmar colunas + constraint unique + check.

- [ ] **Step 6: Downgrade + re-upgrade (idempotência básica)**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run alembic downgrade -1
cd /home/fabio/www/agente-plug/apps/api && uv run alembic upgrade heads
```

- [ ] **Step 7: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/api/src/shared/adapters/db/models.py apps/api/migrations/versions/
git commit -m "feat(meta-media): tabela meta_template_media (BYTEA + dedup sha256)"
```

---

### Task 3: Repository `MetaTemplateMediaRepository`

**Files:**
- Create: `apps/api/src/shared/adapters/db/repositories/meta_template_media_repo.py`
- Test: `apps/api/tests/unit/meta_templates/test_meta_template_media_repo.py`

- [ ] **Step 1: Criar teste falhando**

```python
# apps/api/tests/unit/meta_templates/test_meta_template_media_repo.py
"""Testes do MetaTemplateMediaRepository (insert + get_by_id + get_by_sha + dedup)."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.repositories.meta_template_media_repo import (
    MetaTemplateMediaRepository,
)


@pytest.mark.asyncio
async def test_insert_and_get_by_id(test_session: AsyncSession, seed_account_uuid) -> None:
    repo = MetaTemplateMediaRepository(session=test_session)
    record = await repo.insert(
        account_id=seed_account_uuid,
        kind="IMAGE",
        mime="image/png",
        sha256="a" * 64,
        size_bytes=1024,
        data=b"\x89PNG\r\n\x1a\n",
        original_filename="hello.png",
    )
    assert record.id is not None
    fetched = await repo.get_by_id(record.id)
    assert fetched is not None
    assert fetched.kind == "IMAGE"
    assert fetched.mime == "image/png"
    assert fetched.sha256 == "a" * 64
    assert fetched.size_bytes == 1024


@pytest.mark.asyncio
async def test_get_by_sha_returns_existing(test_session: AsyncSession, seed_account_uuid) -> None:
    repo = MetaTemplateMediaRepository(session=test_session)
    await repo.insert(
        account_id=seed_account_uuid,
        kind="IMAGE",
        mime="image/png",
        sha256="b" * 64,
        size_bytes=10,
        data=b"x" * 10,
        original_filename=None,
    )
    found = await repo.get_by_sha(account_id=seed_account_uuid, sha256="b" * 64)
    assert found is not None
    assert found.sha256 == "b" * 64


@pytest.mark.asyncio
async def test_get_by_sha_returns_none_when_missing(test_session, seed_account_uuid) -> None:
    repo = MetaTemplateMediaRepository(session=test_session)
    found = await repo.get_by_sha(account_id=seed_account_uuid, sha256="c" * 64)
    assert found is None


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_missing(test_session) -> None:
    from uuid import uuid4
    repo = MetaTemplateMediaRepository(session=test_session)
    found = await repo.get_by_id(uuid4())
    assert found is None
```

> Nota sobre fixtures: se `test_session` e `seed_account_uuid` não existirem no projeto, este teste vira **integration test** que requer postgres. Verifique antes:
> ```bash
> grep -rn "test_session\|seed_account_uuid" apps/api/tests/conftest.py 2>/dev/null | head -5
> ```
> Se não houver, **pular Steps 1-2** e ir direto pro Step 3 (implementação sem testes automatizados — vai ser validado via integration na Task 5).

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run pytest tests/unit/meta_templates/test_meta_template_media_repo.py -v 2>&1 | tail -10
```

Esperado: `ModuleNotFoundError` no import do repo.

- [ ] **Step 3: Implementar o repository**

```python
# apps/api/src/shared/adapters/db/repositories/meta_template_media_repo.py
"""Repository para meta_template_media — storage de mídia de template no Postgres."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import MetaTemplateMediaModel


class MetaTemplateMediaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, media_id: UUID) -> MetaTemplateMediaModel | None:
        result = await self._session.execute(
            select(MetaTemplateMediaModel).where(MetaTemplateMediaModel.id == media_id)
        )
        return result.scalar_one_or_none()

    async def get_by_sha(
        self, *, account_id: UUID, sha256: str
    ) -> MetaTemplateMediaModel | None:
        result = await self._session.execute(
            select(MetaTemplateMediaModel)
            .where(MetaTemplateMediaModel.account_id == account_id)
            .where(MetaTemplateMediaModel.sha256 == sha256)
        )
        return result.scalar_one_or_none()

    async def insert(
        self,
        *,
        account_id: UUID,
        kind: str,
        mime: str,
        sha256: str,
        size_bytes: int,
        data: bytes,
        original_filename: str | None,
    ) -> MetaTemplateMediaModel:
        model = MetaTemplateMediaModel(
            account_id=account_id,
            kind=kind,
            mime=mime,
            sha256=sha256,
            size_bytes=size_bytes,
            data=data,
            original_filename=original_filename,
        )
        self._session.add(model)
        await self._session.flush()
        return model
```

- [ ] **Step 4: Rodar testes (se houver fixture)**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run pytest tests/unit/meta_templates/test_meta_template_media_repo.py -v 2>&1 | tail -10
```

Esperado: 4 passed (ou skip se fixture ausente).

- [ ] **Step 5: Lint**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run ruff check src/shared/adapters/db/repositories/meta_template_media_repo.py
```

- [ ] **Step 6: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/api/src/shared/adapters/db/repositories/meta_template_media_repo.py apps/api/tests/unit/meta_templates/test_meta_template_media_repo.py
git commit -m "feat(meta-media): MetaTemplateMediaRepository (insert + get_by_id + get_by_sha)"
```

---

### Task 4: Use case `UploadTemplateMedia` (refactor pra Postgres)

**Files:**
- Modify: `apps/api/src/shared/application/use_cases/meta_templates/upload_template_media.py`
- Test: `apps/api/tests/unit/meta_templates/test_upload_template_media.py` (substitui o existente)

- [ ] **Step 1: Ler o estado atual**

```bash
cat /home/fabio/www/agente-plug/apps/api/src/shared/application/use_cases/meta_templates/upload_template_media.py
```

Identificar a interface atual (`UploadTemplateMediaInput`, `UploadTemplateMediaOutput`) e a chamada a `StoragePort`.

- [ ] **Step 2: Substituir o conteúdo do arquivo por:**

```python
# apps/api/src/shared/application/use_cases/meta_templates/upload_template_media.py
"""Use case: upload de mídia de template — agora salva no Postgres (BYTEA) com dedup por sha256."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

# Limites de tamanho por kind (em bytes)
_SIZE_LIMITS: dict[str, int] = {
    "IMAGE": 5 * 1024 * 1024,        # 5 MB
    "VIDEO": 16 * 1024 * 1024,       # 16 MB
    "DOCUMENT": 16 * 1024 * 1024,    # 16 MB
}


class MediaTooLargeError(Exception):
    """Lançado quando o arquivo excede o limite do `kind`."""

    def __init__(self, kind: str, size: int, limit: int) -> None:
        super().__init__(
            f"{kind} de {size} bytes excede o limite de {limit} bytes"
        )
        self.kind = kind
        self.size = size
        self.limit = limit


@dataclass
class UploadTemplateMediaInput:
    account_id: UUID
    kind: Literal["IMAGE", "VIDEO", "DOCUMENT"]
    data: bytes
    mime: str
    original_filename: str


@dataclass
class UploadTemplateMediaOutput:
    media_id: UUID
    media_url: str
    media_object_key: str  # = str(media_id) — compat com a interface anterior do schema HTTP
    media_kind: str
    sha256: str
    size: int


class UploadTemplateMedia:
    """Salva mídia no Postgres (dedup por sha256) e retorna URL pública servida pelo nosso endpoint."""

    def __init__(self, *, repo: Any, public_base_url: str) -> None:
        self._repo = repo
        self._public_base_url = public_base_url.rstrip("/")

    async def execute(
        self, input_: UploadTemplateMediaInput
    ) -> UploadTemplateMediaOutput:
        limit = _SIZE_LIMITS[input_.kind]
        if len(input_.data) > limit:
            raise MediaTooLargeError(input_.kind, len(input_.data), limit)

        sha256 = hashlib.sha256(input_.data).hexdigest()
        existing = await self._repo.get_by_sha(
            account_id=input_.account_id, sha256=sha256
        )
        if existing is not None:
            return self._to_output(existing)

        record = await self._repo.insert(
            account_id=input_.account_id,
            kind=input_.kind,
            mime=input_.mime,
            sha256=sha256,
            size_bytes=len(input_.data),
            data=input_.data,
            original_filename=input_.original_filename,
        )
        return self._to_output(record)

    def _to_output(self, record: Any) -> UploadTemplateMediaOutput:
        return UploadTemplateMediaOutput(
            media_id=record.id,
            media_url=f"{self._public_base_url}/public/media/{record.id}",
            media_object_key=str(record.id),
            media_kind=record.kind,
            sha256=record.sha256,
            size=record.size_bytes,
        )
```

- [ ] **Step 3: Substituir o teste**

`apps/api/tests/unit/meta_templates/test_upload_template_media.py`:

```python
"""Testes do UploadTemplateMedia use case (Postgres + dedup)."""
from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.application.use_cases.meta_templates.upload_template_media import (
    MediaTooLargeError,
    UploadTemplateMedia,
    UploadTemplateMediaInput,
)


def _make_record(*, kind: str = "IMAGE", size: int = 100, sha: str = "abc"):
    rec = MagicMock()
    rec.id = uuid4()
    rec.kind = kind
    rec.size_bytes = size
    rec.sha256 = sha
    return rec


@pytest.mark.asyncio
async def test_inserts_new_record_when_sha_not_exists() -> None:
    repo = MagicMock()
    repo.get_by_sha = AsyncMock(return_value=None)
    inserted = _make_record(sha=hashlib.sha256(b"hello").hexdigest())
    repo.insert = AsyncMock(return_value=inserted)

    use_case = UploadTemplateMedia(repo=repo, public_base_url="https://example.com/")
    output = await use_case.execute(
        UploadTemplateMediaInput(
            account_id=uuid4(),
            kind="IMAGE",
            data=b"hello",
            mime="image/png",
            original_filename="x.png",
        )
    )

    repo.insert.assert_called_once()
    assert output.media_url.startswith("https://example.com/public/media/")
    assert output.media_url.endswith(str(inserted.id))
    assert output.media_object_key == str(inserted.id)
    assert output.media_kind == "IMAGE"
    assert output.sha256 == hashlib.sha256(b"hello").hexdigest()


@pytest.mark.asyncio
async def test_reuses_existing_record_on_dedup() -> None:
    existing = _make_record()
    repo = MagicMock()
    repo.get_by_sha = AsyncMock(return_value=existing)
    repo.insert = AsyncMock()

    use_case = UploadTemplateMedia(repo=repo, public_base_url="https://example.com")
    output = await use_case.execute(
        UploadTemplateMediaInput(
            account_id=uuid4(),
            kind="IMAGE",
            data=b"x" * 50,
            mime="image/png",
            original_filename="x.png",
        )
    )

    repo.insert.assert_not_called()
    assert str(existing.id) in output.media_url


@pytest.mark.asyncio
async def test_rejects_image_over_5mb() -> None:
    repo = MagicMock()
    repo.get_by_sha = AsyncMock(return_value=None)
    use_case = UploadTemplateMedia(repo=repo, public_base_url="https://x.com")
    big_data = b"\x00" * (5 * 1024 * 1024 + 1)

    with pytest.raises(MediaTooLargeError) as exc_info:
        await use_case.execute(
            UploadTemplateMediaInput(
                account_id=uuid4(),
                kind="IMAGE",
                data=big_data,
                mime="image/png",
                original_filename="big.png",
            )
        )
    assert exc_info.value.kind == "IMAGE"
    assert exc_info.value.limit == 5 * 1024 * 1024


@pytest.mark.asyncio
async def test_accepts_video_up_to_16mb() -> None:
    repo = MagicMock()
    repo.get_by_sha = AsyncMock(return_value=None)
    repo.insert = AsyncMock(return_value=_make_record(kind="VIDEO", size=16 * 1024 * 1024))
    use_case = UploadTemplateMedia(repo=repo, public_base_url="https://x.com")

    out = await use_case.execute(
        UploadTemplateMediaInput(
            account_id=uuid4(),
            kind="VIDEO",
            data=b"\x00" * (16 * 1024 * 1024),
            mime="video/mp4",
            original_filename="v.mp4",
        )
    )
    assert out.media_kind == "VIDEO"
```

- [ ] **Step 4: Rodar tests**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run pytest tests/unit/meta_templates/test_upload_template_media.py -v 2>&1 | tail -10
```

Esperado: 4 passed.

- [ ] **Step 5: Lint**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run ruff check src/shared/application/use_cases/meta_templates/ tests/unit/meta_templates/
```

- [ ] **Step 6: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/api/src/shared/application/use_cases/meta_templates/upload_template_media.py apps/api/tests/unit/meta_templates/test_upload_template_media.py
git commit -m "refactor(meta-media): UploadTemplateMedia salva no Postgres (BYTEA + dedup sha256)"
```

---

### Task 5: Endpoint `POST /admin/meta-templates/upload-media` — refactor

**Files:**
- Modify: `apps/api/src/interface/http/routers/admin/meta_templates.py`

- [ ] **Step 1: Localizar o endpoint atual**

```bash
grep -n "upload-media\|UploadTemplateMedia\|R2Storage" /home/fabio/www/agente-plug/apps/api/src/interface/http/routers/admin/meta_templates.py
```

- [ ] **Step 2: Refatorar a função do endpoint**

Substituir todo o handler `upload_media` (linhas ~100-140 do arquivo atual) por:

```python
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
        raise HTTPException(status_code=422, detail={"code": "MEDIA_KIND_INVALID"})

    data = await file.read()
    settings = get_settings()

    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        repo = MetaTemplateMediaRepository(session=session)
        use_case = UploadTemplateMedia(
            repo=repo, public_base_url=settings.public_base_url
        )
        try:
            out = await use_case.execute(
                UploadTemplateMediaInput(
                    account_id=account_uuid,
                    kind=kind,  # type: ignore[arg-type]
                    data=data,
                    mime=file.content_type or "application/octet-stream",
                    original_filename=file.filename or "upload",
                )
            )
        except MediaTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc

    return UploadMediaResponse(
        media_url=out.media_url,
        media_object_key=out.media_object_key,
        media_kind=out.media_kind,  # type: ignore[arg-type]
        sha256=out.sha256,
        size=out.size,
    )
```

- [ ] **Step 3: Atualizar imports no topo do arquivo**

Remover (se presente):
```python
from shared.adapters.storage.r2 import R2Storage
from shared.application.use_cases.meta_templates.upload_template_media import UploadTemplateMedia, UploadTemplateMediaInput
```

E adicionar (substituir):
```python
from shared.adapters.db.repositories.meta_template_media_repo import (
    MetaTemplateMediaRepository,
)
from shared.application.use_cases.meta_templates.upload_template_media import (
    MediaTooLargeError,
    UploadTemplateMedia,
    UploadTemplateMediaInput,
)
```

- [ ] **Step 4: TypeScript não aplicável (backend). Lint:**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run ruff check src/interface/http/routers/admin/meta_templates.py
```

- [ ] **Step 5: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/api/src/interface/http/routers/admin/meta_templates.py
git commit -m "refactor(meta-media): endpoint upload-media usa Postgres em vez de R2"
```

---

### Task 6: Endpoint público `GET /public/media/{id}`

**Files:**
- Create: `apps/api/src/interface/http/routers/public_media.py`
- Modify: `apps/api/src/main.py` (incluir router)
- Test: `apps/api/tests/unit/interface/test_public_media_router.py`

- [ ] **Step 1: Criar teste falhando**

```python
# apps/api/tests/unit/interface/test_public_media_router.py
"""Smoke test do endpoint público GET /public/media/{id}."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app


def test_public_media_router_mounted() -> None:
    """O endpoint público está registrado no app."""
    routes = [r.path for r in app.routes]
    assert "/public/media/{media_id}" in routes


def test_public_media_returns_404_for_unknown_id() -> None:
    """UUID válido mas sem registro retorna 404."""
    client = TestClient(app)
    response = client.get("/public/media/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
```

> Nota: se o `TestClient(app)` exige fixtures de DB (postgres), este teste vira integration. Em ambiente sem postgres, o teste do 404 pode falhar com 500/erro de conexão DB. Aceitável — basta o primeiro teste (rota montada) passar.

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run pytest tests/unit/interface/test_public_media_router.py -v 2>&1 | tail -10
```

Esperado: 1+ falha (rota não existe).

- [ ] **Step 3: Criar o router**

```python
# apps/api/src/interface/http/routers/public_media.py
"""Endpoint público (sem auth) que serve mídia de template do nosso Postgres.

UUID gera entropia suficiente pra evitar enumeração. SHA256 garante imutabilidade
do conteúdo, então Cache-Control longo é seguro. Acessível por Meta, ChatNexo e
frontend pra preview no painel.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from shared.adapters.db.repositories.meta_template_media_repo import (
    MetaTemplateMediaRepository,
)
from shared.adapters.db.session import session_scope

router = APIRouter(tags=["public-media"])


@router.get("/public/media/{media_id}")
async def get_media(media_id: UUID) -> Response:
    async with session_scope() as session:
        repo = MetaTemplateMediaRepository(session=session)
        record = await repo.get_by_id(media_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return Response(
        content=bytes(record.data),
        media_type=record.mime,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Length": str(record.size_bytes),
        },
    )
```

- [ ] **Step 4: Registrar o router em `main.py`**

Localizar `main.py`:

```bash
grep -n "include_router\|app = FastAPI" /home/fabio/www/agente-plug/apps/api/src/main.py | head -10
```

Adicionar import + include na lista existente. Exemplo (ajustar pela posição real):

```python
from interface.http.routers.public_media import router as public_media_router

# ... (após outras includes) ...
app.include_router(public_media_router)
```

- [ ] **Step 5: Rodar testes**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run pytest tests/unit/interface/test_public_media_router.py -v 2>&1 | tail -10
```

Esperado: 1+ passa (rota montada). O 404 pode requerer DB — aceitável que esse falhe sem postgres.

- [ ] **Step 6: Lint**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run ruff check src/interface/http/routers/public_media.py src/main.py
```

- [ ] **Step 7: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/api/src/interface/http/routers/public_media.py apps/api/src/main.py apps/api/tests/unit/interface/test_public_media_router.py
git commit -m "feat(meta-media): endpoint público GET /public/media/{id} serve BYTEA com Cache-Control"
```

---

### Task 7: Remover dependência de `StoragePort` em `CreateTemplate` e `DeleteTemplate`

**Files:**
- Modify: `apps/api/src/shared/application/use_cases/meta_templates/create_template.py`
- Modify: `apps/api/src/shared/application/use_cases/meta_templates/delete_template.py`

- [ ] **Step 1: Refatorar `create_template.py`**

```bash
cat /home/fabio/www/agente-plug/apps/api/src/shared/application/use_cases/meta_templates/create_template.py
```

Identificar onde `storage: StoragePort` aparece no `__init__` e no uso (provavelmente `storage.put` ou similar pra subir mídia ao R2).

Mudanças:
1. Remover `from shared.domain.ports.storage import StoragePort` do topo.
2. Remover `storage: StoragePort` do `__init__`.
3. Remover qualquer uso de `self._storage.put(...)` — agora a mídia já vem do `media_url` do nosso endpoint (vindo do `UploadTemplateMedia`), não precisa subir nada aqui. Apenas usa `input_.media_url` como está.
4. Atualizar quem instancia `CreateTemplate` no router pra não passar mais `storage=...`.

```bash
grep -n "CreateTemplate(" /home/fabio/www/agente-plug/apps/api/src/interface/http/routers/admin/meta_templates.py
```

Ajustar a chamada para remover o argumento `storage=...`.

- [ ] **Step 2: Refatorar `delete_template.py`**

Mesmo padrão. Remover dep `StoragePort` + uso (`self._storage.delete(...)` se houver — agora não há nada pra deletar no R2 porque não usamos mais R2).

Se houver lógica de cleanup que removia bytes ao deletar template, **substituir** por: opcional cleanup que deleta records de `meta_template_media` órfãos (mídia não referenciada por nenhum template).

**Decisão de escopo:** NÃO implementar cleanup de mídia órfã nesta task. Mídia fica no banco mesmo após template ser deletado (custa-benefício favorável: dedup garante que mesmo upload reusa o mesmo registro; deletar mídia seria complexo se referenciada por mais de um template no futuro).

Apenas remover a dep de StoragePort/storage do construtor e da chamada no router.

- [ ] **Step 3: Atualizar quem instancia `DeleteTemplate`**

```bash
grep -n "DeleteTemplate(" /home/fabio/www/agente-plug/apps/api/src/interface/http/routers/admin/meta_templates.py
```

Remover `storage=...` da invocação.

- [ ] **Step 4: Rodar testes de meta_templates**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run pytest tests/unit/meta_templates -v 2>&1 | tail -20
```

Pode quebrar tests existentes que instanciavam com `storage=...`. **Atualizar esses testes:** procurar e remover argumentos `storage` das construções de `CreateTemplate`/`DeleteTemplate` nos testes.

```bash
grep -rln "CreateTemplate(\|DeleteTemplate(" /home/fabio/www/agente-plug/apps/api/tests
```

Para cada arquivo, remover o argumento `storage=...` (provavelmente `storage=MagicMock()` ou similar).

- [ ] **Step 5: Rodar testes novamente**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run pytest tests/unit -q 2>&1 | tail -5
```

Esperado: todos passam.

- [ ] **Step 6: Lint**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run ruff check src/shared/application/use_cases/meta_templates/ src/interface/http/routers/admin/meta_templates.py tests/
```

- [ ] **Step 7: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/api/src/shared/application/use_cases/meta_templates/ apps/api/src/interface/http/routers/admin/meta_templates.py apps/api/tests/
git commit -m "refactor(meta-templates): remove dependência de StoragePort em Create/Delete use cases"
```

---

### Task 8: Remover diretório `storage/` + `StoragePort` + vars `R2_*`

**Files:**
- Delete: `apps/api/src/shared/adapters/storage/` (diretório inteiro)
- Delete: `apps/api/src/shared/domain/ports/storage.py`
- Modify: `apps/api/src/shared/config/settings.py` (remover vars R2)
- Modify: `apps/api/.env.example` (remover linhas R2_*)

- [ ] **Step 1: Confirmar zero referências externas**

```bash
grep -rn "StoragePort\|R2Storage\|NullStorage\|from_settings_or_null\|r2_account_id\|r2_access_key" /home/fabio/www/agente-plug/apps/api/src /home/fabio/www/agente-plug/apps/api/tests 2>/dev/null
```

Esperado: zero ocorrências. Se houver, são restos das Tasks 5/7 — limpar antes.

- [ ] **Step 2: Deletar arquivos**

```bash
cd /home/fabio/www/agente-plug && rm -rf apps/api/src/shared/adapters/storage/
cd /home/fabio/www/agente-plug && rm apps/api/src/shared/domain/ports/storage.py
```

- [ ] **Step 3: Remover vars R2 de `settings.py`**

Editar `apps/api/src/shared/config/settings.py`. Localizar bloco com `r2_account_id`, `r2_access_key_id`, `r2_secret_access_key`, `r2_bucket_name`, `r2_public_base_url` e remover as 5 linhas.

```bash
grep -n "r2_" /home/fabio/www/agente-plug/apps/api/src/shared/config/settings.py
```

- [ ] **Step 4: Remover linhas R2_* de `.env.example`**

```bash
grep -n "^R2_" /home/fabio/www/agente-plug/apps/api/.env.example
```

Deletar as 5 linhas.

- [ ] **Step 5: Rodar suite completa**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run pytest tests/unit -q 2>&1 | tail -5
```

Esperado: tudo passa.

- [ ] **Step 6: Lint**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run ruff check src tests
```

- [ ] **Step 7: Commit**

```bash
cd /home/fabio/www/agente-plug && git add -A apps/api/src/shared/adapters/ apps/api/src/shared/domain/ports/ apps/api/src/shared/config/settings.py apps/api/.env.example
git commit -m "chore(meta-media): remove R2Storage + StoragePort + vars R2_* (substituídos por Postgres)"
```

---

## Fase 2 — Frontend: preview de mídia inline

### Task 9: Helper `templateMediaHelpers.ts`

**Files:**
- Create: `apps/web/src/features/onboarding/lib/templateMediaHelpers.ts`

- [ ] **Step 1: Criar o helper**

```ts
// apps/web/src/features/onboarding/lib/templateMediaHelpers.ts
import type { MetaTemplate } from "@/features/templates/types";

export type MediaKind = "IMAGE" | "VIDEO" | "DOCUMENT";

/**
 * Verifica se o template tem header de mídia (IMAGE/VIDEO/DOCUMENT).
 */
export function hasMedia(template: MetaTemplate | null | undefined): boolean {
  if (!template) return false;
  const header = template.components.find((c) => c.type === "HEADER");
  if (!header) return false;
  return (
    header.format === "IMAGE" ||
    header.format === "VIDEO" ||
    header.format === "DOCUMENT"
  );
}

/**
 * Retorna a URL pública da mídia (servida pelo nosso /public/media/{id}).
 * `null` se template não tem mídia.
 */
export function getMediaUrl(
  template: MetaTemplate | null | undefined,
): string | null {
  if (!template) return null;
  return template.media_url ?? null;
}

/**
 * Retorna o kind da mídia (IMAGE/VIDEO/DOCUMENT) — útil pra escolher o
 * componente de render (img/video/link).
 */
export function getMediaKind(
  template: MetaTemplate | null | undefined,
): MediaKind | null {
  if (!template) return null;
  const header = template.components.find((c) => c.type === "HEADER");
  if (!header) return null;
  if (
    header.format === "IMAGE" ||
    header.format === "VIDEO" ||
    header.format === "DOCUMENT"
  ) {
    return header.format as MediaKind;
  }
  return null;
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /home/fabio/www/agente-plug/apps/web && npx tsc --noEmit 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/web/src/features/onboarding/lib/templateMediaHelpers.ts
git commit -m "feat(onboarding): helpers hasMedia/getMediaUrl/getMediaKind"
```

---

### Task 10: Hook `useMetaTemplateDetail`

**Files:**
- Create: `apps/web/src/features/onboarding/hooks/useMetaTemplateDetail.ts`

- [ ] **Step 1: Criar o hook**

```ts
// apps/web/src/features/onboarding/hooks/useMetaTemplateDetail.ts
"use client";

import { useEffect, useState } from "react";
import { listMetaTemplates } from "@/lib/api";
import type { MetaTemplate } from "@/features/templates/types";

/**
 * Busca o template Meta pelo `name` e retorna os componentes completos
 * (incluindo media_url/media_kind). Cache simples em módulo entre chamadas
 * para evitar refetch quando vários StepItem usam mesmo template.
 */
const _cache: Record<string, MetaTemplate> = {};
let _allCachePromise: Promise<MetaTemplate[]> | null = null;

async function _fetchAll(): Promise<MetaTemplate[]> {
  if (_allCachePromise === null) {
    _allCachePromise = listMetaTemplates();
  }
  return _allCachePromise;
}

export function useMetaTemplateDetail(name: string | null) {
  const [template, setTemplate] = useState<MetaTemplate | null>(
    name ? (_cache[name] ?? null) : null,
  );
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!name) {
      setTemplate(null);
      return;
    }
    if (_cache[name]) {
      setTemplate(_cache[name]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    _fetchAll()
      .then((all) => {
        if (cancelled) return;
        for (const t of all) _cache[t.name] = t;
        const found = _cache[name] ?? null;
        setTemplate(found);
      })
      .catch(() => {
        if (!cancelled) setTemplate(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [name]);

  return { template, loading };
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /home/fabio/www/agente-plug/apps/web && npx tsc --noEmit 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/web/src/features/onboarding/hooks/useMetaTemplateDetail.ts
git commit -m "feat(onboarding): useMetaTemplateDetail hook com cache em módulo"
```

---

### Task 11: Componente `TemplatePreview`

**Files:**
- Create: `apps/web/src/features/onboarding/components/TemplatePreview.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// apps/web/src/features/onboarding/components/TemplatePreview.tsx
"use client";

import type { MetaTemplate, TemplateComponent } from "@/features/templates/types";
import { getMediaKind, getMediaUrl, hasMedia } from "../lib/templateMediaHelpers";

interface TemplatePreviewProps {
  template: MetaTemplate;
}

function getComponentText(
  components: TemplateComponent[],
  type: string,
): string | null {
  const c = components.find((x) => x.type === type);
  return c?.text ?? null;
}

function getButtons(components: TemplateComponent[]) {
  const c = components.find((x) => x.type === "BUTTONS");
  return c?.buttons ?? [];
}

/**
 * Preview da mensagem WhatsApp inline — bolha com mídia + body + footer + botões.
 * Renderiza inline (não modal) abaixo do select de template no StepInlineForm.
 */
export function TemplatePreview({ template }: TemplatePreviewProps) {
  const mediaUrl = getMediaUrl(template);
  const mediaKind = getMediaKind(template);
  const showMedia = hasMedia(template) && mediaUrl !== null;
  const headerText = getComponentText(template.components, "HEADER");
  const headerComp = template.components.find((c) => c.type === "HEADER");
  const bodyText = getComponentText(template.components, "BODY");
  const footerText = getComponentText(template.components, "FOOTER");
  const buttons = getButtons(template.components);

  return (
    <div className="rounded-lg border border-outline-variant bg-surface-container-low p-3">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
        Preview da mensagem
      </p>
      <div className="rounded-lg border border-outline-variant bg-surface-container p-3 shadow-sm">
        {/* Header com mídia */}
        {showMedia && mediaKind === "IMAGE" && (
          <img
            src={mediaUrl ?? undefined}
            alt="Header"
            className="mb-2 max-h-48 w-full rounded object-cover"
          />
        )}
        {showMedia && mediaKind === "VIDEO" && (
          <video
            src={mediaUrl ?? undefined}
            controls
            className="mb-2 max-h-48 w-full rounded bg-black"
          />
        )}
        {showMedia && mediaKind === "DOCUMENT" && (
          <a
            href={mediaUrl ?? undefined}
            target="_blank"
            rel="noopener noreferrer"
            className="mb-2 flex items-center gap-2 rounded border border-outline-variant bg-surface p-2 text-xs text-on-surface hover:bg-surface-container-high"
          >
            <span className="material-symbols-outlined text-base">
              description
            </span>
            <span className="truncate">{template.name}.pdf</span>
          </a>
        )}

        {/* Header em texto (quando não há mídia) */}
        {!showMedia && headerText && headerComp?.format === "TEXT" && (
          <p className="mb-2 text-sm font-semibold text-on-surface">
            {headerText}
          </p>
        )}

        {/* Body */}
        {bodyText && (
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-on-surface">
            {bodyText}
          </p>
        )}

        {/* Footer */}
        {footerText && (
          <p className="mt-2 text-xs italic text-on-surface-variant">
            {footerText}
          </p>
        )}

        {/* Botões */}
        {buttons.length > 0 && (
          <div className="mt-3 flex flex-col gap-1.5 border-t border-outline-variant pt-2">
            {buttons.map((btn: { type?: string; text?: string }, i: number) => (
              <div
                key={i}
                className="rounded border border-outline-variant bg-surface px-3 py-1.5 text-center text-xs text-primary"
              >
                {btn.text ?? "Botão"}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /home/fabio/www/agente-plug/apps/web && npx tsc --noEmit 2>&1 | tail -5
```

> Pode acusar erros se `MetaTemplate.media_url` ou `TemplateComponent.buttons` não existem no tipo. Se acusar, verificar `apps/web/src/features/templates/types.ts` — os tipos provavelmente já têm esses campos (template já existia antes da PR). Se faltar, adicionar.

- [ ] **Step 3: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/web/src/features/onboarding/components/TemplatePreview.tsx
git commit -m "feat(onboarding): TemplatePreview component (mídia + body + footer + botões inline)"
```

---

### Task 12: Integrar `TemplatePreview` no `StepInlineForm`

**Files:**
- Modify: `apps/web/src/features/onboarding/components/StepInlineForm.tsx`

- [ ] **Step 1: Adicionar import**

No topo do arquivo, adicionar:

```tsx
import { useMetaTemplateDetail } from "../hooks/useMetaTemplateDetail";
import { TemplatePreview } from "./TemplatePreview";
```

- [ ] **Step 2: Usar hook + renderizar preview**

Localizar o bloco `template-mode` (Collapse open={mode === "template"}). Dentro dele, após o select de template e o preview de body atual (que mostra só texto), adicionar bloco com `useMetaTemplateDetail`:

```bash
grep -n "selectedTemplate\|currentTemplate\|templateBody" /home/fabio/www/agente-plug/apps/web/src/features/onboarding/components/StepInlineForm.tsx | head -10
```

Hoje existe `currentTemplate = templates.find((t) => t.name === selectedTemplate);` que pega do array já carregado. Esse objeto pode estar incompleto (sem `media_url` populado dependendo do shape do `listMetaTemplates`).

**Estratégia:** usar `useMetaTemplateDetail(selectedTemplate || null)` para garantir que o template venha com `media_url`:

Adicionar no corpo do componente (depois dos useState existentes):

```tsx
const { template: detailedTemplate } = useMetaTemplateDetail(
  selectedTemplate || null,
);
```

E no JSX, dentro do bloco `<Collapse open={mode === "template"}>`, depois do bloco que mostra `templateBody` (preview de texto atual), adicionar:

```tsx
{/* Preview da mensagem (mídia + body + footer + botões) */}
{detailedTemplate && (
  <TemplatePreview template={detailedTemplate} />
)}
```

> O preview de texto atual (`templateBody`) pode ser removido se quiser deduplicar — mas pode também coexistir (são visões diferentes). **Decisão pragmática:** manter ambos (texto cru + preview formatado).

- [ ] **Step 3: TypeScript check**

```bash
cd /home/fabio/www/agente-plug/apps/web && npx tsc --noEmit 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/web/src/features/onboarding/components/StepInlineForm.tsx
git commit -m "feat(onboarding): preview de mídia inline no StepInlineForm"
```

---

### Task 13: Thumbnail compacto no `StepItem`

**Files:**
- Modify: `apps/web/src/features/onboarding/components/StepItem.tsx`

- [ ] **Step 1: Adicionar imports**

No topo do arquivo:

```tsx
import { useMetaTemplateDetail } from "../hooks/useMetaTemplateDetail";
import { getMediaKind, getMediaUrl, hasMedia } from "../lib/templateMediaHelpers";
```

- [ ] **Step 2: Renderizar thumbnail quando há mídia**

Localizar o trecho do `StepItem` que renderiza o ícone do template (linha ~66 do arquivo atual, dentro do `{/* Conteúdo central */}`):

```tsx
<span
  className={[
    "material-symbols-outlined",
    isTemplate ? "text-primary/70" : "text-on-surface-variant",
  ].join(" ")}
  style={{ fontSize: "14px" }}
>
  {isTemplate ? "receipt_long" : "chat"}
</span>
```

Antes desse ícone, adicionar lookup do template + thumbnail condicional:

```tsx
// dentro do corpo do componente, após os outros hooks:
const { template: detail } = useMetaTemplateDetail(
  step.meta_template_name ?? null,
);
const showThumb = hasMedia(detail);
const thumbUrl = getMediaUrl(detail);
const thumbKind = getMediaKind(detail);

// substituir o <span ícone> por:
{showThumb && thumbUrl && thumbKind === "IMAGE" ? (
  <img
    src={thumbUrl}
    alt=""
    className="h-10 w-10 shrink-0 rounded object-cover"
  />
) : showThumb && thumbKind === "VIDEO" ? (
  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-surface-container-high text-on-surface-variant">
    <span className="material-symbols-outlined text-base">play_circle</span>
  </div>
) : showThumb && thumbKind === "DOCUMENT" ? (
  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-surface-container-high text-on-surface-variant">
    <span className="material-symbols-outlined text-base">description</span>
  </div>
) : (
  <span
    className={[
      "material-symbols-outlined",
      isTemplate ? "text-primary/70" : "text-on-surface-variant",
    ].join(" ")}
    style={{ fontSize: "14px" }}
  >
    {isTemplate ? "receipt_long" : "chat"}
  </span>
)}
```

> Quando não há mídia (template texto, ou message_text), mantém o ícone Material Symbols original.

- [ ] **Step 3: TypeScript check**

```bash
cd /home/fabio/www/agente-plug/apps/web && npx tsc --noEmit 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/web/src/features/onboarding/components/StepItem.tsx
git commit -m "feat(onboarding): thumbnail compacto no StepItem quando template tem mídia"
```

---

## Fase 3 — /settings: webhook URL + instruções

### Task 14: Componente `HublaWebhookCard`

**Files:**
- Create: `apps/web/src/features/settings/components/HublaWebhookCard.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// apps/web/src/features/settings/components/HublaWebhookCard.tsx
"use client";

import { useToast } from "@/shared/hooks/useToast";

const HUBLA_WEBHOOK_URL = "https://api-flow.ianexo.com.br/webhook/hubla";

export function HublaWebhookCard() {
  const toast = useToast();

  async function copy(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`${label} copiado`);
    } catch {
      toast.error("Falha ao copiar");
    }
  }

  return (
    <div className="mt-4 rounded-lg border border-outline-variant bg-surface-container-low p-4">
      <h4 className="text-sm font-semibold text-on-surface">URL do Webhook</h4>
      <p className="mt-1 text-xs text-on-surface-variant">
        Configure essa URL no painel da Hubla para receber eventos.
      </p>
      <div className="mt-3 flex items-center gap-2 rounded-md border border-outline-variant bg-surface px-3 py-2">
        <code className="flex-1 truncate font-mono text-xs text-on-surface">
          {HUBLA_WEBHOOK_URL}
        </code>
        <button
          type="button"
          onClick={() => void copy(HUBLA_WEBHOOK_URL, "URL")}
          className="rounded-md p-1.5 text-on-surface-variant hover:bg-surface-container-high"
          aria-label="Copiar URL"
        >
          <span className="material-symbols-outlined text-base">
            content_copy
          </span>
        </button>
      </div>

      <h4 className="mt-5 text-sm font-semibold text-on-surface">
        Como configurar na Hubla
      </h4>
      <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-xs text-on-surface-variant">
        <li>Acesse o painel da Hubla → Configurações → Webhooks.</li>
        <li>
          Crie um webhook novo e cole a URL acima no campo &quot;URL do
          endpoint&quot;.
        </li>
        <li>
          No campo &quot;Secret&quot; / &quot;Token&quot;, cole o mesmo valor
          configurado em <strong>Webhook Secret</strong> acima.
        </li>
        <li>
          Selecione os eventos que quer disparar fluxos de onboarding (ex:{" "}
          <code>subscription.activated</code>,{" "}
          <code>lead.abandoned_cart</code>, etc).
        </li>
        <li>
          Salve. A partir daí, qualquer evento dispara automaticamente os
          fluxos configurados em <strong>/onboarding</strong>.
        </li>
      </ol>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /home/fabio/www/agente-plug/apps/web && npx tsc --noEmit 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/web/src/features/settings/components/HublaWebhookCard.tsx
git commit -m "feat(settings): HublaWebhookCard (URL copiável + instruções de configuração)"
```

---

### Task 15: Integrar `HublaWebhookCard` na seção Hubla do /settings

**Files:**
- Modify: `apps/web/src/features/settings/components/IntegrationSection.tsx`

- [ ] **Step 1: Localizar a seção Hubla**

```bash
grep -n "hubla\|Hubla\|hubla_webhook_secret" /home/fabio/www/agente-plug/apps/web/src/features/settings/components/IntegrationSection.tsx
```

- [ ] **Step 2: Adicionar componente customizado na seção Hubla**

A seção Hubla é definida como uma entry de um array de config (`{ id: "hubla", title: "Hubla", ... fields: [...] }`). Pra inserir um componente custom (`HublaWebhookCard`) abaixo dos campos, precisamos adaptar o render.

**Estratégia minimalista:** ao invés de modificar o sistema de render por arrays, adicionar o `<HublaWebhookCard />` direto no JSX da `IntegrationSection`, identificando a seção Hubla pelo `id`.

Localizar onde a seção Hubla é renderizada (provavelmente um `.map` sobre `sections` array). Modificar o render para incluir o card extra após os fields da seção Hubla:

```tsx
import { HublaWebhookCard } from "./HublaWebhookCard";

// ... no map de sections, dentro do .map((section) => ...):
{section.fields.map(/* ... renderiza fields normalmente ... */)}
{section.id === "hubla" && <HublaWebhookCard />}
```

Posicionar **dentro** do container da seção Hubla, **depois** dos fields.

> Se a estrutura atual do `IntegrationSection.tsx` for muito rígida (ex: cada seção é um sub-componente próprio), inserir `<HublaWebhookCard />` na seção Hubla via algum slot ou hardcoded por id é aceitável. Olhar o código e fazer a integração mais limpa possível sem refatorar a estrutura.

- [ ] **Step 3: TypeScript check**

```bash
cd /home/fabio/www/agente-plug/apps/web && npx tsc --noEmit 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/web/src/features/settings/components/IntegrationSection.tsx
git commit -m "feat(settings): renderiza HublaWebhookCard abaixo dos fields da seção Hubla"
```

---

## Fase 4 — Validação + push + abrir PR único

### Task 16: Validação end-to-end + abrir PR

**Files:** (nenhuma modificação — só checks + git)

- [ ] **Step 1: TypeScript final**

```bash
cd /home/fabio/www/agente-plug/apps/web && npx tsc --noEmit
```

Esperado: 0 erros.

- [ ] **Step 2: Suite api**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run pytest tests/unit -q 2>&1 | tail -5
```

Esperado: tudo passa.

- [ ] **Step 3: Lint api**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run ruff check src tests
cd /home/fabio/www/agente-plug/apps/api && uv run ruff format --check src tests
```

Esperado: All checks passed em ambos.

- [ ] **Step 4: Smoke manual — upload de mídia**

Subir backend + frontend local:

```bash
cd /home/fabio/www/agente-plug && docker compose up -d postgres redis
cd /home/fabio/www/agente-plug/apps/api && uv run uvicorn main:app --reload &
cd /home/fabio/www/agente-plug/apps/web && npm run dev
```

Em `/templates`:
- [ ] Abrir "Novo template", escolher Header IMAGE, fazer upload de uma imagem ~1MB.
- [ ] Verificar que o upload **completa sem 422** (R2 não bloqueia mais).
- [ ] Verificar no banco:
   ```bash
   docker compose exec -T postgres psql -U postgres -d agente_plug -c "
     SELECT id, kind, mime, size_bytes, sha256 FROM meta_template_media ORDER BY created_at DESC LIMIT 3;
   "
   ```
- [ ] Acessar a URL retornada (`/public/media/<id>`) direto no browser → imagem renderiza.

- [ ] **Step 5: Smoke manual — preview no onboarding**

Em `/onboarding`:
- [ ] Editar um flow existente, expandir step 3 (Mensagens).
- [ ] Selecionar um template que tem mídia (IMAGE/VIDEO).
- [ ] Verificar que `TemplatePreview` aparece com a mídia inline.
- [ ] Voltar pra lista de steps (`StepItem`): verificar thumbnail 40×40.

- [ ] **Step 6: Smoke manual — /settings**

Em `/settings`:
- [ ] Rolar até a seção Hubla.
- [ ] Verificar que o card "URL do Webhook" aparece com a URL `https://api-flow.ianexo.com.br/webhook/hubla`.
- [ ] Clicar no botão copiar → toast de confirmação.
- [ ] Verificar lista numerada de 5 passos.

- [ ] **Step 7: Push final**

```bash
cd /home/fabio/www/agente-plug && git push 2>&1 | tail -3
```

- [ ] **Step 8: Abrir PR único (Spec A + Spec B)**

```bash
gh pr create --title "feat: onboarding step refinement + template media in Postgres + webhook /settings" --body "$(cat <<'EOF'
## Summary

Branch consolidada com duas entregas do roadmap recente:

### Spec A — Refinamento da sequência de mensagens (já implementada na branch)
- Conectores SVG entre cards
- Drag handle sempre visível
- Numeração 1+ (com migration corrigindo flows pré-existentes)
- Label contextual com `triggerVerb` do evento ("Assim que a venda for ativada", "2 dias após a mensagem anterior")
- Campo tempo com 3 inputs Dias/Horas/Minutos + ± + chips de presets + auto-normalize
- Auto-fill do tempo no próximo card; salvar fecha + abre próximo
- Backend: `delay_from_purchase_minutes` → `delay_from_previous_minutes` (relativo do step anterior) com migration round-trip testada

### Spec B — Mídia de template no Postgres + webhook na /settings
- Substitui R2 externo por BYTEA no Postgres (`meta_template_media` com dedup sha256)
- Endpoint público `GET /public/media/{id}` (sem auth, cache imutável)
- Limites: IMAGE 5MB, VIDEO/DOCUMENT 16MB
- Remove `R2Storage`, `StoragePort` e vars `R2_*` do projeto
- Preview de mídia inline no `StepInlineForm` (`TemplatePreview` — bolha WhatsApp)
- Thumbnail compacto no `StepItem` quando template tem mídia
- Card webhook na /settings com URL copiável + 5 passos de configuração

## Test plan

- [x] 484+ testes unit api passam
- [x] TypeScript web 0 erros
- [x] Ruff check + format limpo
- [x] Migration upgrade/downgrade testada round-trip
- [x] Upload de imagem completa sem 422
- [x] Preview de mídia aparece inline no /onboarding
- [x] Card webhook na /settings funcional com botão copiar
- [ ] Smoke manual em dev: criar flow novo, editar step, validar timeline visual

## Docs

- Spec A: `docs/superpowers/specs/2026-05-27-step-sequence-refinement-design.md`
- Plan A: `docs/superpowers/plans/2026-05-27-step-sequence-refinement.md`
- Spec B: `docs/superpowers/specs/2026-05-27-template-media-and-webhook-settings-design.md`
- Plan B: `docs/superpowers/plans/2026-05-27-template-media-and-webhook-settings.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)" 2>&1 | tail -3
```

Retornar a URL do PR.

---

## Self-Review

### Cobertura da spec

| Spec requirement | Coberto em |
|---|---|
| Tabela `meta_template_media` com BYTEA + dedup sha256 | Task 2 |
| Limites por kind (5MB/16MB) + 413 | Task 4 (`MediaTooLargeError`) + Task 5 (handler 413) |
| Repository com get_by_id/get_by_sha/insert | Task 3 |
| Use case `UploadTemplateMedia` com dedup | Task 4 |
| Endpoint POST /admin/meta-templates/upload-media refatorado | Task 5 |
| Endpoint público GET /public/media/{id} | Task 6 |
| Cache-Control: public, max-age=31536000, immutable | Task 6 |
| Remover R2Storage + StoragePort + vars R2_* | Tasks 7 + 8 |
| Settings: novo `PUBLIC_BASE_URL` | Task 1 |
| Helpers hasMedia/getMediaUrl/getMediaKind | Task 9 |
| Hook `useMetaTemplateDetail` | Task 10 |
| `TemplatePreview` (bolha WhatsApp) | Task 11 |
| Integração no StepInlineForm | Task 12 |
| Thumbnail no StepItem | Task 13 |
| `HublaWebhookCard` (URL + instruções) | Task 14 |
| Integração na seção Hubla | Task 15 |
| Validação + PR único | Task 16 |

Nenhum gap detectado.

### Pontos resolvidos durante a escrita do plano

- ✅ Confirmado uso real de `StoragePort` em `CreateTemplate`, `DeleteTemplate`, `UploadTemplateMedia` — Task 7 endereça os 2 primeiros; Task 4 refatora o terceiro completamente.
- ✅ Settings já tem `r2_public_base_url`; substituído por `public_base_url` na Task 1, e as 5 vars R2 são removidas na Task 8.
- ✅ Migration sequencial: `down_revision = 9f07c98d5b22` (head da Spec A já mergeada na branch).

### Pontos que ficam como decisões de implementação razoáveis

- **Botão copiar no campo "Webhook Secret":** removido do escopo desta entrega — adicionar pode exigir ajuste no sistema de render do `IntegrationSection` (input password com botão lateral). Issue minor, fica como follow-up.
- **Cleanup de mídia órfã:** quando template é deletado, o registro em `meta_template_media` permanece (dedup ainda pode ser referenciado por outro template no futuro). Não implementado nesta entrega.
- **Streaming chunked do BYTEA:** read completo na memória. Aceitável dado limite de 16MB. Otimização futura se virar gargalo.
