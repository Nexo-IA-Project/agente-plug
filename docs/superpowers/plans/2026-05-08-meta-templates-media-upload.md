# Meta Templates com Upload de Mídia — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar upload nativo de imagem/vídeo/documento no formulário de Meta Templates, com armazenamento em Cloudflare R2, validações completas Meta, sincronização sob demanda do status, disparo com mídia e exclusão segura.

**Architecture:** Adicionamos um adapter `R2Storage` (boto3 S3-compatible) e estendemos o `MetaTemplateClient` com resumable upload. A tabela `meta_templates` ganha `components` (JSONB), `media_url`, `media_object_key`, `media_kind`, `status`, `category`, `rejection_reason`. Validação Meta vive em uma função pura compartilhada (Python) com mirror em TypeScript. ChatNexoClient ganha `header_link` + `header_kind` no `send_template`. Frontend ganha `MediaUploadField`, `VariablesEditor`, `ButtonsEditor` e validação inline.

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy + Alembic + boto3 (R2) + httpx; Next.js 15 + React + TypeScript + Tailwind; Cloudflare R2; Meta WhatsApp Cloud API v19.0.

**Spec:** `docs/superpowers/specs/2026-05-08-meta-templates-media-upload-design.md`

---

## File Structure

### Backend (apps/api/)

**Criar:**
- `apps/api/migrations/versions/f3a4b5c6d7e8_meta_templates_media.py` — migration
- `apps/api/src/shared/domain/ports/storage.py` — `StoragePort` + `StorageObject`
- `apps/api/src/shared/adapters/storage/__init__.py`
- `apps/api/src/shared/adapters/storage/r2.py` — `R2Storage` (boto3)
- `apps/api/src/shared/application/use_cases/meta_templates/__init__.py`
- `apps/api/src/shared/application/use_cases/meta_templates/validators.py`
- `apps/api/src/shared/application/use_cases/meta_templates/upload_template_media.py`
- `apps/api/src/shared/application/use_cases/meta_templates/create_template.py`
- `apps/api/src/shared/application/use_cases/meta_templates/list_templates.py`
- `apps/api/src/shared/application/use_cases/meta_templates/delete_template.py`
- `apps/api/src/shared/adapters/db/repositories/meta_template_repo.py`
- `apps/api/tests/unit/storage/test_r2.py`
- `apps/api/tests/unit/meta_templates/test_validators.py`
- `apps/api/tests/unit/meta_templates/test_create_template.py`
- `apps/api/tests/unit/meta_templates/test_delete_template.py`
- `apps/api/tests/unit/meta_templates/test_list_templates.py`
- `apps/api/tests/unit/meta/test_template_client_resumable.py`
- `apps/api/tests/integration/test_meta_templates_flow.py`

**Modificar:**
- `apps/api/.env.example` — adicionar `R2_*` e `META_APP_ID`
- `apps/api/src/shared/config/settings.py` — campos novos
- `apps/api/src/shared/adapters/db/models.py` — `MetaTemplateModel` ganha colunas novas
- `apps/api/src/shared/domain/entities/meta_template.py` (se existir; senão ajustar onde está)
- `apps/api/src/shared/adapters/meta/template_client.py` — resumable upload + delete
- `apps/api/src/shared/adapters/chatnexo/client.py` — `send_template` ganha `header_link`/`header_kind`
- `apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py` — passar header
- `apps/api/src/interface/http/routers/admin/meta_templates.py` — endpoints novos + reescrita
- `apps/api/src/interface/http/schemas/meta_templates.py` — schemas novos

### Frontend (apps/web/)

**Criar:**
- `apps/web/src/features/templates/validation.ts` — constantes + funções de validação
- `apps/web/src/features/templates/components/MediaUploadField.tsx`
- `apps/web/src/features/templates/components/VariablesEditor.tsx`
- `apps/web/src/features/templates/components/ButtonsEditor.tsx`
- `apps/web/src/features/templates/components/DeleteTemplateDialog.tsx`
- `apps/web/src/features/templates/hooks/useTemplateValidation.ts`

**Modificar:**
- `apps/web/src/features/templates/types.ts` — adicionar `UploadedMedia`, atualizar `CreateTemplateDto`, remover AUTHENTICATION
- `apps/web/src/lib/api.ts` — `uploadTemplateMedia`, `deleteMetaTemplate`
- `apps/web/src/features/templates/components/TemplateForm.tsx` — refatorar com validação inline + MediaUploadField
- `apps/web/src/features/templates/components/TemplatePreview.tsx` — preview com mídia
- `apps/web/src/app/(admin)/templates/page.tsx` — ação delete + badge de status

---

# Backend

---

### Task 1: Variáveis de ambiente e settings

**Files:**
- Modify: `apps/api/.env.example`
- Modify: `apps/api/src/shared/config/settings.py`

- [ ] **Step 1.1: Adicionar vars em `.env.example`**

Editar `apps/api/.env.example`, adicionar no final:

```
# --- Cloudflare R2 (template media storage) ---
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_BASE_URL=

# --- Meta WhatsApp App ID (resumable upload) ---
META_APP_ID=
```

> **Nota:** os valores reais ficam em `apps/api/.env.local` (gitignored). O usuário preenche localmente.

- [ ] **Step 1.2: Adicionar campos em `Settings`**

Em `apps/api/src/shared/config/settings.py`, dentro da classe `Settings` (BaseSettings), adicionar (mantendo ordem alfabética da seção que faz sentido):

```python
    # Cloudflare R2 (template media storage)
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str | None = None
    r2_public_base_url: str | None = None

    # Meta WhatsApp App ID (resumable upload)
    meta_app_id: str | None = None
```

Todos `None`-default para não quebrar dev local sem R2 (até a primeira tentativa de upload).

- [ ] **Step 1.3: Verificar que server inicia**

Run: `cd apps/api && uv run python -c "from shared.config.settings import get_settings; print(get_settings().r2_account_id)"`
Expected: `None`

- [ ] **Step 1.4: Commit**

```bash
git add apps/api/.env.example apps/api/src/shared/config/settings.py
git commit -m "feat(meta-templates): adicionar settings R2 e META_APP_ID"
```

---

### Task 2: Migration do schema `meta_templates`

**Files:**
- Create: `apps/api/migrations/versions/f3a4b5c6d7e8_meta_templates_media.py`

- [ ] **Step 2.1: Verificar head atual**

Run: `cd apps/api && uv run alembic heads`
Anote os heads atuais (provavelmente 2 heads por branches mergeados).

- [ ] **Step 2.2: Criar migration**

Run: `cd apps/api && uv run alembic revision -m "meta_templates media columns"`

Isso gera um arquivo em `apps/api/migrations/versions/`. Renomeie/edite o `down_revision` para apontar para o head correto da branch atual (verifique com `alembic heads`).

- [ ] **Step 2.3: Escrever upgrade/downgrade**

Substituir o conteúdo do arquivo gerado por:

```python
"""meta_templates media columns

Revision ID: f3a4b5c6d7e8
Revises: <PREENCHER COM HEAD ATUAL>
Create Date: 2026-05-08 ...

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f3a4b5c6d7e8"
down_revision = "<PREENCHER>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meta_templates",
        sa.Column("category", sa.String(32), nullable=False, server_default="UTILITY"),
    )
    op.add_column(
        "meta_templates",
        sa.Column(
            "components",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("meta_templates", sa.Column("media_url", sa.Text(), nullable=True))
    op.add_column("meta_templates", sa.Column("media_object_key", sa.Text(), nullable=True))
    op.add_column("meta_templates", sa.Column("media_kind", sa.String(16), nullable=True))
    op.add_column("meta_templates", sa.Column("media_sha256", sa.String(64), nullable=True))
    op.add_column("meta_templates", sa.Column("media_size", sa.BigInteger(), nullable=True))
    op.add_column(
        "meta_templates",
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
    )
    op.add_column("meta_templates", sa.Column("rejection_reason", sa.Text(), nullable=True))

    # Migra dados antigos
    op.execute("UPDATE meta_templates SET status = 'APPROVED' WHERE approved = TRUE")
    op.drop_column("meta_templates", "approved")

    # Constraints
    op.create_check_constraint(
        "chk_media_consistency",
        "meta_templates",
        "(media_url IS NULL AND media_kind IS NULL AND media_object_key IS NULL) OR "
        "(media_url IS NOT NULL AND media_kind IS NOT NULL AND media_object_key IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_meta_template_account_name", "meta_templates", ["account_id", "name"]
    )
    op.create_index("ix_meta_templates_status", "meta_templates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_meta_templates_status", table_name="meta_templates")
    op.drop_constraint("uq_meta_template_account_name", "meta_templates", type_="unique")
    op.drop_constraint("chk_media_consistency", "meta_templates", type_="check")
    op.add_column(
        "meta_templates",
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE meta_templates SET approved = TRUE WHERE status = 'APPROVED'")
    op.drop_column("meta_templates", "rejection_reason")
    op.drop_column("meta_templates", "status")
    op.drop_column("meta_templates", "media_size")
    op.drop_column("meta_templates", "media_sha256")
    op.drop_column("meta_templates", "media_kind")
    op.drop_column("meta_templates", "media_object_key")
    op.drop_column("meta_templates", "media_url")
    op.drop_column("meta_templates", "components")
    op.drop_column("meta_templates", "category")
```

- [ ] **Step 2.4: Aplicar migration**

Run: `cd apps/api && uv run alembic upgrade heads`
Expected: `INFO  [alembic.runtime.migration] Running upgrade ... -> f3a4b5c6d7e8, meta_templates media columns`

- [ ] **Step 2.5: Verificar schema no banco**

Run: `cd apps/api && uv run python -c "from sqlalchemy import create_engine, inspect; from shared.config.settings import get_settings; e=create_engine(get_settings().database_url.replace('+asyncpg','')); print([c['name'] for c in inspect(e).get_columns('meta_templates')])"`
Expected: lista contendo `category`, `components`, `media_url`, `media_object_key`, `media_kind`, `media_sha256`, `media_size`, `status`, `rejection_reason`, e SEM `approved`.

- [ ] **Step 2.6: Commit**

```bash
git add apps/api/migrations/versions/f3a4b5c6d7e8_meta_templates_media.py
git commit -m "feat(meta-templates): migration para componentes, mídia e status"
```

---

### Task 3: Atualizar `MetaTemplateModel` SQLAlchemy

**Files:**
- Modify: `apps/api/src/shared/adapters/db/models.py:217`

- [ ] **Step 3.1: Localizar a classe**

Abra `apps/api/src/shared/adapters/db/models.py` na linha 217 (`class MetaTemplateModel(Base)`).

- [ ] **Step 3.2: Substituir corpo da classe**

Substituir as colunas atuais por:

```python
class MetaTemplateModel(Base):
    __tablename__ = "meta_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"))
    name: Mapped[str] = mapped_column(String(512))
    meta_template_id: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32), default="UTILITY")
    language: Mapped[str] = mapped_column(String(16))
    components: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    variables_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    media_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    media_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("account_id", "name", name="uq_meta_template_account_name"),
        Index("ix_meta_templates_status", "status"),
    )
```

Garanta os imports no topo do arquivo: `BigInteger`, `Text`, `Index`, `UniqueConstraint`, `JSONB`, `func`, `DateTime`. Já existem na maioria dos casos.

- [ ] **Step 3.3: Rodar mypy**

Run: `cd apps/api && uv run mypy src/shared/adapters/db/models.py`
Expected: sem erros novos.

- [ ] **Step 3.4: Commit**

```bash
git add apps/api/src/shared/adapters/db/models.py
git commit -m "feat(meta-templates): atualizar MetaTemplateModel com colunas de mídia e status"
```

---

### Task 4: `StoragePort` (domain port)

**Files:**
- Create: `apps/api/src/shared/domain/ports/storage.py`
- Test: `apps/api/tests/unit/storage/__init__.py` (vazio) e `apps/api/tests/unit/storage/test_storage_port.py`

- [ ] **Step 4.1: Escrever teste do dataclass**

Criar `apps/api/tests/unit/storage/__init__.py` (arquivo vazio) e `apps/api/tests/unit/storage/test_storage_port.py`:

```python
from shared.domain.ports.storage import StorageObject


def test_storage_object_holds_metadata():
    obj = StorageObject(
        url="https://media.example.com/foo.jpg",
        object_key="accounts/abc/templates/foo.jpg",
        size=1024,
        sha256="deadbeef",
        content_type="image/jpeg",
    )
    assert obj.url == "https://media.example.com/foo.jpg"
    assert obj.object_key == "accounts/abc/templates/foo.jpg"
    assert obj.size == 1024
    assert obj.sha256 == "deadbeef"
    assert obj.content_type == "image/jpeg"
```

- [ ] **Step 4.2: Run test (deve falhar)**

Run: `cd apps/api && uv run pytest tests/unit/storage/test_storage_port.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'shared.domain.ports.storage'`

- [ ] **Step 4.3: Implementar port**

Criar `apps/api/src/shared/domain/ports/storage.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StorageObject:
    url: str
    object_key: str
    size: int
    sha256: str
    content_type: str


class StoragePort(Protocol):
    async def upload(
        self, *, key: str, data: bytes, content_type: str
    ) -> StorageObject: ...

    async def delete(self, *, key: str) -> None: ...

    async def head(self, *, key: str) -> StorageObject | None: ...
```

- [ ] **Step 4.4: Run test (deve passar)**

Run: `cd apps/api && uv run pytest tests/unit/storage/test_storage_port.py -v`
Expected: PASS

- [ ] **Step 4.5: Commit**

```bash
git add apps/api/src/shared/domain/ports/storage.py apps/api/tests/unit/storage/
git commit -m "feat(storage): adicionar StoragePort no domain"
```

---

### Task 5: `R2Storage` adapter

**Files:**
- Create: `apps/api/src/shared/adapters/storage/__init__.py` (vazio)
- Create: `apps/api/src/shared/adapters/storage/r2.py`
- Test: `apps/api/tests/unit/storage/test_r2.py`

- [ ] **Step 5.1: Adicionar `boto3` em pyproject**

Editar `apps/api/pyproject.toml`, dentro de `[project] dependencies`, adicionar:

```toml
"boto3>=1.34",
```

Run: `cd apps/api && uv sync`
Expected: instala boto3.

- [ ] **Step 5.2: Escrever teste com mock**

Criar `apps/api/tests/unit/storage/test_r2.py`:

```python
from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from shared.adapters.storage.r2 import R2Storage


@pytest.fixture
def r2() -> R2Storage:
    return R2Storage(
        account_id="acc123",
        access_key_id="key",
        secret_access_key="secret",
        bucket_name="my-bucket",
        public_base_url="https://media.example.com",
    )


@pytest.mark.asyncio
async def test_upload_returns_storage_object_with_sha256(r2: R2Storage) -> None:
    data = b"hello world"
    expected_sha = hashlib.sha256(data).hexdigest()

    mock_client = MagicMock()
    with patch.object(r2, "_client", mock_client):
        obj = await r2.upload(
            key="accounts/x/templates/foo.jpg",
            data=data,
            content_type="image/jpeg",
        )

    mock_client.put_object.assert_called_once()
    kwargs = mock_client.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "my-bucket"
    assert kwargs["Key"] == "accounts/x/templates/foo.jpg"
    assert kwargs["Body"] == data
    assert kwargs["ContentType"] == "image/jpeg"
    assert kwargs["Metadata"]["sha256"] == expected_sha

    assert obj.url == "https://media.example.com/accounts/x/templates/foo.jpg"
    assert obj.object_key == "accounts/x/templates/foo.jpg"
    assert obj.size == len(data)
    assert obj.sha256 == expected_sha
    assert obj.content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_delete_calls_boto(r2: R2Storage) -> None:
    mock_client = MagicMock()
    with patch.object(r2, "_client", mock_client):
        await r2.delete(key="accounts/x/templates/foo.jpg")

    mock_client.delete_object.assert_called_once_with(
        Bucket="my-bucket",
        Key="accounts/x/templates/foo.jpg",
    )


@pytest.mark.asyncio
async def test_head_returns_none_when_not_found(r2: R2Storage) -> None:
    from botocore.exceptions import ClientError

    mock_client = MagicMock()
    mock_client.head_object.side_effect = ClientError(
        {"Error": {"Code": "404"}}, "HeadObject"
    )
    with patch.object(r2, "_client", mock_client):
        obj = await r2.head(key="missing.jpg")

    assert obj is None
```

- [ ] **Step 5.3: Run tests (devem falhar)**

Run: `cd apps/api && uv run pytest tests/unit/storage/test_r2.py -v`
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 5.4: Implementar `R2Storage`**

Criar `apps/api/src/shared/adapters/storage/__init__.py` (vazio).

Criar `apps/api/src/shared/adapters/storage/r2.py`:

```python
from __future__ import annotations

import asyncio
import hashlib
from typing import Any

import boto3
import structlog
from botocore.exceptions import ClientError

from shared.domain.ports.storage import StorageObject

log = structlog.get_logger(__name__)


class R2Storage:
    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        public_base_url: str,
    ) -> None:
        self._bucket = bucket_name
        self._public_base_url = public_base_url.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    @classmethod
    def from_settings(cls, settings: Any) -> R2Storage:
        if not all([
            settings.r2_account_id,
            settings.r2_access_key_id,
            settings.r2_secret_access_key,
            settings.r2_bucket_name,
            settings.r2_public_base_url,
        ]):
            raise RuntimeError("R2 não configurado: defina R2_* em .env.local")
        return cls(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket_name=settings.r2_bucket_name,
            public_base_url=settings.r2_public_base_url,
        )

    async def upload(
        self, *, key: str, data: bytes, content_type: str
    ) -> StorageObject:
        sha256 = hashlib.sha256(data).hexdigest()
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": sha256},
        )
        log.info("r2_upload", key=key, size=len(data), sha256=sha256)
        return StorageObject(
            url=f"{self._public_base_url}/{key}",
            object_key=key,
            size=len(data),
            sha256=sha256,
            content_type=content_type,
        )

    async def delete(self, *, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._bucket, Key=key
        )
        log.info("r2_delete", key=key)

    async def head(self, *, key: str) -> StorageObject | None:
        try:
            resp = await asyncio.to_thread(
                self._client.head_object, Bucket=self._bucket, Key=key
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return None
            raise
        return StorageObject(
            url=f"{self._public_base_url}/{key}",
            object_key=key,
            size=int(resp.get("ContentLength", 0)),
            sha256=resp.get("Metadata", {}).get("sha256", ""),
            content_type=resp.get("ContentType", ""),
        )
```

- [ ] **Step 5.5: Run tests (devem passar)**

Run: `cd apps/api && uv run pytest tests/unit/storage/test_r2.py -v`
Expected: 3 PASS.

- [ ] **Step 5.6: Commit**

```bash
git add apps/api/src/shared/adapters/storage/ apps/api/tests/unit/storage/test_r2.py apps/api/pyproject.toml apps/api/uv.lock
git commit -m "feat(storage): adicionar R2Storage adapter (boto3 S3-compatible)"
```

---

### Task 6: Validators (regras Meta)

**Files:**
- Create: `apps/api/src/shared/application/use_cases/meta_templates/__init__.py` (vazio)
- Create: `apps/api/src/shared/application/use_cases/meta_templates/validators.py`
- Test: `apps/api/tests/unit/meta_templates/__init__.py` (vazio) e `apps/api/tests/unit/meta_templates/test_validators.py`

- [ ] **Step 6.1: Escrever testes (cobrir cada regra Meta)**

Criar `apps/api/tests/unit/meta_templates/__init__.py` (vazio).

Criar `apps/api/tests/unit/meta_templates/test_validators.py`:

```python
from __future__ import annotations

import pytest

from shared.application.use_cases.meta_templates.validators import (
    MEDIA_LIMITS,
    validate_media_file,
    validate_template_payload,
)


def _payload(**overrides):
    base = {
        "name": "boas_vindas",
        "category": "UTILITY",
        "language": "pt_BR",
        "components": [
            {"type": "BODY", "text": "Olá {{1}}!", "example": {"body_text": [["Fabio"]]}},
        ],
    }
    base.update(overrides)
    return base


def test_payload_minimo_valido():
    assert validate_template_payload(_payload()) == []


@pytest.mark.parametrize("name", ["AB", "Has Caps", "with-dash", "ç", ""])
def test_name_invalid(name):
    errors = validate_template_payload(_payload(name=name))
    assert any(e.code == "NAME_INVALID" for e in errors)


def test_name_valid_snake_case():
    assert validate_template_payload(_payload(name="meu_template_123")) == []


@pytest.mark.parametrize("category", ["AUTHENTICATION", "OTHER", ""])
def test_category_invalid(category):
    errors = validate_template_payload(_payload(category=category))
    assert any(e.code == "CATEGORY_INVALID" for e in errors)


def test_category_only_marketing_or_utility():
    assert validate_template_payload(_payload(category="MARKETING")) == []
    assert validate_template_payload(_payload(category="UTILITY")) == []


def test_body_required():
    errors = validate_template_payload(_payload(components=[]))
    assert any(e.code == "BODY_REQUIRED" for e in errors)


def test_body_too_long():
    long_body = "a" * 1025
    errors = validate_template_payload(_payload(components=[
        {"type": "BODY", "text": long_body},
    ]))
    assert any(e.code == "BODY_TEXT_TOO_LONG" for e in errors)


def test_body_variables_must_be_sequential():
    errors = validate_template_payload(_payload(components=[
        {"type": "BODY", "text": "Olá {{1}} e {{3}}",
         "example": {"body_text": [["a", "b"]]}},
    ]))
    assert any(e.code == "VARIABLES_NOT_SEQUENTIAL" for e in errors)


def test_body_variables_no_adjacent():
    errors = validate_template_payload(_payload(components=[
        {"type": "BODY", "text": "Olá {{1}}{{2}}",
         "example": {"body_text": [["a", "b"]]}},
    ]))
    assert any(e.code == "VARIABLES_ADJACENT" for e in errors)


def test_body_variable_missing_example():
    errors = validate_template_payload(_payload(components=[
        {"type": "BODY", "text": "Olá {{1}}"},
    ]))
    assert any(e.code == "VARIABLE_MISSING_EXAMPLE" for e in errors)


def test_header_text_too_long():
    errors = validate_template_payload(_payload(components=[
        {"type": "HEADER", "format": "TEXT", "text": "x" * 61},
        {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
    ]))
    assert any(e.code == "HEADER_TEXT_TOO_LONG" for e in errors)


def test_header_text_max_one_variable():
    errors = validate_template_payload(_payload(components=[
        {"type": "HEADER", "format": "TEXT", "text": "{{1}} e {{2}}",
         "example": {"header_text": ["a", "b"]}},
        {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
    ]))
    assert any(e.code == "HEADER_TOO_MANY_VARIABLES" for e in errors)


def test_footer_too_long():
    errors = validate_template_payload(_payload(components=[
        {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
        {"type": "FOOTER", "text": "x" * 61},
    ]))
    assert any(e.code == "FOOTER_TOO_LONG" for e in errors)


def test_footer_no_variables():
    errors = validate_template_payload(_payload(components=[
        {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
        {"type": "FOOTER", "text": "Vai {{1}}"},
    ]))
    assert any(e.code == "FOOTER_HAS_VARIABLES" for e in errors)


def test_button_label_too_long():
    errors = validate_template_payload(_payload(components=[
        {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
        {"type": "BUTTONS", "buttons": [
            {"type": "QUICK_REPLY", "text": "x" * 26},
        ]},
    ]))
    assert any(e.code == "BUTTON_LABEL_TOO_LONG" for e in errors)


def test_button_url_invalid():
    errors = validate_template_payload(_payload(components=[
        {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
        {"type": "BUTTONS", "buttons": [
            {"type": "URL", "text": "Ir", "url": "not-a-url"},
        ]},
    ]))
    assert any(e.code == "BUTTON_URL_INVALID" for e in errors)


def test_button_phone_e164_required():
    errors = validate_template_payload(_payload(components=[
        {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
        {"type": "BUTTONS", "buttons": [
            {"type": "PHONE_NUMBER", "text": "Liga", "phone_number": "11912345678"},
        ]},
    ]))
    assert any(e.code == "BUTTON_PHONE_INVALID" for e in errors)


def test_buttons_too_many_total():
    errors = validate_template_payload(_payload(components=[
        {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
        {"type": "BUTTONS", "buttons": [
            {"type": "QUICK_REPLY", "text": f"q{i}"} for i in range(11)
        ]},
    ]))
    assert any(e.code == "BUTTONS_TOO_MANY" for e in errors)


def test_buttons_too_many_cta():
    errors = validate_template_payload(_payload(components=[
        {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
        {"type": "BUTTONS", "buttons": [
            {"type": "URL", "text": "a", "url": "https://a.com"},
            {"type": "URL", "text": "b", "url": "https://b.com"},
            {"type": "URL", "text": "c", "url": "https://c.com"},
        ]},
    ]))
    assert any(e.code == "BUTTONS_TOO_MANY_CTA" for e in errors)


def test_validate_media_file_size():
    err = validate_media_file(kind="IMAGE", size=10 * 1024 * 1024, mime="image/jpeg")
    assert err is not None
    assert err.code == "MEDIA_SIZE_EXCEEDED"


def test_validate_media_file_mime():
    err = validate_media_file(kind="IMAGE", size=1024, mime="image/gif")
    assert err is not None
    assert err.code == "MEDIA_TYPE_INVALID"


def test_validate_media_file_ok():
    assert validate_media_file(kind="IMAGE", size=1024, mime="image/jpeg") is None


def test_media_limits_constants_match_spec():
    assert MEDIA_LIMITS["IMAGE"]["max_bytes"] == 5 * 1024 * 1024
    assert MEDIA_LIMITS["VIDEO"]["max_bytes"] == 16 * 1024 * 1024
    assert MEDIA_LIMITS["DOCUMENT"]["max_bytes"] == 100 * 1024 * 1024
```

- [ ] **Step 6.2: Run tests (devem falhar)**

Run: `cd apps/api && uv run pytest tests/unit/meta_templates/test_validators.py -v`
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 6.3: Implementar validators**

Criar `apps/api/src/shared/application/use_cases/meta_templates/__init__.py` (vazio).

Criar `apps/api/src/shared/application/use_cases/meta_templates/validators.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

NAME_REGEX = re.compile(r"^[a-z0-9_]{3,512}$")
PHONE_E164_REGEX = re.compile(r"^\+\d{8,15}$")
VARIABLE_REGEX = re.compile(r"\{\{(\d+)\}\}")
ADJACENT_VAR_REGEX = re.compile(r"\}\}\{\{")

ALLOWED_CATEGORIES = {"MARKETING", "UTILITY"}
ALLOWED_LANGUAGES = {"pt_BR", "en_US"}
ALLOWED_HEADER_FORMATS = {"TEXT", "IMAGE", "VIDEO", "DOCUMENT"}

HEADER_TEXT_MAX = 60
BODY_TEXT_MAX = 1024
FOOTER_MAX = 60
BUTTON_LABEL_MAX = 25
BUTTON_URL_MAX = 2000
BUTTONS_TOTAL_MAX = 10
CTA_BUTTONS_MAX = 2

MEDIA_LIMITS: dict[str, dict[str, Any]] = {
    "IMAGE":    {"mimes": ["image/jpeg", "image/png"],          "max_bytes": 5  * 1024 * 1024},
    "VIDEO":    {"mimes": ["video/mp4"],                          "max_bytes": 16 * 1024 * 1024},
    "DOCUMENT": {"mimes": ["application/pdf"],                    "max_bytes": 100 * 1024 * 1024},
}


@dataclass(frozen=True)
class ValidationError:
    field: str
    code: str
    message: str


def _err(field: str, code: str, message: str) -> ValidationError:
    return ValidationError(field=field, code=code, message=message)


def _detect_variables(text: str) -> list[int]:
    return [int(m) for m in VARIABLE_REGEX.findall(text)]


def _validate_body(idx: int, c: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    text = c.get("text") or ""
    if len(text) > BODY_TEXT_MAX:
        errors.append(_err(
            f"components[{idx}].text", "BODY_TEXT_TOO_LONG",
            f"Body excede {BODY_TEXT_MAX} caracteres",
        ))
    if not text.strip():
        errors.append(_err(f"components[{idx}].text", "BODY_REQUIRED", "Body é obrigatório"))
    if ADJACENT_VAR_REGEX.search(text):
        errors.append(_err(
            f"components[{idx}].text", "VARIABLES_ADJACENT",
            "Variáveis não podem ser adjacentes (ex.: {{1}}{{2}})",
        ))
    vars_found = _detect_variables(text)
    if vars_found:
        unique = sorted(set(vars_found))
        if unique != list(range(1, len(unique) + 1)):
            errors.append(_err(
                f"components[{idx}].text", "VARIABLES_NOT_SEQUENTIAL",
                "Variáveis devem ser sequenciais a partir de {{1}}",
            ))
        examples = ((c.get("example") or {}).get("body_text") or [[]])[0]
        if len(examples) < len(unique):
            errors.append(_err(
                f"components[{idx}].example", "VARIABLE_MISSING_EXAMPLE",
                "Cada variável precisa de um exemplo em example.body_text",
            ))
    return errors


def _validate_header(idx: int, c: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    fmt = c.get("format")
    if fmt not in ALLOWED_HEADER_FORMATS:
        errors.append(_err(
            f"components[{idx}].format", "HEADER_FORMAT_INVALID",
            f"Header format inválido (esperado um de {sorted(ALLOWED_HEADER_FORMATS)})",
        ))
        return errors
    if fmt == "TEXT":
        text = c.get("text") or ""
        if len(text) > HEADER_TEXT_MAX:
            errors.append(_err(
                f"components[{idx}].text", "HEADER_TEXT_TOO_LONG",
                f"Header excede {HEADER_TEXT_MAX} caracteres",
            ))
        vars_found = _detect_variables(text)
        if len(set(vars_found)) > 1:
            errors.append(_err(
                f"components[{idx}].text", "HEADER_TOO_MANY_VARIABLES",
                "Header text aceita no máximo 1 variável",
            ))
    return errors


def _validate_footer(idx: int, c: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    text = c.get("text") or ""
    if len(text) > FOOTER_MAX:
        errors.append(_err(
            f"components[{idx}].text", "FOOTER_TOO_LONG",
            f"Footer excede {FOOTER_MAX} caracteres",
        ))
    if VARIABLE_REGEX.search(text):
        errors.append(_err(
            f"components[{idx}].text", "FOOTER_HAS_VARIABLES",
            "Footer não pode conter variáveis",
        ))
    return errors


def _validate_buttons(idx: int, c: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    buttons = c.get("buttons") or []
    if len(buttons) > BUTTONS_TOTAL_MAX:
        errors.append(_err(
            f"components[{idx}].buttons", "BUTTONS_TOO_MANY",
            f"Total de botões excede {BUTTONS_TOTAL_MAX}",
        ))
    cta_count = sum(1 for b in buttons if b.get("type") in {"URL", "PHONE_NUMBER"})
    if cta_count > CTA_BUTTONS_MAX:
        errors.append(_err(
            f"components[{idx}].buttons", "BUTTONS_TOO_MANY_CTA",
            f"Botões CTA (URL/PHONE) excedem {CTA_BUTTONS_MAX}",
        ))
    for j, b in enumerate(buttons):
        label = b.get("text") or ""
        if len(label) > BUTTON_LABEL_MAX:
            errors.append(_err(
                f"components[{idx}].buttons[{j}].text", "BUTTON_LABEL_TOO_LONG",
                f"Label do botão excede {BUTTON_LABEL_MAX} caracteres",
            ))
        if b.get("type") == "URL":
            url = b.get("url") or ""
            if len(url) > BUTTON_URL_MAX:
                errors.append(_err(
                    f"components[{idx}].buttons[{j}].url", "BUTTON_URL_TOO_LONG",
                    f"URL do botão excede {BUTTON_URL_MAX} caracteres",
                ))
            try:
                parsed = urlparse(url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ValueError
            except Exception:
                errors.append(_err(
                    f"components[{idx}].buttons[{j}].url", "BUTTON_URL_INVALID",
                    "URL inválida",
                ))
        if b.get("type") == "PHONE_NUMBER":
            phone = b.get("phone_number") or ""
            if not PHONE_E164_REGEX.match(phone):
                errors.append(_err(
                    f"components[{idx}].buttons[{j}].phone_number", "BUTTON_PHONE_INVALID",
                    "Telefone deve estar em E.164 (ex.: +5511999999999)",
                ))
    return errors


def validate_template_payload(payload: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []

    name = payload.get("name") or ""
    if not NAME_REGEX.match(name):
        errors.append(_err("name", "NAME_INVALID",
            "Nome deve ser snake_case (a-z, 0-9, _) com 3-512 caracteres"))

    category = payload.get("category")
    if category not in ALLOWED_CATEGORIES:
        errors.append(_err("category", "CATEGORY_INVALID",
            f"Categoria deve ser uma de {sorted(ALLOWED_CATEGORIES)}"))

    language = payload.get("language")
    if language not in ALLOWED_LANGUAGES:
        errors.append(_err("language", "LANGUAGE_INVALID",
            f"Idioma deve ser um de {sorted(ALLOWED_LANGUAGES)}"))

    components = payload.get("components") or []
    has_body = False
    for i, c in enumerate(components):
        ctype = c.get("type")
        if ctype == "HEADER":
            errors.extend(_validate_header(i, c))
        elif ctype == "BODY":
            has_body = True
            errors.extend(_validate_body(i, c))
        elif ctype == "FOOTER":
            errors.extend(_validate_footer(i, c))
        elif ctype == "BUTTONS":
            errors.extend(_validate_buttons(i, c))

    if not has_body:
        errors.append(_err("components", "BODY_REQUIRED", "Body é obrigatório"))

    return errors


def validate_media_file(*, kind: str, size: int, mime: str) -> ValidationError | None:
    limits = MEDIA_LIMITS.get(kind)
    if limits is None:
        return _err("media.kind", "MEDIA_KIND_INVALID",
            f"Kind deve ser um de {list(MEDIA_LIMITS.keys())}")
    if mime not in limits["mimes"]:
        return _err("media.mime", "MEDIA_TYPE_INVALID",
            f"MIME inválido para {kind} (esperado: {limits['mimes']})")
    if size > limits["max_bytes"]:
        max_mb = limits["max_bytes"] // (1024 * 1024)
        return _err("media.size", "MEDIA_SIZE_EXCEEDED",
            f"Arquivo excede {max_mb}MB para {kind}")
    return None
```

- [ ] **Step 6.4: Run tests (devem passar)**

Run: `cd apps/api && uv run pytest tests/unit/meta_templates/test_validators.py -v`
Expected: todos os ~25 testes PASS.

- [ ] **Step 6.5: Commit**

```bash
git add apps/api/src/shared/application/use_cases/meta_templates/ apps/api/tests/unit/meta_templates/
git commit -m "feat(meta-templates): adicionar validators com regras Meta completas"
```

---

### Task 7: Estender `MetaTemplateClient` (resumable upload + delete)

**Files:**
- Modify: `apps/api/src/shared/adapters/meta/template_client.py`
- Test: `apps/api/tests/unit/meta/test_template_client_resumable.py`

- [ ] **Step 7.1: Escrever testes do resumable upload**

Criar `apps/api/tests/unit/meta/__init__.py` se não existir (vazio).

Criar `apps/api/tests/unit/meta/test_template_client_resumable.py`:

```python
from __future__ import annotations

import httpx
import pytest

from shared.adapters.meta.template_client import MetaTemplateClient


@pytest.mark.asyncio
async def test_create_resumable_upload_session_returns_id(monkeypatch):
    client = MetaTemplateClient(api_key="k")

    async def fake_post(self, url, *args, **kwargs):
        assert "/app123/uploads" in url
        assert kwargs["params"]["file_length"] == 1024
        assert kwargs["params"]["file_type"] == "image/jpeg"
        return httpx.Response(200, json={"id": "upload:abc"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    session = await client.create_resumable_upload_session(
        app_id="app123", file_size=1024, file_type="image/jpeg"
    )
    assert session == "upload:abc"


@pytest.mark.asyncio
async def test_upload_media_resumable_returns_handle(monkeypatch):
    client = MetaTemplateClient(api_key="k")

    async def fake_post(self, url, *args, **kwargs):
        assert "/upload:abc" in url
        assert kwargs["headers"]["file_offset"] == "0"
        assert kwargs["content"] == b"BYTES"
        return httpx.Response(200, json={"h": "4::aW1n=="})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    handle = await client.upload_media_resumable(session_id="upload:abc", data=b"BYTES")
    assert handle == "4::aW1n=="


@pytest.mark.asyncio
async def test_delete_template_calls_delete(monkeypatch):
    client = MetaTemplateClient(api_key="k")
    captured: dict = {}

    async def fake_delete(self, url, *args, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        return httpx.Response(200, json={"success": True})

    monkeypatch.setattr(httpx.AsyncClient, "delete", fake_delete)
    await client.delete_template(waba_id="waba1", name="my_tpl")
    assert "waba1/message_templates" in captured["url"]
    assert captured["params"]["name"] == "my_tpl"
```

- [ ] **Step 7.2: Run tests (devem falhar)**

Run: `cd apps/api && uv run pytest tests/unit/meta/test_template_client_resumable.py -v`
Expected: FAIL — métodos não existem.

- [ ] **Step 7.3: Adicionar métodos no client**

Em `apps/api/src/shared/adapters/meta/template_client.py`, adicionar ao final da classe `MetaTemplateClient`:

```python
    async def create_resumable_upload_session(
        self, *, app_id: str, file_size: int, file_type: str
    ) -> str:
        url = f"{_BASE_URL}/{app_id}/uploads"
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                url,
                params={"file_length": file_size, "file_type": file_type},
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=15,
            )
        resp.raise_for_status()
        data = resp.json()
        session_id = data.get("id", "")
        if not session_id:
            raise RuntimeError(f"Meta upload session sem id: {data}")
        return session_id

    async def upload_media_resumable(
        self, *, session_id: str, data: bytes
    ) -> str:
        url = f"{_BASE_URL}/{session_id}"
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                url,
                content=data,
                headers={
                    "Authorization": f"OAuth {self._api_key}",
                    "file_offset": "0",
                },
                timeout=60,
            )
        resp.raise_for_status()
        body = resp.json()
        handle = body.get("h", "")
        if not handle:
            raise RuntimeError(f"Meta upload sem handle: {body}")
        return handle

    async def delete_template(self, *, waba_id: str, name: str) -> None:
        url = f"{_BASE_URL}/{waba_id}/message_templates"
        async with httpx.AsyncClient() as http:
            resp = await http.delete(
                url,
                params={"name": name},
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=15,
            )
        resp.raise_for_status()
```

> **Nota:** O endpoint resumable upload usa `OAuth` ao invés de `Bearer` no header — é assim que a Meta documenta a Cloud API para uploads.

- [ ] **Step 7.4: Run tests (devem passar)**

Run: `cd apps/api && uv run pytest tests/unit/meta/test_template_client_resumable.py -v`
Expected: 3 PASS.

- [ ] **Step 7.5: Commit**

```bash
git add apps/api/src/shared/adapters/meta/template_client.py apps/api/tests/unit/meta/
git commit -m "feat(meta-templates): adicionar resumable upload e delete no MetaTemplateClient"
```

---

### Task 8: Repository de `MetaTemplate`

**Files:**
- Create: `apps/api/src/shared/adapters/db/repositories/meta_template_repo.py`

- [ ] **Step 8.1: Implementar repo**

Criar `apps/api/src/shared/adapters/db/repositories/meta_template_repo.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import MetaTemplateModel


class MetaTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_account(self, account_id: UUID) -> list[MetaTemplateModel]:
        result = await self._session.execute(
            select(MetaTemplateModel)
            .where(MetaTemplateModel.account_id == account_id)
            .order_by(MetaTemplateModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, template_id: UUID, account_id: UUID) -> MetaTemplateModel | None:
        result = await self._session.execute(
            select(MetaTemplateModel)
            .where(MetaTemplateModel.id == template_id)
            .where(MetaTemplateModel.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str, account_id: UUID) -> MetaTemplateModel | None:
        result = await self._session.execute(
            select(MetaTemplateModel)
            .where(MetaTemplateModel.name == name)
            .where(MetaTemplateModel.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def create(self, **fields: Any) -> MetaTemplateModel:
        model = MetaTemplateModel(**fields)
        self._session.add(model)
        await self._session.flush()
        return model

    async def update_status(
        self,
        template_id: UUID,
        *,
        status: str,
        rejection_reason: str | None = None,
    ) -> None:
        model = await self._session.get(MetaTemplateModel, template_id)
        if not model:
            return
        model.status = status
        model.rejection_reason = rejection_reason
        model.last_synced_at = datetime.now(timezone.utc)
        await self._session.flush()

    async def delete(self, template_id: UUID) -> None:
        model = await self._session.get(MetaTemplateModel, template_id)
        if model:
            await self._session.delete(model)
            await self._session.flush()

    async def find_pending(self, account_id: UUID) -> list[MetaTemplateModel]:
        result = await self._session.execute(
            select(MetaTemplateModel)
            .where(MetaTemplateModel.account_id == account_id)
            .where(MetaTemplateModel.status == "PENDING")
        )
        return list(result.scalars().all())
```

- [ ] **Step 8.2: Verificar que importa**

Run: `cd apps/api && uv run python -c "from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository"`
Expected: sem erro.

- [ ] **Step 8.3: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/meta_template_repo.py
git commit -m "feat(meta-templates): adicionar MetaTemplateRepository"
```

---

### Task 9: Use case `upload_template_media`

**Files:**
- Create: `apps/api/src/shared/application/use_cases/meta_templates/upload_template_media.py`
- Test: `apps/api/tests/unit/meta_templates/test_upload_template_media.py`

- [ ] **Step 9.1: Escrever teste**

Criar `apps/api/tests/unit/meta_templates/test_upload_template_media.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from shared.application.use_cases.meta_templates.upload_template_media import (
    UploadTemplateMedia,
    UploadTemplateMediaInput,
)
from shared.domain.ports.storage import StorageObject


@pytest.mark.asyncio
async def test_upload_returns_metadata():
    storage = AsyncMock()
    storage.upload.return_value = StorageObject(
        url="https://media.example.com/accounts/abc/templates/xxx.jpg",
        object_key="accounts/abc/templates/xxx.jpg",
        size=1024,
        sha256="deadbeef",
        content_type="image/jpeg",
    )

    use_case = UploadTemplateMedia(storage=storage)
    out = await use_case.execute(UploadTemplateMediaInput(
        account_id=uuid4(),
        kind="IMAGE",
        data=b"x" * 1024,
        mime="image/jpeg",
        original_filename="photo.jpg",
    ))

    storage.upload.assert_awaited_once()
    call = storage.upload.await_args.kwargs
    assert call["key"].startswith("accounts/")
    assert call["key"].endswith(".jpg")
    assert call["content_type"] == "image/jpeg"

    assert out.media_url.startswith("https://media.example.com/")
    assert out.media_kind == "IMAGE"
    assert out.size == 1024


@pytest.mark.asyncio
async def test_upload_rejects_oversize():
    storage = AsyncMock()
    use_case = UploadTemplateMedia(storage=storage)
    with pytest.raises(ValueError, match="MEDIA_SIZE_EXCEEDED"):
        await use_case.execute(UploadTemplateMediaInput(
            account_id=uuid4(),
            kind="IMAGE",
            data=b"x" * (10 * 1024 * 1024),
            mime="image/jpeg",
            original_filename="huge.jpg",
        ))
    storage.upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_rejects_wrong_mime():
    storage = AsyncMock()
    use_case = UploadTemplateMedia(storage=storage)
    with pytest.raises(ValueError, match="MEDIA_TYPE_INVALID"):
        await use_case.execute(UploadTemplateMediaInput(
            account_id=uuid4(),
            kind="IMAGE",
            data=b"x" * 1024,
            mime="image/gif",
            original_filename="anim.gif",
        ))
```

- [ ] **Step 9.2: Run tests (devem falhar)**

Run: `cd apps/api && uv run pytest tests/unit/meta_templates/test_upload_template_media.py -v`
Expected: FAIL.

- [ ] **Step 9.3: Implementar use case**

Criar `apps/api/src/shared/application/use_cases/meta_templates/upload_template_media.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID, uuid4

from shared.application.use_cases.meta_templates.validators import validate_media_file
from shared.domain.ports.storage import StoragePort

MediaKind = Literal["IMAGE", "VIDEO", "DOCUMENT"]


@dataclass(frozen=True)
class UploadTemplateMediaInput:
    account_id: UUID
    kind: MediaKind
    data: bytes
    mime: str
    original_filename: str


@dataclass(frozen=True)
class UploadTemplateMediaOutput:
    media_url: str
    media_object_key: str
    media_kind: MediaKind
    sha256: str
    size: int


_EXT_BY_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "video/mp4": "mp4",
    "application/pdf": "pdf",
}


class UploadTemplateMedia:
    def __init__(self, *, storage: StoragePort) -> None:
        self._storage = storage

    async def execute(self, payload: UploadTemplateMediaInput) -> UploadTemplateMediaOutput:
        err = validate_media_file(kind=payload.kind, size=len(payload.data), mime=payload.mime)
        if err:
            raise ValueError(err.code)

        ext = _EXT_BY_MIME.get(payload.mime) or PurePosixPath(payload.original_filename).suffix.lstrip(".") or "bin"
        key = f"accounts/{payload.account_id}/templates/{uuid4()}.{ext}"

        obj = await self._storage.upload(
            key=key, data=payload.data, content_type=payload.mime
        )
        return UploadTemplateMediaOutput(
            media_url=obj.url,
            media_object_key=obj.object_key,
            media_kind=payload.kind,
            sha256=obj.sha256,
            size=obj.size,
        )
```

- [ ] **Step 9.4: Run tests (devem passar)**

Run: `cd apps/api && uv run pytest tests/unit/meta_templates/test_upload_template_media.py -v`
Expected: 3 PASS.

- [ ] **Step 9.5: Commit**

```bash
git add apps/api/src/shared/application/use_cases/meta_templates/upload_template_media.py apps/api/tests/unit/meta_templates/test_upload_template_media.py
git commit -m "feat(meta-templates): use case upload_template_media com validação"
```

---

### Task 10: Use case `create_template`

**Files:**
- Create: `apps/api/src/shared/application/use_cases/meta_templates/create_template.py`
- Test: `apps/api/tests/unit/meta_templates/test_create_template.py`

- [ ] **Step 10.1: Escrever teste**

Criar `apps/api/tests/unit/meta_templates/test_create_template.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from shared.application.use_cases.meta_templates.create_template import (
    CreateTemplate,
    CreateTemplateInput,
)


@pytest.mark.asyncio
async def test_create_template_without_media():
    repo = AsyncMock()
    meta_client = AsyncMock()
    storage = AsyncMock()
    repo.create.return_value = AsyncMock(id=uuid4())
    meta_client.create_template.return_value = AsyncMock(
        id="meta_id_123", status="PENDING"
    )

    use_case = CreateTemplate(repo=repo, meta_client=meta_client, storage=storage)

    out = await use_case.execute(CreateTemplateInput(
        account_id=uuid4(),
        waba_id="waba1",
        app_id="app1",
        name="boas_vindas",
        category="UTILITY",
        language="pt_BR",
        components=[
            {"type": "BODY", "text": "Olá {{1}}", "example": {"body_text": [["Fabio"]]}},
        ],
        media_url=None,
        media_object_key=None,
        media_kind=None,
    ))

    meta_client.create_resumable_upload_session.assert_not_awaited()
    storage.delete.assert_not_awaited()
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_template_with_media_does_resumable_upload():
    repo = AsyncMock()
    meta_client = AsyncMock()
    storage = AsyncMock()
    meta_client.create_resumable_upload_session.return_value = "upload:abc"
    meta_client.upload_media_resumable.return_value = "4::HANDLE=="
    meta_client.create_template.return_value = AsyncMock(id="m_id", status="PENDING")

    fake_resp = AsyncMock()
    fake_resp.content = b"FAKEBYTES"
    fake_resp.raise_for_status.return_value = None

    fake_client = AsyncMock()
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = None
    fake_client.get.return_value = fake_resp

    with patch("shared.application.use_cases.meta_templates.create_template.httpx.AsyncClient", return_value=fake_client):
        use_case = CreateTemplate(repo=repo, meta_client=meta_client, storage=storage)
        await use_case.execute(CreateTemplateInput(
            account_id=uuid4(),
            waba_id="waba1",
            app_id="app1",
            name="com_imagem",
            category="UTILITY",
            language="pt_BR",
            components=[
                {"type": "HEADER", "format": "IMAGE", "example": {"header_handle": []}},
                {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
            ],
            media_url="https://media.example.com/x.jpg",
            media_object_key="accounts/x/templates/x.jpg",
            media_kind="IMAGE",
        ))

    meta_client.create_resumable_upload_session.assert_awaited_once()
    meta_client.upload_media_resumable.assert_awaited_once()
    args = meta_client.create_template.await_args.args
    payload = args[1]
    header = next(c for c in payload.components if c["type"] == "HEADER")
    assert header["example"]["header_handle"] == ["4::HANDLE=="]


@pytest.mark.asyncio
async def test_create_template_validation_failure_blocks_meta_call():
    repo = AsyncMock()
    meta_client = AsyncMock()
    storage = AsyncMock()
    use_case = CreateTemplate(repo=repo, meta_client=meta_client, storage=storage)

    with pytest.raises(ValueError, match="VALIDATION_FAILED"):
        await use_case.execute(CreateTemplateInput(
            account_id=uuid4(), waba_id="w", app_id="a",
            name="BadName!",
            category="UTILITY", language="pt_BR",
            components=[{"type": "BODY", "text": "ok", "example": {"body_text": [[]]}}],
            media_url=None, media_object_key=None, media_kind=None,
        ))
    meta_client.create_template.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_template_meta_failure_cleans_r2():
    repo = AsyncMock()
    meta_client = AsyncMock()
    storage = AsyncMock()
    meta_client.create_resumable_upload_session.side_effect = RuntimeError("meta down")

    fake_resp = AsyncMock()
    fake_resp.content = b"BYTES"
    fake_resp.raise_for_status.return_value = None
    fake_client = AsyncMock()
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = None
    fake_client.get.return_value = fake_resp

    with patch("shared.application.use_cases.meta_templates.create_template.httpx.AsyncClient", return_value=fake_client):
        use_case = CreateTemplate(repo=repo, meta_client=meta_client, storage=storage)
        with pytest.raises(RuntimeError, match="meta down"):
            await use_case.execute(CreateTemplateInput(
                account_id=uuid4(), waba_id="w", app_id="a",
                name="ok_name",
                category="UTILITY", language="pt_BR",
                components=[
                    {"type": "HEADER", "format": "IMAGE", "example": {"header_handle": []}},
                    {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
                ],
                media_url="https://x/x.jpg",
                media_object_key="accounts/x/templates/x.jpg",
                media_kind="IMAGE",
            ))

    storage.delete.assert_awaited_once_with(key="accounts/x/templates/x.jpg")
```

- [ ] **Step 10.2: Run tests (devem falhar)**

Run: `cd apps/api && uv run pytest tests/unit/meta_templates/test_create_template.py -v`
Expected: FAIL.

- [ ] **Step 10.3: Implementar use case**

Criar `apps/api/src/shared/application/use_cases/meta_templates/create_template.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

import httpx
import structlog

from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository
from shared.adapters.meta.template_client import MetaTemplateClient
from shared.application.use_cases.meta_templates.validators import (
    validate_template_payload,
)
from shared.domain.ports.meta_template import CreateTemplatePayload
from shared.domain.ports.storage import StoragePort

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class CreateTemplateInput:
    account_id: UUID
    waba_id: str
    app_id: str
    name: str
    category: str
    language: str
    components: list[dict[str, Any]]
    media_url: str | None
    media_object_key: str | None
    media_kind: Literal["IMAGE", "VIDEO", "DOCUMENT"] | None


_MIME_BY_KIND = {
    "IMAGE": "image/jpeg",
    "VIDEO": "video/mp4",
    "DOCUMENT": "application/pdf",
}


class CreateTemplate:
    def __init__(
        self,
        *,
        repo: MetaTemplateRepository,
        meta_client: MetaTemplateClient,
        storage: StoragePort,
    ) -> None:
        self._repo = repo
        self._meta = meta_client
        self._storage = storage

    async def execute(self, payload: CreateTemplateInput) -> Any:
        # 1. Validate
        errors = validate_template_payload({
            "name": payload.name,
            "category": payload.category,
            "language": payload.language,
            "components": payload.components,
        })
        if errors:
            raise ValueError(f"VALIDATION_FAILED: {[e.code for e in errors]}")

        components = [dict(c) for c in payload.components]

        # 2. Resumable upload Meta (se houver mídia)
        if payload.media_url and payload.media_object_key and payload.media_kind:
            try:
                async with httpx.AsyncClient(timeout=60) as http:
                    r = await http.get(payload.media_url)
                    r.raise_for_status()
                    media_bytes = r.content

                session_id = await self._meta.create_resumable_upload_session(
                    app_id=payload.app_id,
                    file_size=len(media_bytes),
                    file_type=_MIME_BY_KIND[payload.media_kind],
                )
                handle = await self._meta.upload_media_resumable(
                    session_id=session_id, data=media_bytes
                )
                # Injetar handle no header
                for c in components:
                    if c.get("type") == "HEADER":
                        c.setdefault("example", {})
                        c["example"]["header_handle"] = [handle]
                        break
            except Exception:
                # Limpa R2 pra não deixar órfão
                log.warning("meta_create_failed_cleaning_r2", key=payload.media_object_key)
                try:
                    await self._storage.delete(key=payload.media_object_key)
                except Exception:
                    log.error("r2_cleanup_failed", key=payload.media_object_key)
                raise

        # 3. Criar template na Meta
        try:
            meta_template = await self._meta.create_template(
                payload.waba_id,
                CreateTemplatePayload(
                    name=payload.name,
                    category=payload.category,
                    language=payload.language,
                    components=components,
                ),
            )
        except Exception:
            if payload.media_object_key:
                try:
                    await self._storage.delete(key=payload.media_object_key)
                except Exception:
                    log.error("r2_cleanup_failed", key=payload.media_object_key)
            raise

        # 4. Persistir
        record = await self._repo.create(
            account_id=payload.account_id,
            name=payload.name,
            meta_template_id=meta_template.id,
            category=payload.category,
            language=payload.language,
            components=components,
            variables_schema={},
            media_url=payload.media_url,
            media_object_key=payload.media_object_key,
            media_kind=payload.media_kind,
            status=meta_template.status or "PENDING",
        )
        log.info(
            "meta_template_created",
            template_id=str(record.id),
            meta_template_id=meta_template.id,
            has_media=bool(payload.media_url),
        )
        return record
```

- [ ] **Step 10.4: Run tests (devem passar)**

Run: `cd apps/api && uv run pytest tests/unit/meta_templates/test_create_template.py -v`
Expected: 4 PASS.

- [ ] **Step 10.5: Commit**

```bash
git add apps/api/src/shared/application/use_cases/meta_templates/create_template.py apps/api/tests/unit/meta_templates/test_create_template.py
git commit -m "feat(meta-templates): use case create_template com resumable upload Meta"
```

---

### Task 11: Use case `list_templates` com sync de PENDING

**Files:**
- Create: `apps/api/src/shared/application/use_cases/meta_templates/list_templates.py`
- Test: `apps/api/tests/unit/meta_templates/test_list_templates.py`

- [ ] **Step 11.1: Escrever teste**

Criar `apps/api/tests/unit/meta_templates/test_list_templates.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.application.use_cases.meta_templates.list_templates import ListTemplates


@pytest.mark.asyncio
async def test_list_returns_all_when_no_pending():
    repo = AsyncMock()
    meta = AsyncMock()
    repo.list_by_account.return_value = [
        MagicMock(id=uuid4(), name="ok", status="APPROVED"),
    ]
    repo.find_pending.return_value = []

    out = await ListTemplates(repo=repo, meta_client=meta).execute(
        account_id=uuid4(), waba_id="w"
    )

    assert len(out) == 1
    meta.list_templates.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_syncs_pending():
    repo = AsyncMock()
    meta = AsyncMock()
    pending_id = uuid4()
    pending = MagicMock(id=pending_id, name="pend", status="PENDING")
    repo.list_by_account.return_value = [pending]
    repo.find_pending.return_value = [pending]

    meta.list_templates.return_value = [
        MagicMock(name="pend", status="APPROVED", rejection_reason=None),
    ]

    await ListTemplates(repo=repo, meta_client=meta).execute(
        account_id=uuid4(), waba_id="w"
    )

    meta.list_templates.assert_awaited_once_with("w")
    repo.update_status.assert_awaited_once_with(
        pending_id, status="APPROVED", rejection_reason=None
    )
```

- [ ] **Step 11.2: Run tests (devem falhar)**

Run: `cd apps/api && uv run pytest tests/unit/meta_templates/test_list_templates.py -v`
Expected: FAIL.

- [ ] **Step 11.3: Implementar**

Criar `apps/api/src/shared/application/use_cases/meta_templates/list_templates.py`:

```python
from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository
from shared.adapters.meta.template_client import MetaTemplateClient

log = structlog.get_logger(__name__)


class ListTemplates:
    def __init__(
        self,
        *,
        repo: MetaTemplateRepository,
        meta_client: MetaTemplateClient,
    ) -> None:
        self._repo = repo
        self._meta = meta_client

    async def execute(self, *, account_id: UUID, waba_id: str) -> list[Any]:
        pending = await self._repo.find_pending(account_id)
        if pending and waba_id:
            try:
                meta_list = await self._meta.list_templates(waba_id)
            except Exception as exc:
                log.warning("meta_template_sync_failed", error=str(exc))
            else:
                by_name = {t.name: t for t in meta_list}
                for record in pending:
                    found = by_name.get(record.name)
                    if found and found.status != record.status:
                        await self._repo.update_status(
                            record.id,
                            status=found.status,
                            rejection_reason=found.rejection_reason,
                        )
        return await self._repo.list_by_account(account_id)
```

- [ ] **Step 11.4: Run tests (devem passar)**

Run: `cd apps/api && uv run pytest tests/unit/meta_templates/test_list_templates.py -v`
Expected: 2 PASS.

- [ ] **Step 11.5: Commit**

```bash
git add apps/api/src/shared/application/use_cases/meta_templates/list_templates.py apps/api/tests/unit/meta_templates/test_list_templates.py
git commit -m "feat(meta-templates): use case list_templates com sync sob demanda"
```

---

### Task 12: Use case `delete_template`

**Files:**
- Create: `apps/api/src/shared/application/use_cases/meta_templates/delete_template.py`
- Test: `apps/api/tests/unit/meta_templates/test_delete_template.py`

- [ ] **Step 12.1: Escrever teste**

Criar `apps/api/tests/unit/meta_templates/test_delete_template.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.application.use_cases.meta_templates.delete_template import (
    DeleteTemplate,
    MetaTemplateInUse,
)


def _template(name="t", media_object_key="k"):
    m = MagicMock()
    m.id = uuid4()
    m.name = name
    m.media_object_key = media_object_key
    return m


@pytest.mark.asyncio
async def test_delete_blocked_when_in_use():
    repo = AsyncMock()
    meta = AsyncMock()
    storage = AsyncMock()
    flow_check = AsyncMock(return_value=[
        {"id": "f1", "name": "Welcome", "step_position": 2}
    ])
    template = _template()
    repo.get.return_value = template

    use_case = DeleteTemplate(repo=repo, meta_client=meta, storage=storage,
                              flow_usage_check=flow_check)

    with pytest.raises(MetaTemplateInUse) as info:
        await use_case.execute(account_id=uuid4(), template_id=template.id, waba_id="w")
    assert info.value.flows[0]["name"] == "Welcome"
    meta.delete_template.assert_not_awaited()
    storage.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_full_path():
    repo = AsyncMock()
    meta = AsyncMock()
    storage = AsyncMock()
    template = _template()
    repo.get.return_value = template
    flow_check = AsyncMock(return_value=[])

    use_case = DeleteTemplate(repo=repo, meta_client=meta, storage=storage,
                              flow_usage_check=flow_check)
    await use_case.execute(account_id=uuid4(), template_id=template.id, waba_id="w")

    meta.delete_template.assert_awaited_once_with(waba_id="w", name="t")
    storage.delete.assert_awaited_once_with(key="k")
    repo.delete.assert_awaited_once_with(template.id)


@pytest.mark.asyncio
async def test_delete_without_media_skips_storage():
    repo = AsyncMock()
    meta = AsyncMock()
    storage = AsyncMock()
    template = _template(media_object_key=None)
    repo.get.return_value = template
    flow_check = AsyncMock(return_value=[])

    use_case = DeleteTemplate(repo=repo, meta_client=meta, storage=storage,
                              flow_usage_check=flow_check)
    await use_case.execute(account_id=uuid4(), template_id=template.id, waba_id="w")

    storage.delete.assert_not_awaited()
    repo.delete.assert_awaited_once()
```

- [ ] **Step 12.2: Run tests (devem falhar)**

Run: `cd apps/api && uv run pytest tests/unit/meta_templates/test_delete_template.py -v`
Expected: FAIL.

- [ ] **Step 12.3: Implementar use case**

Criar `apps/api/src/shared/application/use_cases/meta_templates/delete_template.py`:

```python
from __future__ import annotations

from typing import Awaitable, Callable
from uuid import UUID

import structlog

from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository
from shared.adapters.meta.template_client import MetaTemplateClient
from shared.domain.ports.storage import StoragePort

log = structlog.get_logger(__name__)


class MetaTemplateInUse(Exception):
    def __init__(self, flows: list[dict]) -> None:
        super().__init__("template em uso por flows")
        self.flows = flows


FlowUsageCheck = Callable[[UUID, str], Awaitable[list[dict]]]


class DeleteTemplate:
    def __init__(
        self,
        *,
        repo: MetaTemplateRepository,
        meta_client: MetaTemplateClient,
        storage: StoragePort,
        flow_usage_check: FlowUsageCheck,
    ) -> None:
        self._repo = repo
        self._meta = meta_client
        self._storage = storage
        self._check_usage = flow_usage_check

    async def execute(self, *, account_id: UUID, template_id: UUID, waba_id: str) -> None:
        template = await self._repo.get(template_id, account_id)
        if not template:
            raise LookupError("META_TEMPLATE_NOT_FOUND")

        flows = await self._check_usage(account_id, template.name)
        if flows:
            raise MetaTemplateInUse(flows=flows)

        await self._meta.delete_template(waba_id=waba_id, name=template.name)

        if template.media_object_key:
            try:
                await self._storage.delete(key=template.media_object_key)
            except Exception as exc:
                log.warning(
                    "r2_cleanup_pending",
                    template_id=str(template_id),
                    object_key=template.media_object_key,
                    error=str(exc),
                )

        await self._repo.delete(template_id)
        log.info("meta_template_deleted", template_id=str(template_id), name=template.name)
```

- [ ] **Step 12.4: Run tests (devem passar)**

Run: `cd apps/api && uv run pytest tests/unit/meta_templates/test_delete_template.py -v`
Expected: 3 PASS.

- [ ] **Step 12.5: Commit**

```bash
git add apps/api/src/shared/application/use_cases/meta_templates/delete_template.py apps/api/tests/unit/meta_templates/test_delete_template.py
git commit -m "feat(meta-templates): use case delete_template com bloqueio em uso"
```

---

### Task 13: `ChatNexoClient.send_template` estendido + `DispatchFollowupStep`

**Files:**
- Modify: `apps/api/src/shared/adapters/chatnexo/client.py`
- Modify: `apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py`
- Test: `apps/api/tests/unit/chatnexo/test_send_template_with_header.py`
- Test: `apps/api/tests/unit/followup/test_dispatch_with_media.py`

- [ ] **Step 13.1: Escrever teste do ChatNexoClient**

Criar `apps/api/tests/unit/chatnexo/__init__.py` se não existir (vazio).

Criar `apps/api/tests/unit/chatnexo/test_send_template_with_header.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from shared.adapters.chatnexo.client import ChatNexoClient


@pytest.mark.asyncio
async def test_send_template_without_header():
    http = AsyncMock()
    http.post = AsyncMock()
    client = ChatNexoClient(http=http)

    await client.send_template(
        account_id="a", conversation_id="c",
        template_name="t", language="pt_BR", variables={"1": "Fabio"},
    )

    body = http.post.call_args.kwargs["json"]
    assert "header" not in body
    assert body["template_name"] == "t"


@pytest.mark.asyncio
async def test_send_template_with_image_header():
    http = AsyncMock()
    http.post = AsyncMock()
    client = ChatNexoClient(http=http)

    await client.send_template(
        account_id="a", conversation_id="c",
        template_name="t", language="pt_BR", variables={"1": "x"},
        header_link="https://media.example.com/x.jpg",
        header_kind="image",
    )

    body = http.post.call_args.kwargs["json"]
    assert body["header"] == {
        "type": "image",
        "link": "https://media.example.com/x.jpg",
    }
```

- [ ] **Step 13.2: Run test (deve falhar — assinatura antiga)**

Run: `cd apps/api && uv run pytest tests/unit/chatnexo/test_send_template_with_header.py -v`
Expected: FAIL com `TypeError: send_template() got an unexpected keyword argument`.

- [ ] **Step 13.3: Atualizar `send_template`**

Em `apps/api/src/shared/adapters/chatnexo/client.py`, substituir o método `send_template` por:

```python
    async def send_template(
        self,
        *,
        account_id: str,
        conversation_id: str,
        template_name: str,
        language: str | None = None,
        variables: dict[str, Any] | None = None,
        header_link: str | None = None,
        header_kind: Literal["image", "video", "document"] | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "type": "template",
            "template_name": template_name,
            "variables": variables or {},
        }
        if language:
            body["language"] = language
        if header_link and header_kind:
            body["header"] = {"type": header_kind, "link": header_link}
        await self._post(
            f"/accounts/{account_id}/conversations/{conversation_id}/messages",
            json=body,
        )
```

Garantir o import: `from typing import Literal` no topo (e `Any` já existe).

- [ ] **Step 13.4: Run test (deve passar)**

Run: `cd apps/api && uv run pytest tests/unit/chatnexo/test_send_template_with_header.py -v`
Expected: 2 PASS.

- [ ] **Step 13.5: Atualizar callers existentes do `send_template`**

Run: `cd apps/api && grep -rn "send_template" src/shared/application src/agent`

Para cada chamada que passe argumentos posicionais ou faltando `language`, ajustar para forma keyword. Em particular `dispatch_followup_step.py`.

- [ ] **Step 13.6: Escrever teste do dispatch com mídia**

Criar `apps/api/tests/unit/followup/__init__.py` se não existir (vazio).

Criar `apps/api/tests/unit/followup/test_dispatch_with_media.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# Imports devem bater com a estrutura real após Task 13 — ajustar após explorar dispatch_followup_step.py
from shared.application.use_cases.followup.dispatch_followup_step import (
    DispatchFollowupStep,
)


@pytest.mark.asyncio
async def test_dispatch_passes_header_when_template_has_media():
    chatnexo = AsyncMock()
    repo = AsyncMock()
    template = MagicMock(
        name="t", language="pt_BR",
        media_url="https://media.example.com/x.jpg",
        media_kind="IMAGE",
    )
    enrollment_step = MagicMock(
        contact=MagicMock(phone="+5511999"),
        template=template,
        resolved_variables={"1": "Fabio"},
        account_id=uuid4(),
        conversation_id="c1",
    )
    repo.get_with_template.return_value = enrollment_step

    use_case = DispatchFollowupStep(steps=repo, chatnexo=chatnexo)
    await use_case.execute(enrollment_step_id=uuid4())

    chatnexo.send_template.assert_awaited_once()
    kwargs = chatnexo.send_template.await_args.kwargs
    assert kwargs["header_link"] == "https://media.example.com/x.jpg"
    assert kwargs["header_kind"] == "image"


@pytest.mark.asyncio
async def test_dispatch_omits_header_when_no_media():
    chatnexo = AsyncMock()
    repo = AsyncMock()
    template = MagicMock(name="t", language="pt_BR", media_url=None, media_kind=None)
    enrollment_step = MagicMock(
        contact=MagicMock(phone="+5511999"),
        template=template,
        resolved_variables={"1": "Fabio"},
        account_id=uuid4(),
        conversation_id="c1",
    )
    repo.get_with_template.return_value = enrollment_step

    await DispatchFollowupStep(steps=repo, chatnexo=chatnexo).execute(
        enrollment_step_id=uuid4()
    )

    kwargs = chatnexo.send_template.await_args.kwargs
    assert kwargs.get("header_link") is None
    assert kwargs.get("header_kind") is None
```

> **Nota:** se a assinatura real do `DispatchFollowupStep` divergir, ajustar o teste pra refletir a assinatura existente — não inventar.

- [ ] **Step 13.7: Atualizar `DispatchFollowupStep`**

Localizar `apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py` e na chamada a `chatnexo.send_template`, adicionar:

```python
        header_link = template.media_url if getattr(template, "media_url", None) else None
        header_kind = template.media_kind.lower() if getattr(template, "media_kind", None) else None

        await self._chatnexo.send_template(
            account_id=str(account_id),
            conversation_id=conversation_id,
            template_name=template.name,
            language=template.language,
            variables=variables,
            header_link=header_link,
            header_kind=header_kind,
        )
```

Adaptar nomes às variáveis locais já presentes no método.

- [ ] **Step 13.8: Run tests do followup**

Run: `cd apps/api && uv run pytest tests/unit/followup/test_dispatch_with_media.py tests/unit/chatnexo/ -v`
Expected: PASS.

- [ ] **Step 13.9: Run suite unitária inteira**

Run: `cd apps/api && uv run pytest tests/unit -v`
Expected: tudo PASS (incluindo testes pré-existentes).

- [ ] **Step 13.10: Commit**

```bash
git add apps/api/src/shared/adapters/chatnexo/client.py apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py apps/api/tests/unit/chatnexo/ apps/api/tests/unit/followup/
git commit -m "feat(meta-templates): ChatNexoClient.send_template com header_link e DispatchFollowupStep usando mídia"
```

---

### Task 14: Endpoints HTTP atualizados

**Files:**
- Modify: `apps/api/src/interface/http/routers/admin/meta_templates.py`
- Modify: `apps/api/src/interface/http/schemas/meta_templates.py`

- [ ] **Step 14.1: Atualizar schemas Pydantic**

Substituir o conteúdo de `apps/api/src/interface/http/schemas/meta_templates.py` por:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

MediaKind = Literal["IMAGE", "VIDEO", "DOCUMENT"]
TemplateCategory = Literal["MARKETING", "UTILITY"]
TemplateStatus = Literal["PENDING", "APPROVED", "REJECTED"]


class UploadMediaResponse(BaseModel):
    media_url: str
    media_object_key: str
    media_kind: MediaKind
    sha256: str
    size: int


class CreateTemplateRequest(BaseModel):
    name: str
    category: TemplateCategory
    language: str
    components: list[dict[str, Any]]
    media_url: str | None = None
    media_object_key: str | None = None
    media_kind: MediaKind | None = None


class MetaTemplateResponse(BaseModel):
    id: UUID
    name: str
    category: str
    language: str
    status: TemplateStatus
    components: list[dict[str, Any]]
    media_url: str | None = None
    media_kind: MediaKind | None = None
    rejection_reason: str | None = None
    meta_template_id: str | None = None
    created_at: datetime


class DeleteConflictDetail(BaseModel):
    flows: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 14.2: Reescrever router**

Substituir `apps/api/src/interface/http/routers/admin/meta_templates.py` por:

```python
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
    from shared.adapters.db.models import FollowupFlowModel, FollowupStepModel
    from sqlalchemy import select

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
    auth: AdminAuth = Depends(require_admin),
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
    auth: AdminAuth = Depends(require_admin),
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
            raise HTTPException(status_code=422, detail={"code": "META_TEMPLATE_VALIDATION_FAILED", "detail": str(exc)}) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail={"code": "META_API_ERROR", "detail": str(exc)}) from exc

        return _to_response(record)


@router.get("/meta-templates", response_model=list[MetaTemplateResponse])
async def list_templates(
    auth: AdminAuth = Depends(require_admin),
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
    auth: AdminAuth = Depends(require_admin),
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
        except LookupError:
            raise HTTPException(status_code=404, detail="META_TEMPLATE_NOT_FOUND")
        except MetaTemplateInUse as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "META_TEMPLATE_IN_USE", "flows": exc.flows},
            ) from exc
```

- [ ] **Step 14.3: Verificar limites de upload no FastAPI**

Run: `cd apps/api && grep -rn "max_request_size\|MAX_UPLOAD" src/`

Se não houver, ok — FastAPI/Uvicorn não impõe limite por padrão (limite é da request body). Documento de 100MB pode passar mas grande. Adicionar comentário no router (não bloqueia).

- [ ] **Step 14.4: Run all unit tests**

Run: `cd apps/api && uv run pytest tests/unit -v`
Expected: tudo PASS.

- [ ] **Step 14.5: Subir API local e testar smoke**

Run: `cd apps/api && uv run uvicorn main:app --reload &` (em terminal separado)

Run: `curl -i http://localhost:8000/health`
Expected: 200 com `{"status":"ok"}`.

Parar o uvicorn.

- [ ] **Step 14.6: Commit**

```bash
git add apps/api/src/interface/http/routers/admin/meta_templates.py apps/api/src/interface/http/schemas/meta_templates.py
git commit -m "feat(meta-templates): endpoints HTTP de upload, create, list e delete"
```

---

# Frontend

---

### Task 15: `validation.ts` no frontend

**Files:**
- Create: `apps/web/src/features/templates/validation.ts`
- Modify: `apps/web/src/features/templates/types.ts`

- [ ] **Step 15.1: Atualizar `types.ts`**

Substituir `apps/web/src/features/templates/types.ts` por:

```typescript
export type MediaKind = "IMAGE" | "VIDEO" | "DOCUMENT";
export type TemplateCategory = "MARKETING" | "UTILITY";
export type TemplateStatus = "APPROVED" | "PENDING" | "REJECTED";

export interface TemplateButton {
  type: "QUICK_REPLY" | "URL" | "PHONE_NUMBER";
  text: string;
  url?: string;
  phone_number?: string;
  example?: string[];
}

export interface TemplateComponent {
  type: "HEADER" | "BODY" | "FOOTER" | "BUTTONS";
  format?: "TEXT" | MediaKind;
  text?: string;
  buttons?: TemplateButton[];
  example?: {
    header_text?: string[];
    header_handle?: string[];
    body_text?: string[][];
  };
}

export interface UploadedMedia {
  url: string;
  objectKey: string;
  kind: MediaKind;
  size: number;
  sha256: string;
  fileName: string;
}

export interface MetaTemplate {
  id: string;
  name: string;
  category: TemplateCategory;
  language: string;
  status: TemplateStatus;
  components: TemplateComponent[];
  media_url?: string | null;
  media_kind?: MediaKind | null;
  rejection_reason?: string | null;
  meta_template_id?: string | null;
  created_at: string;
}

export interface CreateTemplateDto {
  name: string;
  category: TemplateCategory;
  language: string;
  components: Record<string, unknown>[];
  media_url?: string | null;
  media_object_key?: string | null;
  media_kind?: MediaKind | null;
}
```

- [ ] **Step 15.2: Criar `validation.ts`**

Criar `apps/web/src/features/templates/validation.ts`:

```typescript
import type { MediaKind, TemplateButton, TemplateComponent } from "./types";

export const NAME_REGEX = /^[a-z0-9_]{3,512}$/;
export const PHONE_E164_REGEX = /^\+\d{8,15}$/;
export const VARIABLE_REGEX = /\{\{(\d+)\}\}/g;
export const ADJACENT_VAR_REGEX = /\}\}\{\{/;

export const ALLOWED_CATEGORIES = ["MARKETING", "UTILITY"] as const;
export const ALLOWED_LANGUAGES = ["pt_BR", "en_US"] as const;
export const ALLOWED_HEADER_FORMATS = ["TEXT", "IMAGE", "VIDEO", "DOCUMENT"] as const;

export const HEADER_TEXT_MAX = 60;
export const BODY_TEXT_MAX = 1024;
export const FOOTER_MAX = 60;
export const BUTTON_LABEL_MAX = 25;
export const BUTTON_URL_MAX = 2000;
export const BUTTONS_TOTAL_MAX = 10;
export const CTA_BUTTONS_MAX = 2;

export const MEDIA_LIMITS: Record<MediaKind, { mimes: string[]; maxBytes: number }> = {
  IMAGE: { mimes: ["image/jpeg", "image/png"], maxBytes: 5 * 1024 * 1024 },
  VIDEO: { mimes: ["video/mp4"], maxBytes: 16 * 1024 * 1024 },
  DOCUMENT: { mimes: ["application/pdf"], maxBytes: 100 * 1024 * 1024 },
};

export interface ValidationError {
  field: string;
  code: string;
  message: string;
}

export function detectVariables(text: string): number[] {
  const matches = text.matchAll(VARIABLE_REGEX);
  const out: number[] = [];
  for (const m of matches) out.push(parseInt(m[1], 10));
  return out;
}

export function validateName(name: string): ValidationError | null {
  if (!NAME_REGEX.test(name)) {
    return {
      field: "name",
      code: "NAME_INVALID",
      message: "Use a-z, 0-9, _ — entre 3 e 512 caracteres",
    };
  }
  return null;
}

export function validateBody(text: string, examples: string[]): ValidationError[] {
  const errors: ValidationError[] = [];
  if (!text.trim()) {
    errors.push({ field: "body", code: "BODY_REQUIRED", message: "Body é obrigatório" });
  }
  if (text.length > BODY_TEXT_MAX) {
    errors.push({ field: "body", code: "BODY_TEXT_TOO_LONG",
      message: `Body excede ${BODY_TEXT_MAX} caracteres` });
  }
  if (ADJACENT_VAR_REGEX.test(text)) {
    errors.push({ field: "body", code: "VARIABLES_ADJACENT",
      message: "Variáveis não podem ser adjacentes" });
  }
  const vars = detectVariables(text);
  const unique = Array.from(new Set(vars)).sort((a, b) => a - b);
  const expected = unique.map((_, i) => i + 1);
  if (JSON.stringify(unique) !== JSON.stringify(expected)) {
    errors.push({ field: "body", code: "VARIABLES_NOT_SEQUENTIAL",
      message: "Variáveis devem ser sequenciais a partir de {{1}}" });
  }
  if (examples.length < unique.length || examples.some((e) => !e.trim())) {
    errors.push({ field: "body.examples", code: "VARIABLE_MISSING_EXAMPLE",
      message: "Cada variável precisa de um exemplo" });
  }
  return errors;
}

export function validateHeader(format: string | undefined, text: string): ValidationError[] {
  const errors: ValidationError[] = [];
  if (format === "TEXT") {
    if (text.length > HEADER_TEXT_MAX) {
      errors.push({ field: "header.text", code: "HEADER_TEXT_TOO_LONG",
        message: `Header excede ${HEADER_TEXT_MAX} caracteres` });
    }
    const vars = detectVariables(text);
    if (new Set(vars).size > 1) {
      errors.push({ field: "header.text", code: "HEADER_TOO_MANY_VARIABLES",
        message: "Header text aceita no máximo 1 variável" });
    }
  }
  return errors;
}

export function validateFooter(text: string): ValidationError[] {
  const errors: ValidationError[] = [];
  if (text.length > FOOTER_MAX) {
    errors.push({ field: "footer", code: "FOOTER_TOO_LONG",
      message: `Footer excede ${FOOTER_MAX} caracteres` });
  }
  if (VARIABLE_REGEX.test(text)) {
    errors.push({ field: "footer", code: "FOOTER_HAS_VARIABLES",
      message: "Footer não pode conter variáveis" });
  }
  return errors;
}

export function validateButtons(buttons: TemplateButton[]): ValidationError[] {
  const errors: ValidationError[] = [];
  if (buttons.length > BUTTONS_TOTAL_MAX) {
    errors.push({ field: "buttons", code: "BUTTONS_TOO_MANY",
      message: `Máximo ${BUTTONS_TOTAL_MAX} botões` });
  }
  const cta = buttons.filter((b) => b.type === "URL" || b.type === "PHONE_NUMBER").length;
  if (cta > CTA_BUTTONS_MAX) {
    errors.push({ field: "buttons", code: "BUTTONS_TOO_MANY_CTA",
      message: `Máximo ${CTA_BUTTONS_MAX} botões CTA (URL/PHONE)` });
  }
  buttons.forEach((b, i) => {
    if (b.text.length > BUTTON_LABEL_MAX) {
      errors.push({ field: `buttons[${i}].text`, code: "BUTTON_LABEL_TOO_LONG",
        message: `Label excede ${BUTTON_LABEL_MAX} chars` });
    }
    if (b.type === "URL") {
      const url = b.url || "";
      if (url.length > BUTTON_URL_MAX) {
        errors.push({ field: `buttons[${i}].url`, code: "BUTTON_URL_TOO_LONG",
          message: `URL excede ${BUTTON_URL_MAX} chars` });
      }
      try {
        const u = new URL(url);
        if (!["http:", "https:"].includes(u.protocol)) throw new Error();
      } catch {
        errors.push({ field: `buttons[${i}].url`, code: "BUTTON_URL_INVALID",
          message: "URL inválida" });
      }
    }
    if (b.type === "PHONE_NUMBER") {
      if (!PHONE_E164_REGEX.test(b.phone_number || "")) {
        errors.push({ field: `buttons[${i}].phone_number`, code: "BUTTON_PHONE_INVALID",
          message: "Use formato E.164 (ex.: +5511999999999)" });
      }
    }
  });
  return errors;
}

export function validateMediaFile(file: File, kind: MediaKind): ValidationError | null {
  const limits = MEDIA_LIMITS[kind];
  if (!limits.mimes.includes(file.type)) {
    return { field: "media.mime", code: "MEDIA_TYPE_INVALID",
      message: `Tipo inválido. Permitido: ${limits.mimes.join(", ")}` };
  }
  if (file.size > limits.maxBytes) {
    const mb = limits.maxBytes / (1024 * 1024);
    return { field: "media.size", code: "MEDIA_SIZE_EXCEEDED",
      message: `Arquivo excede ${mb}MB` };
  }
  return null;
}
```

- [ ] **Step 15.3: Type-check**

Run: `cd apps/web && npx tsc --noEmit`
Expected: sem erros novos.

- [ ] **Step 15.4: Commit**

```bash
git add apps/web/src/features/templates/validation.ts apps/web/src/features/templates/types.ts
git commit -m "feat(templates): tipos atualizados e validation.ts com regras Meta"
```

---

### Task 16: API client (`uploadTemplateMedia`, `deleteMetaTemplate`)

**Files:**
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 16.1: Atualizar `api.ts`**

Localizar a seção de Meta Templates em `apps/web/src/lib/api.ts` (linha ~211). Substituir/adicionar:

```typescript
export async function listMetaTemplates(): Promise<MetaTemplate[]> {
  return apiFetch<MetaTemplate[]>("/admin/meta-templates");
}

export async function createMetaTemplate(dto: CreateTemplateDto): Promise<MetaTemplate> {
  return apiFetch<MetaTemplate>("/admin/meta-templates", {
    method: "POST",
    body: JSON.stringify(dto),
  });
}

export async function deleteMetaTemplate(id: string): Promise<void> {
  await apiFetch<void>(`/admin/meta-templates/${id}`, { method: "DELETE" });
}

export interface UploadMediaResponse {
  media_url: string;
  media_object_key: string;
  media_kind: "IMAGE" | "VIDEO" | "DOCUMENT";
  sha256: string;
  size: number;
}

export function uploadTemplateMedia(
  file: File,
  kind: "IMAGE" | "VIDEO" | "DOCUMENT",
  onProgress?: (pct: number) => void,
): Promise<UploadMediaResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const fd = new FormData();
    fd.append("file", file);
    fd.append("kind", kind);

    xhr.open("POST", `${getApiBase()}/admin/meta-templates/upload-media`);
    const token = getAuthToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        let detail: unknown = xhr.responseText;
        try { detail = JSON.parse(xhr.responseText); } catch {}
        reject(new Error(typeof detail === "object" ? JSON.stringify(detail) : String(detail)));
      }
    };
    xhr.onerror = () => reject(new Error("Network error"));
    xhr.send(fd);
  });
}
```

> **Nota:** se `getApiBase` ou `getAuthToken` ainda não existem como funções exportadas, use as variáveis/lógica equivalentes que `apiFetch` usa hoje. Se `apiFetch` lê do localStorage, replicar a mesma leitura aqui.

- [ ] **Step 16.2: Type-check**

Run: `cd apps/web && npx tsc --noEmit`
Expected: sem erros.

- [ ] **Step 16.3: Commit**

```bash
git add apps/web/src/lib/api.ts
git commit -m "feat(templates): api client upload + delete de templates"
```

---

### Task 17: Componente `MediaUploadField`

**Files:**
- Create: `apps/web/src/features/templates/components/MediaUploadField.tsx`

- [ ] **Step 17.1: Implementar**

Criar o arquivo:

```tsx
"use client";

import { useCallback, useRef, useState } from "react";
import { uploadTemplateMedia } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import { MEDIA_LIMITS, validateMediaFile } from "../validation";
import type { MediaKind, UploadedMedia } from "../types";

interface Props {
  kind: MediaKind;
  value: UploadedMedia | null;
  onChange: (media: UploadedMedia | null) => void;
}

const KIND_LABEL: Record<MediaKind, string> = {
  IMAGE: "Imagem",
  VIDEO: "Vídeo",
  DOCUMENT: "Documento",
};

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

export function MediaUploadField({ kind, value, onChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const toast = useToast();
  const limits = MEDIA_LIMITS[kind];
  const maxMb = limits.maxBytes / (1024 * 1024);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      const file = files?.[0];
      if (!file) return;
      const err = validateMediaFile(file, kind);
      if (err) {
        toast.error(err.message);
        return;
      }
      try {
        setProgress(0);
        const out = await uploadTemplateMedia(file, kind, setProgress);
        onChange({
          url: out.media_url,
          objectKey: out.media_object_key,
          kind: out.media_kind,
          size: out.size,
          sha256: out.sha256,
          fileName: file.name,
        });
        toast.success("Mídia enviada com sucesso");
      } catch (e) {
        toast.error(`Falha no upload: ${e instanceof Error ? e.message : e}`);
      } finally {
        setProgress(null);
      }
    },
    [kind, onChange, toast],
  );

  if (value) {
    return (
      <div className="rounded-lg border border-outline-variant bg-surface-container p-3 flex items-center gap-3">
        <span className="material-symbols-outlined text-on-surface-variant">
          {kind === "IMAGE" ? "image" : kind === "VIDEO" ? "videocam" : "description"}
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-on-surface truncate">{value.fileName}</div>
          <div className="text-xs text-on-surface-variant">
            {KIND_LABEL[kind]} · {formatBytes(value.size)}
          </div>
        </div>
        <button
          type="button"
          className="text-sm text-primary hover:underline"
          onClick={() => inputRef.current?.click()}
        >
          Trocar
        </button>
        <button
          type="button"
          className="text-sm text-error hover:underline"
          onClick={() => onChange(null)}
        >
          Remover
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={limits.mimes.join(",")}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
    );
  }

  return (
    <div
      className={`rounded-lg border-2 border-dashed p-6 text-center cursor-pointer transition ${
        dragOver
          ? "border-primary bg-primary/5"
          : "border-outline-variant bg-surface-container hover:border-primary"
      }`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      {progress !== null ? (
        <div className="space-y-2">
          <div className="text-sm text-on-surface">Enviando {progress}%…</div>
          <div className="h-2 bg-outline-variant rounded overflow-hidden">
            <div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
      ) : (
        <>
          <span className="material-symbols-outlined text-4xl text-on-surface-variant">
            cloud_upload
          </span>
          <div className="text-sm text-on-surface mt-1">
            Arraste {KIND_LABEL[kind].toLowerCase()} aqui ou <span className="text-primary">clique pra selecionar</span>
          </div>
          <div className="text-xs text-on-surface-variant mt-1">
            Max {maxMb}MB · {limits.mimes.map((m) => m.split("/")[1]).join(", ")}
          </div>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={limits.mimes.join(",")}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}
```

- [ ] **Step 17.2: Type-check**

Run: `cd apps/web && npx tsc --noEmit`
Expected: sem erros.

- [ ] **Step 17.3: Commit**

```bash
git add apps/web/src/features/templates/components/MediaUploadField.tsx
git commit -m "feat(templates): MediaUploadField com drag-and-drop e progresso"
```

---

### Task 18: Componente `VariablesEditor`

**Files:**
- Create: `apps/web/src/features/templates/components/VariablesEditor.tsx`

- [ ] **Step 18.1: Implementar**

Criar `apps/web/src/features/templates/components/VariablesEditor.tsx`:

```tsx
"use client";

import { detectVariables } from "../validation";

interface Props {
  bodyText: string;
  examples: string[];
  onChange: (examples: string[]) => void;
}

export function VariablesEditor({ bodyText, examples, onChange }: Props) {
  const vars = Array.from(new Set(detectVariables(bodyText))).sort((a, b) => a - b);

  if (vars.length === 0) {
    return (
      <p className="text-xs text-on-surface-variant">
        Variáveis no formato {`{{1}}`}, {`{{2}}`} aparecerão aqui para você definir um exemplo.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-on-surface-variant">
        Exemplos das variáveis (obrigatório)
      </div>
      {vars.map((n, i) => (
        <div key={n} className="flex items-center gap-2">
          <span className="text-sm font-mono text-on-surface w-12">{`{{${n}}}`}</span>
          <input
            type="text"
            className="flex-1 px-3 py-2 rounded border border-outline-variant bg-surface-container text-sm"
            placeholder={`Exemplo para variável ${n}`}
            value={examples[i] || ""}
            onChange={(e) => {
              const next = [...examples];
              next[i] = e.target.value;
              onChange(next);
            }}
          />
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 18.2: Type-check + commit**

Run: `cd apps/web && npx tsc --noEmit`
Expected: sem erros.

```bash
git add apps/web/src/features/templates/components/VariablesEditor.tsx
git commit -m "feat(templates): VariablesEditor para exemplos de variáveis"
```

---

### Task 19: Componente `ButtonsEditor`

**Files:**
- Create: `apps/web/src/features/templates/components/ButtonsEditor.tsx`

- [ ] **Step 19.1: Implementar**

Criar `apps/web/src/features/templates/components/ButtonsEditor.tsx`:

```tsx
"use client";

import {
  BUTTONS_TOTAL_MAX,
  BUTTON_LABEL_MAX,
  BUTTON_URL_MAX,
  CTA_BUTTONS_MAX,
} from "../validation";
import type { TemplateButton } from "../types";

interface Props {
  buttons: TemplateButton[];
  onChange: (buttons: TemplateButton[]) => void;
}

export function ButtonsEditor({ buttons, onChange }: Props) {
  const ctaCount = buttons.filter((b) => b.type === "URL" || b.type === "PHONE_NUMBER").length;

  const add = (type: TemplateButton["type"]) => {
    if (buttons.length >= BUTTONS_TOTAL_MAX) return;
    if ((type === "URL" || type === "PHONE_NUMBER") && ctaCount >= CTA_BUTTONS_MAX) return;
    const next: TemplateButton = { type, text: "" };
    if (type === "URL") next.url = "";
    if (type === "PHONE_NUMBER") next.phone_number = "";
    onChange([...buttons, next]);
  };

  const update = (i: number, patch: Partial<TemplateButton>) => {
    const next = buttons.map((b, idx) => (idx === i ? { ...b, ...patch } : b));
    onChange(next);
  };

  const remove = (i: number) => {
    onChange(buttons.filter((_, idx) => idx !== i));
  };

  return (
    <div className="space-y-2">
      {buttons.map((b, i) => (
        <div key={i} className="flex items-center gap-2 p-2 rounded border border-outline-variant bg-surface-container">
          <select
            className="px-2 py-1 rounded border border-outline-variant bg-surface text-sm"
            value={b.type}
            onChange={(e) => update(i, { type: e.target.value as TemplateButton["type"] })}
          >
            <option value="QUICK_REPLY">Quick Reply</option>
            <option value="URL">URL</option>
            <option value="PHONE_NUMBER">Telefone</option>
          </select>
          <input
            type="text"
            className="flex-1 px-2 py-1 rounded border border-outline-variant bg-surface text-sm"
            placeholder="Label (max 25)"
            maxLength={BUTTON_LABEL_MAX}
            value={b.text}
            onChange={(e) => update(i, { text: e.target.value })}
          />
          {b.type === "URL" && (
            <input
              type="url"
              className="flex-[2] px-2 py-1 rounded border border-outline-variant bg-surface text-sm"
              placeholder="https://..."
              maxLength={BUTTON_URL_MAX}
              value={b.url || ""}
              onChange={(e) => update(i, { url: e.target.value })}
            />
          )}
          {b.type === "PHONE_NUMBER" && (
            <input
              type="tel"
              className="flex-[2] px-2 py-1 rounded border border-outline-variant bg-surface text-sm"
              placeholder="+5511999999999"
              value={b.phone_number || ""}
              onChange={(e) => update(i, { phone_number: e.target.value })}
            />
          )}
          <button
            type="button"
            className="text-error hover:underline text-sm"
            onClick={() => remove(i)}
          >
            Remover
          </button>
        </div>
      ))}
      <div className="flex gap-2">
        <button type="button" disabled={buttons.length >= BUTTONS_TOTAL_MAX}
          className="text-sm text-primary disabled:opacity-50 hover:underline"
          onClick={() => add("QUICK_REPLY")}>
          + Quick Reply
        </button>
        <button type="button" disabled={ctaCount >= CTA_BUTTONS_MAX || buttons.length >= BUTTONS_TOTAL_MAX}
          className="text-sm text-primary disabled:opacity-50 hover:underline"
          onClick={() => add("URL")}>
          + URL
        </button>
        <button type="button" disabled={ctaCount >= CTA_BUTTONS_MAX || buttons.length >= BUTTONS_TOTAL_MAX}
          className="text-sm text-primary disabled:opacity-50 hover:underline"
          onClick={() => add("PHONE_NUMBER")}>
          + Telefone
        </button>
      </div>
      <div className="text-xs text-on-surface-variant">
        Total: {buttons.length}/{BUTTONS_TOTAL_MAX} · CTA: {ctaCount}/{CTA_BUTTONS_MAX}
      </div>
    </div>
  );
}
```

- [ ] **Step 19.2: Type-check + commit**

Run: `cd apps/web && npx tsc --noEmit`
Expected: sem erros.

```bash
git add apps/web/src/features/templates/components/ButtonsEditor.tsx
git commit -m "feat(templates): ButtonsEditor com tipos QR/URL/PHONE e limites"
```

---

### Task 20: Refatorar `TemplateForm`

**Files:**
- Modify: `apps/web/src/features/templates/components/TemplateForm.tsx`

- [ ] **Step 20.1: Estudar form atual**

Run: `cd apps/web && wc -l src/features/templates/components/TemplateForm.tsx`

Abrir o arquivo e localizar:
- Estado de `category` (remover AUTHENTICATION das opções)
- Estado de header (substituir input de URL por `MediaUploadField`)
- Lógica `buildComponents()` (incluir `media_url`, `media_object_key`, `media_kind` no DTO)
- Submit (chamar `validateAll()` antes)

- [ ] **Step 20.2: Aplicar mudanças**

Mudanças pontuais (não reescrever o arquivo inteiro):

1. **Importar:**
```tsx
import { MediaUploadField } from "./MediaUploadField";
import { VariablesEditor } from "./VariablesEditor";
import { ButtonsEditor } from "./ButtonsEditor";
import {
  validateName, validateBody, validateHeader, validateFooter, validateButtons,
  HEADER_TEXT_MAX, BODY_TEXT_MAX, FOOTER_MAX,
} from "../validation";
import type { UploadedMedia } from "../types";
```

2. **Estado:**
```tsx
const [media, setMedia] = useState<UploadedMedia | null>(null);
const [bodyExamples, setBodyExamples] = useState<string[]>([]);
```

3. **Categoria — substituir lista por:**
```tsx
<option value="MARKETING">MARKETING</option>
<option value="UTILITY">UTILITY</option>
```
(remover `AUTHENTICATION`)

4. **Header — quando format ∈ {IMAGE, VIDEO, DOCUMENT}:**
```tsx
<MediaUploadField kind={headerFormat as MediaKind} value={media} onChange={setMedia} />
```

5. **Body — adicionar contador e VariablesEditor logo abaixo:**
```tsx
<div className="flex justify-between text-xs text-on-surface-variant">
  <span>Body * (max {BODY_TEXT_MAX})</span>
  <span className={bodyText.length > BODY_TEXT_MAX ? "text-error" : ""}>
    {bodyText.length}/{BODY_TEXT_MAX}
  </span>
</div>
{/* textarea existente */}
<VariablesEditor bodyText={bodyText} examples={bodyExamples} onChange={setBodyExamples} />
```

6. **Footer — contador `N/60`** (similar ao Body, com `FOOTER_MAX`).

7. **Botões — substituir bloco existente por:**
```tsx
<ButtonsEditor buttons={buttons} onChange={setButtons} />
```

8. **`buildComponents()` — quando há mídia, montar header com `format` e `example.header_handle: []` (a Meta preenche com handle no backend); incluir `media_*` no DTO retornado:**

```tsx
function buildDto(): CreateTemplateDto {
  const components: Record<string, unknown>[] = [];
  if (headerFormat === "TEXT" && headerText.trim()) {
    components.push({ type: "HEADER", format: "TEXT", text: headerText });
  } else if (media && (headerFormat === "IMAGE" || headerFormat === "VIDEO" || headerFormat === "DOCUMENT")) {
    components.push({ type: "HEADER", format: headerFormat, example: { header_handle: [] } });
  }
  components.push({
    type: "BODY",
    text: bodyText,
    example: { body_text: [bodyExamples] },
  });
  if (footerText.trim()) components.push({ type: "FOOTER", text: footerText });
  if (buttons.length > 0) components.push({ type: "BUTTONS", buttons });

  return {
    name, category, language,
    components,
    media_url: media?.url ?? null,
    media_object_key: media?.objectKey ?? null,
    media_kind: media?.kind ?? null,
  };
}
```

9. **Submit — validar antes:**

```tsx
function validateAll(): ValidationError[] {
  const errs: ValidationError[] = [];
  const ne = validateName(name); if (ne) errs.push(ne);
  errs.push(...validateHeader(headerFormat, headerText));
  errs.push(...validateBody(bodyText, bodyExamples));
  if (footerText) errs.push(...validateFooter(footerText));
  errs.push(...validateButtons(buttons));
  return errs;
}

async function handleSubmit() {
  const errs = validateAll();
  if (errs.length > 0) {
    toast.error(errs[0].message);
    return;
  }
  // ... existing submission ...
}
```

`<button type="submit" disabled={validateAll().length > 0}>...`

- [ ] **Step 20.3: Type-check**

Run: `cd apps/web && npx tsc --noEmit`
Expected: sem erros.

- [ ] **Step 20.4: Smoke test no navegador**

Run: `cd apps/web && npm run dev` (em terminal separado)

No navegador (`http://localhost:3000`):
1. Login admin
2. Ir em `/templates`, abrir modal "Novo Template"
3. Preencher nome `teste_imagem`, categoria UTILITY, idioma pt_BR, header IMAGE
4. Arrastar uma imagem JPG/PNG ≤5MB → deve subir e mostrar preview
5. Body: `Olá {{1}}, sua compra de {{2}} foi confirmada!`
6. Preencher exemplos das variáveis
7. Submit deve criar template (verificar toast e listagem com badge PENDING)

> Se R2/META_APP_ID não configurados, espera-se 422 — documenta isso e segue.

Parar o dev server.

- [ ] **Step 20.5: Commit**

```bash
git add apps/web/src/features/templates/components/TemplateForm.tsx
git commit -m "feat(templates): TemplateForm com upload de mídia e validação inline"
```

---

### Task 21: Listagem `/templates` com badges, delete e dialog

**Files:**
- Create: `apps/web/src/features/templates/components/DeleteTemplateDialog.tsx`
- Modify: `apps/web/src/app/(admin)/templates/page.tsx`

- [ ] **Step 21.1: Criar `DeleteTemplateDialog.tsx`**

```tsx
"use client";

import { ConfirmDialog } from "@/shared/components/ConfirmDialog";
import type { MetaTemplate } from "../types";

interface Props {
  template: MetaTemplate | null;
  conflictFlows?: { id: string; name: string; step_position: number }[] | null;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

export function DeleteTemplateDialog({ template, conflictFlows, onConfirm, onClose }: Props) {
  if (!template) return null;

  if (conflictFlows && conflictFlows.length > 0) {
    return (
      <ConfirmDialog
        title="Template em uso"
        confirmLabel="Entendi"
        onConfirm={onClose}
        onClose={onClose}
        variant="warning"
      >
        <p className="text-sm text-on-surface-variant mb-2">
          Não é possível excluir <b>{template.name}</b>. Ele é usado nestes flows:
        </p>
        <ul className="text-sm space-y-1">
          {conflictFlows.map((f) => (
            <li key={f.id} className="text-on-surface">
              <a href={`/followup/${f.id}`} className="text-primary hover:underline">
                {f.name}
              </a>{" "}
              <span className="text-on-surface-variant">(passo {f.step_position})</span>
            </li>
          ))}
        </ul>
      </ConfirmDialog>
    );
  }

  return (
    <ConfirmDialog
      title="Excluir template?"
      confirmLabel="Excluir"
      variant="destructive"
      onConfirm={onConfirm}
      onClose={onClose}
    >
      <p className="text-sm text-on-surface-variant">
        Vamos excluir <b>{template.name}</b> da Meta, do nosso storage e do banco. Esta ação não pode ser desfeita.
      </p>
    </ConfirmDialog>
  );
}
```

> **Nota:** se o `ConfirmDialog` existente tiver assinatura diferente (ex.: usar `open` prop), ajustar para a real. Verificar `apps/web/src/shared/components/ConfirmDialog.tsx`.

- [ ] **Step 21.2: Atualizar página `/templates`**

Em `apps/web/src/app/(admin)/templates/page.tsx`:

1. Adicionar estado:
```tsx
const [toDelete, setToDelete] = useState<MetaTemplate | null>(null);
const [conflictFlows, setConflictFlows] = useState<{ id: string; name: string; step_position: number }[] | null>(null);
```

2. Função delete:
```tsx
async function handleDelete() {
  if (!toDelete) return;
  try {
    await deleteMetaTemplate(toDelete.id);
    toast.success("Template excluído");
    setToDelete(null);
    refresh();
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    try {
      const parsed = JSON.parse(msg);
      if (parsed?.detail?.code === "META_TEMPLATE_IN_USE") {
        setConflictFlows(parsed.detail.flows);
        return;
      }
    } catch {}
    toast.error(`Falha: ${msg}`);
  }
}
```

3. Em cada item da lista, adicionar:
```tsx
<StatusBadge status={t.status} />
{t.status === "REJECTED" && t.rejection_reason && (
  <span title={t.rejection_reason} className="text-xs text-error cursor-help">
    motivo
  </span>
)}
<button onClick={() => setToDelete(t)} className="text-error hover:underline">
  Excluir
</button>
```

4. Adicionar componente `StatusBadge` inline ou em arquivo dedicado:
```tsx
function StatusBadge({ status }: { status: TemplateStatus }) {
  const map = {
    PENDING: { label: "Pendente", cls: "bg-warning/10 text-warning" },
    APPROVED: { label: "Aprovado", cls: "bg-success/10 text-success" },
    REJECTED: { label: "Rejeitado", cls: "bg-error/10 text-error" },
  };
  const m = map[status];
  return <span className={`px-2 py-0.5 rounded-full text-xs ${m.cls}`}>{m.label}</span>;
}
```

5. Renderizar `DeleteTemplateDialog`:
```tsx
<DeleteTemplateDialog
  template={toDelete}
  conflictFlows={conflictFlows}
  onConfirm={handleDelete}
  onClose={() => { setToDelete(null); setConflictFlows(null); }}
/>
```

- [ ] **Step 21.3: Type-check + dev test**

Run: `cd apps/web && npx tsc --noEmit`
Expected: sem erros.

Smoke test no navegador: tenta excluir um template em uso por um flow → deve mostrar dialog com lista; excluir um template não-usado → deve sumir da listagem.

- [ ] **Step 21.4: Commit**

```bash
git add apps/web/src/app/\(admin\)/templates/page.tsx apps/web/src/features/templates/components/DeleteTemplateDialog.tsx
git commit -m "feat(templates): delete com bloqueio em uso e badge de status"
```

---

# Integration Test

---

### Task 22: Integration test do fluxo end-to-end

**Files:**
- Create: `apps/api/tests/integration/test_meta_templates_flow.py`

- [ ] **Step 22.1: Escrever teste**

Criar `apps/api/tests/integration/test_meta_templates_flow.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from main import app
from shared.adapters.db.session import session_scope
from shared.adapters.db.models import MetaTemplateModel


@pytest.mark.asyncio
async def test_full_flow_upload_create_list_delete(monkeypatch, admin_token):
    # Mock R2 storage
    fake_r2 = AsyncMock()
    fake_r2.upload.return_value = type("O", (), {
        "url": "https://media.example.com/x.jpg",
        "object_key": "accounts/x/templates/x.jpg",
        "size": 1024, "sha256": "ab", "content_type": "image/jpeg",
    })()
    fake_r2.delete = AsyncMock()

    # Mock Meta client
    fake_meta = AsyncMock()
    fake_meta.create_resumable_upload_session.return_value = "upload:1"
    fake_meta.upload_media_resumable.return_value = "4::HANDLE"
    fake_meta.create_template.return_value = type("T", (), {
        "id": "meta_id_1", "status": "PENDING",
    })()
    fake_meta.list_templates.return_value = []
    fake_meta.delete_template = AsyncMock()

    with (
        patch("interface.http.routers.admin.meta_templates.R2Storage.from_settings", return_value=fake_r2),
        patch("interface.http.routers.admin.meta_templates._get_meta_client_and_waba",
              new=AsyncMock(return_value=(fake_meta, "waba1"))),
    ):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            headers = {"Authorization": f"Bearer {admin_token}"}

            # 1. Upload media
            files = {"file": ("x.jpg", b"x" * 1024, "image/jpeg")}
            r = await ac.post(
                "/admin/meta-templates/upload-media",
                files=files, data={"kind": "IMAGE"}, headers=headers,
            )
            assert r.status_code == 201, r.text
            uploaded = r.json()

            # 2. Create template
            r = await ac.post(
                "/admin/meta-templates",
                json={
                    "name": "test_int",
                    "category": "UTILITY",
                    "language": "pt_BR",
                    "components": [
                        {"type": "HEADER", "format": "IMAGE", "example": {"header_handle": []}},
                        {"type": "BODY", "text": "Olá {{1}}", "example": {"body_text": [["Fabio"]]}},
                    ],
                    "media_url": uploaded["media_url"],
                    "media_object_key": uploaded["media_object_key"],
                    "media_kind": uploaded["media_kind"],
                },
                headers=headers,
            )
            assert r.status_code == 201, r.text
            template = r.json()

            # 3. List
            r = await ac.get("/admin/meta-templates", headers=headers)
            assert r.status_code == 200
            assert any(t["id"] == template["id"] for t in r.json())

            # 4. Delete
            r = await ac.delete(f"/admin/meta-templates/{template['id']}", headers=headers)
            assert r.status_code == 204
            fake_r2.delete.assert_awaited()
            fake_meta.delete_template.assert_awaited()


@pytest.mark.asyncio
async def test_create_meta_failure_cleans_r2(admin_token):
    """Verifica rollback: meta create falha → R2 limpo."""
    fake_r2 = AsyncMock()
    fake_r2.delete = AsyncMock()

    fake_meta = AsyncMock()
    fake_meta.create_resumable_upload_session.side_effect = RuntimeError("meta down")

    with (
        patch("interface.http.routers.admin.meta_templates.R2Storage.from_settings", return_value=fake_r2),
        patch("interface.http.routers.admin.meta_templates._get_meta_client_and_waba",
              new=AsyncMock(return_value=(fake_meta, "waba1"))),
    ):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            headers = {"Authorization": f"Bearer {admin_token}"}
            r = await ac.post(
                "/admin/meta-templates",
                json={
                    "name": "test_fail",
                    "category": "UTILITY",
                    "language": "pt_BR",
                    "components": [
                        {"type": "HEADER", "format": "IMAGE", "example": {"header_handle": []}},
                        {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
                    ],
                    "media_url": "https://media.example.com/x.jpg",
                    "media_object_key": "accounts/x/templates/x.jpg",
                    "media_kind": "IMAGE",
                },
                headers=headers,
            )
            assert r.status_code == 502
            fake_r2.delete.assert_awaited_once_with(key="accounts/x/templates/x.jpg")
```

> **Nota:** o fixture `admin_token` precisa existir nos integration tests. Se não existir, adicionar ao `conftest.py` da pasta `tests/integration/`. Padrão: criar admin user na fixture e gerar JWT.

- [ ] **Step 22.2: Run integration**

Run: `cd apps/api && uv run pytest tests/integration/test_meta_templates_flow.py -v`
Expected: PASS (com postgres+redis up). Ajustar fixtures se necessário.

- [ ] **Step 22.3: Run all tests**

Run: `cd apps/api && uv run pytest -v`
Expected: tudo PASS.

- [ ] **Step 22.4: Lint + format**

Run: `cd apps/api && uv run ruff check src tests && uv run ruff format src tests && uv run mypy src`
Expected: limpo.

Run: `cd apps/web && npx tsc --noEmit && npm run lint`
Expected: limpo.

- [ ] **Step 22.5: Commit final**

```bash
git add apps/api/tests/integration/test_meta_templates_flow.py
git commit -m "test(meta-templates): integration test do fluxo end-to-end"
```

---

## Verificação Final

- [ ] **Subir docker compose e testar manualmente:**

```bash
docker compose up postgres redis -d
cd apps/api && uv run uvicorn main:app --reload &
cd apps/web && npm run dev &
```

Login admin → `/templates` → criar template com imagem → ver na listagem com PENDING → (opcional) verificar bucket R2 manualmente → excluir → ver some.

- [ ] **Validar disparo:** criar um followup flow com um step apontando para o template criado → enrollar um contato de teste → verificar que ChatNexo recebe o `header_link` correto.

- [ ] **Cleanup:** parar dev server, docker compose down se quiser.

---

## Notas para o executor

- Configure R2 (criar conta Cloudflare se não tiver, gerar API token, criar bucket, ativar Public Development URL) antes de testar manualmente. Para os testes unitários, todos os adapters são mockados.
- `META_APP_ID` deve ser o ID do app Meta no Developer Console — diferente do `META_WABA_ID`.
- A migration deve ser aplicada DEPOIS dos heads atuais. Se houver duas branches ativas, criar manualmente um `down_revision = ("head_a", "head_b")` (merge migration) ou rodar `alembic merge` antes.
- Smoke test do upload requer R2 configurado de verdade. Testes unitários cobrem a lógica sem precisar disso.
- Se o `ConfirmDialog` existente não suportar a `variant="warning"` ou `"destructive"`, ajustar a chamada pra forma que o componente aceita.
- O endpoint `/admin/meta-templates/upload-media` aceita arquivos até 100MB — confirme que o reverse proxy / Cloudflare Tunnel não bloqueia (default Cloudflare é 100MB pra paid, 25MB free).
