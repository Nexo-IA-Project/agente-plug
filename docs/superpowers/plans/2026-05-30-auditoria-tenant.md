# Auditoria por Tenant — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capturar automaticamente todas as ações de escrita do painel admin por tenant e exibi-las em uma página de Auditoria acessível somente ao `role=admin`.

**Architecture:** Middleware FastAPI intercepta POST/PUT/PATCH/DELETE em `/admin/*`, seta `request.state.audit_ctx` via `require_admin` modificado, salva o evento com IP e resolve geolocalização via `asyncio.create_task` (não bloqueia response). Login/logout são auditados diretamente nos seus routers. Frontend expõe `/administracao/auditoria` com tabela paginada e filtros.

**Tech Stack:** Python/FastAPI (Starlette `BaseHTTPMiddleware`), SQLAlchemy async, Alembic, `httpx` async para geo lookup, Next.js 15 App Router, TypeScript, Tailwind + design system NexoIA, Material Symbols.

---

## File Map

**Backend — criar:**
- `apps/api/migrations/versions/a9b0c1d2e3f4_audit_events_expand.py`
- `apps/api/src/shared/domain/ports/audit_repository.py`
- `apps/api/src/shared/adapters/geo/__init__.py`
- `apps/api/src/shared/adapters/geo/port.py`
- `apps/api/src/shared/adapters/geo/ip_api.py`
- `apps/api/src/shared/adapters/db/repositories/audit_repo.py`
- `apps/api/src/shared/application/use_cases/admin/list_audit_events.py`
- `apps/api/src/interface/http/routers/admin/audit.py`
- `apps/api/tests/unit/test_audit_middleware_action_map.py`
- `apps/api/tests/unit/test_audit_repo.py`

**Backend — modificar:**
- `apps/api/src/shared/domain/entities/audit_event.py` — adicionar campos ip/geo/user_id/user_name
- `apps/api/src/shared/domain/permissions/catalog.py` — adicionar `audit.view` + ADMIN_ONLY_KEYS
- `apps/api/src/interface/http/deps/admin_auth.py` — `require_admin` seta `request.state.audit_ctx`
- `apps/api/src/interface/http/middleware.py` — adicionar `AuditMiddleware` + `ACTION_MAP`
- `apps/api/src/interface/http/routers/admin/auth.py` — audit no login
- `apps/api/src/main.py` — registrar middleware + router

**Frontend — criar:**
- `apps/web/src/features/audit/types.ts`
- `apps/web/src/app/(admin)/administracao/auditoria/page.tsx`
- `apps/web/src/features/audit/components/AuditTable.tsx`

**Frontend — modificar:**
- `apps/web/src/lib/api.ts` — adicionar `listAuditEvents`
- `apps/web/src/shared/components/layout/Sidebar.tsx` — grupo "Administração"
- `apps/web/src/features/auth/lib/routePermissions.ts` — mapear `/administracao/auditoria`

---

### Task 1: Migration — expandir `audit_events`

**Files:**
- Create: `apps/api/migrations/versions/a9b0c1d2e3f4_audit_events_expand.py`

- [ ] **Criar o arquivo de migration**

```python
# apps/api/migrations/versions/a9b0c1d2e3f4_audit_events_expand.py
"""audit_events: add ip, geo and user columns

Revision ID: a9b0c1d2e3f4
Revises: c3d4e5f6a7b8
Create Date: 2026-05-30 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a9b0c1d2e3f4"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "audit_events",
        "actor",
        type_=sa.String(120),
        existing_type=sa.String(20),
        existing_nullable=False,
    )
    op.add_column("audit_events", sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("audit_events", sa.Column("user_name", sa.String(120), nullable=True))
    op.add_column("audit_events", sa.Column("ip_address", sa.String(45), nullable=True))
    op.add_column("audit_events", sa.Column("geo_city", sa.String(100), nullable=True))
    op.add_column("audit_events", sa.Column("geo_country", sa.String(100), nullable=True))
    op.add_column("audit_events", sa.Column("geo_region", sa.String(100), nullable=True))
    op.create_index("ix_audit_events_account_user", "audit_events", ["account_id", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_account_user", table_name="audit_events")
    op.drop_column("audit_events", "geo_region")
    op.drop_column("audit_events", "geo_country")
    op.drop_column("audit_events", "geo_city")
    op.drop_column("audit_events", "ip_address")
    op.drop_column("audit_events", "user_name")
    op.drop_column("audit_events", "user_id")
    op.alter_column(
        "audit_events",
        "actor",
        type_=sa.String(20),
        existing_type=sa.String(120),
        existing_nullable=False,
    )
```

- [ ] **Aplicar migration**

```bash
cd apps/api
uv run alembic upgrade heads
```

Esperado: `Running upgrade c3d4e5f6a7b8 -> a9b0c1d2e3f4, audit_events: add ip, geo and user columns`

- [ ] **Commit**

```bash
git add apps/api/migrations/versions/a9b0c1d2e3f4_audit_events_expand.py
git commit -m "feat(audit): migration — expand audit_events with ip/geo/user columns"
```

---

### Task 2: Entidade `AuditEvent` expandida

**Files:**
- Modify: `apps/api/src/shared/domain/entities/audit_event.py`

- [ ] **Substituir o conteúdo completo do arquivo**

```python
# apps/api/src/shared/domain/entities/audit_event.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class AuditEvent:
    id: UUID
    account_id: UUID
    actor: str
    user_id: UUID | None
    user_name: str | None
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    geo_city: str | None
    geo_country: str | None
    geo_region: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    created_at: datetime | None = None
```

- [ ] **Commit**

```bash
git add apps/api/src/shared/domain/entities/audit_event.py
git commit -m "feat(audit): expand AuditEvent entity with ip/geo/user fields"
```

---

### Task 3: Port `AuditRepository`

**Files:**
- Create: `apps/api/src/shared/domain/ports/audit_repository.py`

- [ ] **Criar o arquivo**

```python
# apps/api/src/shared/domain/ports/audit_repository.py
from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from shared.domain.entities.audit_event import AuditEvent


class AuditRepository(Protocol):
    async def save(self, event: AuditEvent) -> None: ...

    async def update_geo(
        self,
        event_id: UUID,
        *,
        city: str,
        country: str,
        region: str,
    ) -> None: ...

    async def paginate(
        self,
        account_id: UUID,
        *,
        user_id: UUID | None = None,
        action: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[AuditEvent], int]: ...
```

- [ ] **Commit**

```bash
git add apps/api/src/shared/domain/ports/audit_repository.py
git commit -m "feat(audit): AuditRepository port (Protocol)"
```

---

### Task 4: GeoService port + implementação `ip-api.com`

**Files:**
- Create: `apps/api/src/shared/adapters/geo/__init__.py`
- Create: `apps/api/src/shared/adapters/geo/port.py`
- Create: `apps/api/src/shared/adapters/geo/ip_api.py`

- [ ] **Criar `__init__.py` (vazio)**

```python
# apps/api/src/shared/adapters/geo/__init__.py
```

- [ ] **Criar `port.py`**

```python
# apps/api/src/shared/adapters/geo/port.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class GeoResult:
    city: str
    country: str
    region: str


class GeoService(Protocol):
    async def lookup(self, ip: str) -> GeoResult | None: ...
```

- [ ] **Criar `ip_api.py`**

```python
# apps/api/src/shared/adapters/geo/ip_api.py
from __future__ import annotations

import httpx

from shared.adapters.geo.port import GeoResult
from shared.adapters.observability.logger import get_logger

log = get_logger(__name__)

_PRIVATE_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.",
                     "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.",
                     "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
                     "192.168.", "127.", "::1", "")


def _is_private(ip: str) -> bool:
    return any(ip.startswith(p) for p in _PRIVATE_PREFIXES)


class IpApiGeoService:
    """Resolve geolocalização via ip-api.com (gratuito, sem chave, ~45 req/min)."""

    async def lookup(self, ip: str) -> GeoResult | None:
        if _is_private(ip):
            return None
        url = f"http://ip-api.com/json/{ip}?fields=status,city,country,regionName"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                data = resp.json()
                if data.get("status") != "success":
                    return None
                return GeoResult(
                    city=data.get("city", ""),
                    country=data.get("country", ""),
                    region=data.get("regionName", ""),
                )
        except Exception:
            log.warning("geo_lookup_failed", ip=ip)
            return None
```

- [ ] **Commit**

```bash
git add apps/api/src/shared/adapters/geo/
git commit -m "feat(audit): GeoService port + IpApiGeoService implementation"
```

---

### Task 5: `SqlAuditRepository`

**Files:**
- Create: `apps/api/src/shared/adapters/db/repositories/audit_repo.py`
- Create: `apps/api/tests/unit/test_audit_repo.py`

- [ ] **Escrever o teste unitário (falha primeiro)**

```python
# apps/api/tests/unit/test_audit_repo.py
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from shared.adapters.db.repositories.audit_repo import SqlAuditRepository


def test_repo_initializes_with_session():
    session = AsyncMock()
    repo = SqlAuditRepository(session=session)
    assert repo.session is session


@pytest.mark.asyncio
async def test_paginate_returns_empty_list_when_no_events():
    session = AsyncMock()
    count_result = AsyncMock()
    count_result.scalar_one = lambda: 0
    list_result = AsyncMock()
    list_result.scalars = lambda: type("S", (), {"all": lambda *_: []})()
    session.execute = AsyncMock(side_effect=[count_result, list_result])

    repo = SqlAuditRepository(session=session)
    items, total = await repo.paginate(uuid4())

    assert items == []
    assert total == 0
    assert session.execute.call_count == 2
```

- [ ] **Rodar o teste — deve falhar**

```bash
cd apps/api
uv run pytest tests/unit/test_audit_repo.py -v
```

Esperado: `ImportError` ou `ModuleNotFoundError` (arquivo ainda não existe)

- [ ] **Criar `audit_repo.py`**

```python
# apps/api/src/shared/adapters/db/repositories/audit_repo.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import AuditEventModel
from shared.domain.entities.audit_event import AuditEvent


def _to_entity(m: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        id=m.id,
        account_id=m.account_id,
        actor=m.actor,
        user_id=m.user_id,
        user_name=m.user_name,
        action=m.action,
        resource_type=m.resource_type,
        resource_id=m.resource_id,
        ip_address=m.ip_address,
        geo_city=m.geo_city,
        geo_country=m.geo_country,
        geo_region=m.geo_region,
        metadata=m.metadata_json,
        correlation_id=m.correlation_id,
        created_at=m.created_at,
    )


class SqlAuditRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def save(self, event: AuditEvent) -> None:
        model = AuditEventModel(
            id=event.id,
            account_id=event.account_id,
            actor=event.actor,
            user_id=event.user_id,
            user_name=event.user_name,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            ip_address=event.ip_address,
            geo_city=event.geo_city,
            geo_country=event.geo_country,
            geo_region=event.geo_region,
            metadata_json=event.metadata,
            correlation_id=event.correlation_id,
        )
        self.session.add(model)
        await self.session.commit()

    async def update_geo(
        self,
        event_id: UUID,
        *,
        city: str,
        country: str,
        region: str,
    ) -> None:
        await self.session.execute(
            update(AuditEventModel)
            .where(AuditEventModel.id == event_id)
            .values(geo_city=city, geo_country=country, geo_region=region)
        )
        await self.session.commit()

    async def paginate(
        self,
        account_id: UUID,
        *,
        user_id: UUID | None = None,
        action: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[AuditEvent], int]:
        base = select(AuditEventModel).where(AuditEventModel.account_id == account_id)
        if user_id is not None:
            base = base.where(AuditEventModel.user_id == user_id)
        if action is not None:
            base = base.where(AuditEventModel.action == action)
        if date_from is not None:
            base = base.where(AuditEventModel.created_at >= date_from)
        if date_to is not None:
            base = base.where(AuditEventModel.created_at <= date_to)

        count_q = select(func.count()).select_from(base.subquery())
        total = (await self.session.execute(count_q)).scalar_one()

        rows = (
            await self.session.execute(
                base.order_by(AuditEventModel.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        return [_to_entity(r) for r in rows], total
```

- [ ] **Atualizar `AuditEventModel` em `models.py`** para incluir as novas colunas

Abrir `apps/api/src/shared/adapters/db/models.py` e localizar a classe `AuditEventModel`. Substituir por:

```python
class AuditEventModel(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    user_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80))
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    geo_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geo_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geo_region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    __table_args__ = (
        Index("ix_audit_events_account_created", "account_id", "created_at"),
        Index("ix_audit_events_account_user", "account_id", "user_id"),
    )
```

- [ ] **Rodar o teste — deve passar**

```bash
cd apps/api
uv run pytest tests/unit/test_audit_repo.py -v
```

Esperado: `PASSED` em ambos os testes

- [ ] **Commit**

```bash
git add apps/api/src/shared/adapters/db/models.py \
        apps/api/src/shared/adapters/db/repositories/audit_repo.py \
        apps/api/tests/unit/test_audit_repo.py
git commit -m "feat(audit): SqlAuditRepository + AuditEventModel columns"
```

---

### Task 6: Permissão `audit.view`

**Files:**
- Modify: `apps/api/src/shared/domain/permissions/catalog.py`

- [ ] **Verificar o teste existente antes de modificar**

```bash
cd apps/api
uv run pytest tests/unit/test_permission_catalog.py -v
```

Esperado: todos `PASSED`

- [ ] **Adicionar permissão ao catálogo**

Em `apps/api/src/shared/domain/permissions/catalog.py`, localizar a lista `PERMISSION_CATALOG` e adicionar ao final (antes do fechamento da lista):

```python
    _p("audit", "view", "Ver auditoria"),
```

Na constante `ADMIN_ONLY_KEYS`, adicionar `"audit.view"`:

```python
ADMIN_ONLY_KEYS: frozenset[str] = frozenset(
    {
        "users.manage",
        "profiles.view",
        "profiles.manage",
        "templates.delete",
        "kb.delete",
        "tokens.manage",
        "settings.edit_credentials",
        "settings.edit_smtp",
        "audit.view",
    }
)
```

- [ ] **Rodar testes de permissão — devem passar**

```bash
cd apps/api
uv run pytest tests/unit/test_permission_catalog.py -v
```

Esperado: todos `PASSED` (o count de perms aumentou mas os testes só checam unicidade e módulos core)

- [ ] **Commit**

```bash
git add apps/api/src/shared/domain/permissions/catalog.py
git commit -m "feat(audit): add audit.view permission (admin-only)"
```

---

### Task 7: `require_admin` seta `request.state.audit_ctx`

**Files:**
- Modify: `apps/api/src/interface/http/deps/admin_auth.py`

- [ ] **Modificar `require_admin` para injetar Request e setar audit_ctx**

Localizar a função `require_admin` e substituir por:

```python
async def require_admin(
    request: Request,
    authorization: str | None = Header(default=None),
    nexoia_token: str | None = Cookie(default=None),
) -> AdminAuth:
    from fastapi import Request as _Request  # noqa: F401 — import já no topo
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
    auth = _decode(token)
    request.state.audit_ctx = {
        "account_id": auth.account_id,
        "user_id": auth.user_id,
        "user_email": auth.user_email,
    }
    return auth
```

Adicionar o import de `Request` no topo do arquivo (se não existir):

```python
from fastapi import Cookie, Depends, Header, HTTPException, Query, Request, status
```

- [ ] **Rodar mypy para verificar tipagem**

```bash
cd apps/api
uv run mypy src/interface/http/deps/admin_auth.py
```

Esperado: sem erros

- [ ] **Commit**

```bash
git add apps/api/src/interface/http/deps/admin_auth.py
git commit -m "feat(audit): require_admin sets request.state.audit_ctx"
```

---

### Task 8: `AuditMiddleware` + `ACTION_MAP`

**Files:**
- Modify: `apps/api/src/interface/http/middleware.py`
- Create: `apps/api/tests/unit/test_audit_middleware_action_map.py`

- [ ] **Escrever teste do ACTION_MAP (falha primeiro)**

```python
# apps/api/tests/unit/test_audit_middleware_action_map.py
import pytest
from interface.http.middleware import resolve_audit_action


@pytest.mark.parametrize("method,path,expected_label,expected_resource", [
    ("POST", "/admin/auth/login", None, None),          # login auditado no router, não aqui
    ("POST", "/admin/users", "Criou usuário", "user"),
    ("PUT", "/admin/users/abc-123", "Editou usuário", "user"),
    ("DELETE", "/admin/users/abc-123", "Excluiu usuário", "user"),
    ("POST", "/admin/users/abc-123/reset-password", "Resetou senha de usuário", "user"),
    ("PUT", "/admin/me/password", "Alterou própria senha", "user"),
    ("POST", "/admin/products", "Criou produto", "product"),
    ("DELETE", "/admin/products/abc-123", "Excluiu produto", "product"),
    ("POST", "/admin/followup/flows", "Criou flow de follow-up", "flow"),
    ("DELETE", "/admin/followup/flows/abc/steps/def", "Excluiu step do flow", "flow_step"),
    ("PUT", "/admin/settings", "Editou configurações", "settings"),
    ("POST", "/admin/api-tokens", "Criou token de API", "api_token"),
    ("DELETE", "/admin/api-tokens/abc-123", "Revogou token de API", "api_token"),
    ("POST", "/admin/profiles", "Criou perfil", "profile"),
    ("DELETE", "/admin/profiles/abc-123", "Excluiu perfil", "profile"),
    ("POST", "/admin/dlq/abc/requeue", "Reprocessou job DLQ", "dlq"),
    ("GET", "/admin/leads", None, None),                # GET ignorado
    ("POST", "/admin/search/test", None, None),         # path sem mapeamento
])
def test_resolve_audit_action(method, path, expected_label, expected_resource):
    result = resolve_audit_action(method, path)
    if expected_label is None:
        assert result is None
    else:
        assert result is not None
        label, resource_type = result
        assert label == expected_label
        assert resource_type == expected_resource
```

- [ ] **Rodar o teste — deve falhar**

```bash
cd apps/api
uv run pytest tests/unit/test_audit_middleware_action_map.py -v
```

Esperado: `ImportError` (função ainda não existe)

- [ ] **Adicionar `AuditMiddleware` e `resolve_audit_action` ao `middleware.py`**

Adicionar no final do arquivo `apps/api/src/interface/http/middleware.py`:

```python
import asyncio
import re
from uuid import UUID, uuid4

from shared.adapters.db.repositories.audit_repo import SqlAuditRepository
from shared.adapters.geo.ip_api import IpApiGeoService
from shared.adapters.observability.logger import get_logger
from shared.domain.entities.audit_event import AuditEvent

_audit_log = get_logger(__name__)

# (method, path_regex, label, resource_type)
_ACTION_RULES: list[tuple[str, re.Pattern[str], str, str]] = [
    ("POST",   re.compile(r"^/admin/users/[^/]+/reset-password$"), "Resetou senha de usuário", "user"),
    ("POST",   re.compile(r"^/admin/users$"),                      "Criou usuário",            "user"),
    ("PUT",    re.compile(r"^/admin/users/[^/]+$"),                "Editou usuário",           "user"),
    ("DELETE", re.compile(r"^/admin/users/[^/]+$"),                "Excluiu usuário",          "user"),
    ("PUT",    re.compile(r"^/admin/me/password$"),                "Alterou própria senha",    "user"),
    ("PUT",    re.compile(r"^/admin/me/avatar$"),                  "Alterou avatar",           "user"),
    ("PUT",    re.compile(r"^/admin/me$"),                         "Editou perfil próprio",    "user"),
    ("POST",   re.compile(r"^/admin/products$"),                   "Criou produto",            "product"),
    ("PUT",    re.compile(r"^/admin/products/[^/]+$"),             "Editou produto",           "product"),
    ("DELETE", re.compile(r"^/admin/products/[^/]+$"),             "Excluiu produto",          "product"),
    ("POST",   re.compile(r"^/admin/documents/upload$"),           "Enviou documento KB",      "document"),
    ("DELETE", re.compile(r"^/admin/documents/[^/]+$"),            "Excluiu documento KB",     "document"),
    ("POST",   re.compile(r"^/admin/followup/flows/[^/]+/steps$"), "Adicionou step ao flow",   "flow_step"),
    ("PUT",    re.compile(r"^/admin/followup/flows/[^/]+/steps/[^/]+$"), "Editou step do flow",    "flow_step"),
    ("DELETE", re.compile(r"^/admin/followup/flows/[^/]+/steps/[^/]+$"), "Excluiu step do flow",   "flow_step"),
    ("PATCH",  re.compile(r"^/admin/followup/flows/[^/]+/steps/reorder$"), "Reordenou steps do flow", "flow_step"),
    ("POST",   re.compile(r"^/admin/followup/flows$"),             "Criou flow de follow-up",  "flow"),
    ("PUT",    re.compile(r"^/admin/followup/flows/[^/]+$"),       "Editou flow de follow-up", "flow"),
    ("DELETE", re.compile(r"^/admin/followup/flows/[^/]+$"),       "Excluiu flow de follow-up","flow"),
    ("POST",   re.compile(r"^/admin/meta-templates$"),             "Criou template Meta",      "meta_template"),
    ("DELETE", re.compile(r"^/admin/meta-templates/[^/]+$"),       "Excluiu template Meta",    "meta_template"),
    ("PUT",    re.compile(r"^/admin/settings$"),                   "Editou configurações",     "settings"),
    ("PUT",    re.compile(r"^/admin/smtp-config$"),                "Editou configuração SMTP", "settings"),
    ("POST",   re.compile(r"^/admin/api-tokens$"),                 "Criou token de API",       "api_token"),
    ("DELETE", re.compile(r"^/admin/api-tokens/[^/]+$"),           "Revogou token de API",     "api_token"),
    ("POST",   re.compile(r"^/admin/profiles$"),                   "Criou perfil",             "profile"),
    ("PUT",    re.compile(r"^/admin/profiles/[^/]+$"),             "Editou perfil",            "profile"),
    ("DELETE", re.compile(r"^/admin/profiles/[^/]+$"),             "Excluiu perfil",           "profile"),
    ("POST",   re.compile(r"^/admin/dlq/requeue-all$"),            "Reprocessou todos os jobs DLQ", "dlq"),
    ("POST",   re.compile(r"^/admin/dlq/[^/]+/requeue$"),          "Reprocessou job DLQ",      "dlq"),
    ("DELETE", re.compile(r"^/admin/dlq/[^/]+$"),                  "Excluiu job DLQ",          "dlq"),
]

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def resolve_audit_action(method: str, path: str) -> tuple[str, str] | None:
    """Retorna (label, resource_type) ou None se o path não deve ser auditado."""
    if method not in _WRITE_METHODS:
        return None
    for rule_method, pattern, label, resource_type in _ACTION_RULES:
        if method == rule_method and pattern.match(path):
            return label, resource_type
    return None


def _extract_ip(request: Request) -> str:
    cf = request.headers.get("CF-Connecting-IP")
    if cf:
        return cf.strip()
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


def _extract_resource_id(path: str, resource_type: str) -> str | None:
    # Tenta extrair o último segmento UUID-like do path como resource_id
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[-1] not in {"upload", "reorder", "requeue", "requeue-all"}:
        return parts[-1]
    return None


async def _do_geo_update(event_id: UUID, ip: str) -> None:
    from shared.adapters.db.session import session_scope
    geo = IpApiGeoService()
    result = await geo.lookup(ip)
    if result is None:
        return
    async with session_scope() as session:
        repo = SqlAuditRepository(session=session)
        await repo.update_geo(event_id, city=result.city, country=result.country, region=result.region)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        audit_ctx = getattr(request.state, "audit_ctx", None)
        if audit_ctx is None:
            return response

        action_result = resolve_audit_action(request.method, request.url.path)
        if action_result is None:
            return response

        label, resource_type = action_result
        ip = _extract_ip(request)
        resource_id = _extract_resource_id(request.url.path, resource_type)

        account_id: UUID | None = audit_ctx.get("account_id")
        if account_id is None:
            return response

        event_id = uuid4()
        event = AuditEvent(
            id=event_id,
            account_id=account_id,
            actor=audit_ctx.get("user_email", ""),
            user_id=_parse_uuid(audit_ctx.get("user_id")),
            user_name=audit_ctx.get("user_email"),
            action=label,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip or None,
            geo_city=None,
            geo_country=None,
            geo_region=None,
        )

        try:
            from shared.adapters.db.session import session_scope
            async with session_scope() as session:
                repo = SqlAuditRepository(session=session)
                await repo.save(event)
            if ip:
                asyncio.create_task(_do_geo_update(event_id, ip))
        except Exception:
            _audit_log.warning("audit_save_failed", path=request.url.path)

        return response


def _parse_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None
```

- [ ] **Rodar o teste — deve passar**

```bash
cd apps/api
uv run pytest tests/unit/test_audit_middleware_action_map.py -v
```

Esperado: todos `PASSED`

- [ ] **Commit**

```bash
git add apps/api/src/interface/http/middleware.py \
        apps/api/tests/unit/test_audit_middleware_action_map.py
git commit -m "feat(audit): AuditMiddleware + ACTION_MAP with unit tests"
```

---

### Task 9: Audit de login e logout no router de auth

**Files:**
- Modify: `apps/api/src/interface/http/routers/admin/auth.py`

- [ ] **Adicionar gravação de evento de login após autenticação bem-sucedida**

Em `apps/api/src/interface/http/routers/admin/auth.py`, adicionar os imports no topo:

```python
import asyncio
from uuid import uuid4

from fastapi import Request
```

Modificar a assinatura do endpoint `login` para aceitar `request: Request`:

```python
@router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response) -> LoginResponse:
```

Após o bloco `await session.commit()` (dentro do `async with get_db() as session:`), adicionar a chamada de auditoria **antes** de criar o token:

```python
        # Auditoria de login (fora do with para não travar a sessão)
        _login_account_id = snapshot["account_id"]
        _login_user_id = snapshot["id"]
        _login_email = snapshot["email"]

    # registra evento de login em task separada para não bloquear
    asyncio.create_task(_save_login_audit(
        account_id=_login_account_id,
        user_id=_login_user_id,
        user_email=_login_email,
        ip=_extract_login_ip(request),
    ))
```

Adicionar as funções auxiliares antes do router (após os imports):

```python
def _extract_login_ip(request: Request) -> str:
    cf = request.headers.get("CF-Connecting-IP")
    if cf:
        return cf.strip()
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


async def _save_login_audit(*, account_id, user_id, user_email: str, ip: str) -> None:
    from uuid import UUID as _UUID
    from shared.adapters.db.repositories.audit_repo import SqlAuditRepository
    from shared.adapters.db.session import session_scope
    from shared.adapters.geo.ip_api import IpApiGeoService
    from shared.domain.entities.audit_event import AuditEvent

    event_id = uuid4()
    try:
        event = AuditEvent(
            id=event_id,
            account_id=account_id,
            actor=user_email,
            user_id=user_id if isinstance(user_id, _UUID) else None,
            user_name=user_email,
            action="Login",
            resource_type="auth",
            resource_id=None,
            ip_address=ip or None,
            geo_city=None, geo_country=None, geo_region=None,
        )
        async with session_scope() as session:
            repo = SqlAuditRepository(session=session)
            await repo.save(event)
        if ip:
            geo = IpApiGeoService()
            result = await geo.lookup(ip)
            if result:
                async with session_scope() as session:
                    repo = SqlAuditRepository(session=session)
                    await repo.update_geo(event_id, city=result.city, country=result.country, region=result.region)
    except Exception:
        pass
```

- [ ] **Adicionar audit de logout**

O endpoint `logout` atualmente não usa `require_admin`. Modificar para aceitar auth opcional e logar se tiver JWT válido:

```python
@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    nexoia_token: str | None = Cookie(default=None),
) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path="/", samesite="lax")
    # tenta auditar — falha silenciosa se sem JWT válido
    token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif nexoia_token:
        token = nexoia_token
    if token:
        try:
            from shared.adapters.kb.jwt_handler import verify_token
            settings = get_settings()
            payload = verify_token(token, secret=settings.jwt_secret)
            asyncio.create_task(_save_login_audit(
                account_id=payload.get("account_id"),
                user_id=payload.get("user_id"),
                user_email=payload.get("sub", ""),
                ip=_extract_login_ip(request),
                action="Logout",
            ))
        except Exception:
            pass
```

Atualizar `_save_login_audit` para aceitar o parâmetro `action`:

```python
async def _save_login_audit(*, account_id, user_id, user_email: str, ip: str, action: str = "Login") -> None:
    from uuid import UUID as _UUID
    from shared.adapters.db.repositories.audit_repo import SqlAuditRepository
    from shared.adapters.db.session import session_scope
    from shared.adapters.geo.ip_api import IpApiGeoService
    from shared.domain.entities.audit_event import AuditEvent

    event_id = uuid4()
    try:
        _account_id = _UUID(str(account_id)) if account_id else None
        if _account_id is None:
            return
        event = AuditEvent(
            id=event_id,
            account_id=_account_id,
            actor=user_email,
            user_id=_UUID(str(user_id)) if user_id else None,
            user_name=user_email,
            action=action,
            resource_type="auth",
            resource_id=None,
            ip_address=ip or None,
            geo_city=None, geo_country=None, geo_region=None,
        )
        async with session_scope() as session:
            repo = SqlAuditRepository(session=session)
            await repo.save(event)
        if ip:
            geo = IpApiGeoService()
            result = await geo.lookup(ip)
            if result:
                async with session_scope() as session:
                    repo = SqlAuditRepository(session=session)
                    await repo.update_geo(event_id, city=result.city, country=result.country, region=result.region)
    except Exception:
        pass
```

- [ ] **Rodar mypy**

```bash
cd apps/api
uv run mypy src/interface/http/routers/admin/auth.py
```

Esperado: sem erros

- [ ] **Commit**

```bash
git add apps/api/src/interface/http/routers/admin/auth.py
git commit -m "feat(audit): log login and logout events in auth router"
```

---

### Task 10: Use case `ListAuditEvents`

**Files:**
- Create: `apps/api/src/shared/application/use_cases/admin/list_audit_events.py`

- [ ] **Criar o arquivo**

```python
# apps/api/src/shared/application/use_cases/admin/list_audit_events.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared.domain.entities.audit_event import AuditEvent
from shared.domain.ports.audit_repository import AuditRepository


@dataclass
class ListAuditEventsInput:
    account_id: UUID
    user_id: UUID | None = None
    action: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = 1
    page_size: int = 25


@dataclass
class ListAuditEventsOutput:
    items: list[AuditEvent]
    total: int
    page: int
    page_size: int


class ListAuditEventsUseCase:
    def __init__(self, *, repo: AuditRepository) -> None:
        self._repo = repo

    async def execute(self, inp: ListAuditEventsInput) -> ListAuditEventsOutput:
        page_size = min(inp.page_size, 100)
        items, total = await self._repo.paginate(
            inp.account_id,
            user_id=inp.user_id,
            action=inp.action,
            date_from=inp.date_from,
            date_to=inp.date_to,
            page=inp.page,
            page_size=page_size,
        )
        return ListAuditEventsOutput(
            items=items,
            total=total,
            page=inp.page,
            page_size=page_size,
        )
```

- [ ] **Commit**

```bash
git add apps/api/src/shared/application/use_cases/admin/list_audit_events.py
git commit -m "feat(audit): ListAuditEventsUseCase"
```

---

### Task 11: Router `GET /admin/audit-events`

**Files:**
- Create: `apps/api/src/interface/http/routers/admin/audit.py`

- [ ] **Criar o router**

```python
# apps/api/src/interface/http/routers/admin/audit.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from interface.http.deps.admin_auth import AdminAuth
from interface.http.deps.permissions import require_permission
from shared.adapters.db.repositories.audit_repo import SqlAuditRepository
from shared.adapters.db.session import session_scope
from shared.application.use_cases.admin.list_audit_events import (
    ListAuditEventsInput,
    ListAuditEventsUseCase,
)
from shared.domain.entities.audit_event import AuditEvent

router = APIRouter(tags=["admin-audit"])


class AuditEventResponse(BaseModel):
    id: UUID
    user_name: str | None
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    geo_city: str | None
    geo_country: str | None
    geo_region: str | None
    created_at: datetime


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
    total: int
    page: int
    page_size: int


def _to_response(e: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=e.id,
        user_name=e.user_name,
        action=e.action,
        resource_type=e.resource_type,
        resource_id=e.resource_id,
        ip_address=e.ip_address,
        geo_city=e.geo_city,
        geo_country=e.geo_country,
        geo_region=e.geo_region,
        created_at=e.created_at,
    )


@router.get("/audit-events", response_model=AuditEventListResponse)
async def list_audit_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    user_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    auth: AdminAuth = Depends(require_permission("audit.view")),
) -> AuditEventListResponse:
    if auth.account_id is None:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(status_code=400, detail="account_id ausente no token")
    async with session_scope() as session:
        repo = SqlAuditRepository(session=session)
        use_case = ListAuditEventsUseCase(repo=repo)
        result = await use_case.execute(
            ListAuditEventsInput(
                account_id=auth.account_id,
                user_id=user_id,
                action=action,
                date_from=date_from,
                date_to=date_to,
                page=page,
                page_size=page_size,
            )
        )
    return AuditEventListResponse(
        items=[_to_response(e) for e in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
```

- [ ] **Commit**

```bash
git add apps/api/src/interface/http/routers/admin/audit.py
git commit -m "feat(audit): GET /admin/audit-events router"
```

---

### Task 12: Registrar middleware e router em `main.py`

**Files:**
- Modify: `apps/api/src/main.py`

- [ ] **Adicionar imports no topo de `main.py`**

Após o import de `CorrelationIdMiddleware`:

```python
from interface.http.middleware import AuditMiddleware
from interface.http.routers.admin import audit as admin_audit
```

- [ ] **Registrar `AuditMiddleware` na função `create_app`**

Após `app.add_middleware(CorrelationIdMiddleware)`, adicionar:

```python
    app.add_middleware(AuditMiddleware)
```

- [ ] **Registrar o router de audit**

Na lista de `app.include_router`, adicionar:

```python
    app.include_router(admin_audit.router, prefix="/admin")
```

- [ ] **Rodar o servidor e verificar que sobe sem erros**

```bash
cd apps/api
uv run uvicorn main:app --reload
```

Esperado: `Application startup complete.` sem erros. Pressionar Ctrl+C.

- [ ] **Rodar mypy na interface**

```bash
cd apps/api
uv run mypy src/main.py src/interface/http/middleware.py
```

Esperado: sem erros

- [ ] **Rodar testes unitários completos**

```bash
cd apps/api
uv run pytest tests/unit -v --tb=short
```

Esperado: todos passando

- [ ] **Commit**

```bash
git add apps/api/src/main.py
git commit -m "feat(audit): register AuditMiddleware and audit router in app"
```

---

### Task 13: Frontend — tipos e função de API

**Files:**
- Create: `apps/web/src/features/audit/types.ts`
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Criar `features/audit/types.ts`**

```typescript
// apps/web/src/features/audit/types.ts
export interface AuditEventItem {
  id: string;
  user_name: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string | null;
  geo_city: string | null;
  geo_country: string | null;
  geo_region: string | null;
  created_at: string;
}

export interface AuditEventListResponse {
  items: AuditEventItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditFilters {
  user_id?: string;
  action?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}
```

- [ ] **Adicionar `listAuditEvents` em `apps/web/src/lib/api.ts`**

Ao final do arquivo, antes do último export (ou no bloco de audit), adicionar:

```typescript
export async function listAuditEvents(params: {
  page?: number;
  page_size?: number;
  user_id?: string;
  action?: string;
  date_from?: string;
  date_to?: string;
} = {}): Promise<import("@/features/audit/types").AuditEventListResponse> {
  const qs = new URLSearchParams();
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  if (params.user_id) qs.set("user_id", params.user_id);
  if (params.action) qs.set("action", params.action);
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  return apiFetch(`/admin/audit-events?${qs.toString()}`);
}
```

- [ ] **Verificar typecheck**

```bash
cd apps/web
npx tsc --noEmit
```

Esperado: sem erros

- [ ] **Commit**

```bash
git add apps/web/src/features/audit/types.ts apps/web/src/lib/api.ts
git commit -m "feat(audit): frontend types + listAuditEvents API function"
```

---

### Task 14: Página de Auditoria

**Files:**
- Create: `apps/web/src/features/audit/components/AuditTable.tsx`
- Create: `apps/web/src/app/(admin)/administracao/auditoria/page.tsx`

- [ ] **Criar `AuditTable.tsx`**

Usar o skill `frontend-design` para gerar a tabela com design NexoIA de alta qualidade. O componente deve:
- Receber `items: AuditEventItem[]` e `isLoading: boolean` como props
- Exibir colunas: **Usuário** (`user_name` ou "—"), **Ação** (`action` com chip colorido por `resource_type`), **IP · Localidade** (`ip_address` + `geo_city, geo_country` ou só IP como fallback), **Data e Hora** (formatada em pt-BR)
- Skeleton loader quando `isLoading = true` (3 linhas)
- Linha vazia ("Nenhuma ação registrada") quando `items` vazio
- Seguir tokens NexoIA: `bg-surface-container`, `text-on-surface`, `border-outline-variant`, etc.
- Ícone Material Symbols `history` para o estado vazio

```typescript
// apps/web/src/features/audit/components/AuditTable.tsx
"use client";

import type { AuditEventItem } from "@/features/audit/types";

const RESOURCE_COLORS: Record<string, string> = {
  auth:          "bg-primary-container text-on-primary-container",
  user:          "bg-secondary-container text-on-secondary-container",
  product:       "bg-tertiary-container text-on-tertiary-container",
  flow:          "bg-[color:var(--color-emerald-container,#d1fae5)] text-[color:var(--color-on-emerald-container,#064e3b)]",
  flow_step:     "bg-[color:var(--color-sky-container,#e0f2fe)] text-[color:var(--color-on-sky-container,#0c4a6e)]",
  document:      "bg-surface-container-high text-on-surface-variant",
  meta_template: "bg-[color:var(--color-violet-container,#ede9fe)] text-[color:var(--color-on-violet-container,#4c1d95)]",
  settings:      "bg-error-container text-on-error-container",
  api_token:     "bg-surface-container-highest text-on-surface",
  profile:       "bg-secondary-container text-on-secondary-container",
  dlq:           "bg-error-container text-on-error-container",
};

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).format(new Date(iso));
}

interface Props {
  items: AuditEventItem[];
  isLoading: boolean;
}

export function AuditTable({ items, isLoading }: Props) {
  if (isLoading) {
    return (
      <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-outline-variant">
              <th className="px-4 py-3 text-left font-medium text-on-surface-variant">Usuário</th>
              <th className="px-4 py-3 text-left font-medium text-on-surface-variant">Ação</th>
              <th className="px-4 py-3 text-left font-medium text-on-surface-variant">IP · Localidade</th>
              <th className="px-4 py-3 text-left font-medium text-on-surface-variant">Data e Hora</th>
            </tr>
          </thead>
          <tbody>
            {[...Array(3)].map((_, i) => (
              <tr key={i} className="border-b border-outline-variant last:border-0">
                {[...Array(4)].map((_, j) => (
                  <td key={j} className="px-4 py-3">
                    <div className="h-4 animate-pulse rounded bg-surface-container-high" />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex min-h-[200px] items-center justify-center rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
        <div className="flex flex-col items-center gap-2 text-on-surface-variant">
          <span className="material-symbols-outlined" style={{ fontSize: "40px" }}>history</span>
          <p className="text-sm">Nenhuma ação registrada</p>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-outline-variant">
            <th className="px-4 py-3 text-left font-medium text-on-surface-variant">Usuário</th>
            <th className="px-4 py-3 text-left font-medium text-on-surface-variant">Ação</th>
            <th className="px-4 py-3 text-left font-medium text-on-surface-variant">IP · Localidade</th>
            <th className="px-4 py-3 text-left font-medium text-on-surface-variant">Data e Hora</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const colorClass = RESOURCE_COLORS[item.resource_type] ?? "bg-surface-container-high text-on-surface";
            const locality = item.geo_city
              ? `${item.geo_city}, ${item.geo_country}`
              : (item.ip_address ?? "—");
            return (
              <tr key={item.id} className="border-b border-outline-variant last:border-0 hover:bg-surface-container-low transition-colors">
                <td className="px-4 py-3 text-on-surface">
                  {item.user_name ?? <span className="text-on-surface-variant">—</span>}
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${colorClass}`}>
                    {item.action}
                  </span>
                </td>
                <td className="px-4 py-3 text-on-surface-variant font-mono text-xs">
                  <div>{item.ip_address ?? "—"}</div>
                  {item.geo_city && (
                    <div className="text-on-surface-variant/70">{locality}</div>
                  )}
                </td>
                <td className="px-4 py-3 text-on-surface-variant">{formatDate(item.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Criar `page.tsx` da auditoria**

```typescript
// apps/web/src/app/(admin)/administracao/auditoria/page.tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { listAuditEvents } from "@/lib/api";
import { RequirePermission } from "@/features/auth/components/RequirePermission";
import { AuditTable } from "@/features/audit/components/AuditTable";
import type { AuditEventItem, AuditFilters } from "@/features/audit/types";

const ACTION_OPTIONS = [
  "Login", "Criou usuário", "Editou usuário", "Excluiu usuário",
  "Resetou senha de usuário", "Alterou própria senha", "Alterou avatar",
  "Editou perfil próprio", "Criou produto", "Editou produto", "Excluiu produto",
  "Enviou documento KB", "Excluiu documento KB", "Criou flow de follow-up",
  "Editou flow de follow-up", "Excluiu flow de follow-up", "Adicionou step ao flow",
  "Editou step do flow", "Excluiu step do flow", "Reordenou steps do flow",
  "Criou template Meta", "Excluiu template Meta", "Editou configurações",
  "Editou configuração SMTP", "Criou token de API", "Revogou token de API",
  "Criou perfil", "Editou perfil", "Excluiu perfil",
  "Reprocessou job DLQ", "Reprocessou todos os jobs DLQ", "Excluiu job DLQ",
];

export default function AuditoriaPage() {
  const [items, setItems] = useState<AuditEventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState<AuditFilters>({ page_size: 25 });

  const load = useCallback(async (f: AuditFilters, p: number) => {
    setIsLoading(true);
    try {
      const res = await listAuditEvents({ ...f, page: p });
      setItems(res.items);
      setTotal(res.total);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { load(filters, page); }, [filters, page, load]);

  const totalPages = Math.ceil(total / (filters.page_size ?? 25));

  return (
    <RequirePermission perm="audit.view">
      <div className="space-y-6 p-6">
        {/* Header */}
        <header className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
          <div className="flex items-center gap-5 px-7 py-6">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-secondary-container">
              <span
                className="material-symbols-outlined text-on-secondary-container"
                style={{ fontSize: "28px", fontVariationSettings: "'FILL' 1" }}
              >
                policy
              </span>
            </div>
            <div>
              <p className="text-xs font-medium text-on-surface-variant">Administração</p>
              <h1 className="mt-0.5 text-2xl font-bold text-on-surface">Auditoria</h1>
              <p className="mt-1 text-sm text-on-surface-variant">
                Registro de todas as ações realizadas no painel.
              </p>
            </div>
          </div>
        </header>

        {/* Filtros */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-on-surface-variant">Ação</label>
            <select
              className="rounded-xl border border-outline-variant bg-white dark:bg-surface-container px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              value={filters.action ?? ""}
              onChange={(e) => {
                setPage(1);
                setFilters((f) => ({ ...f, action: e.target.value || undefined }));
              }}
            >
              <option value="">Todas as ações</option>
              {ACTION_OPTIONS.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-on-surface-variant">De</label>
            <input
              type="datetime-local"
              className="rounded-xl border border-outline-variant bg-white dark:bg-surface-container px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              value={filters.date_from ?? ""}
              onChange={(e) => {
                setPage(1);
                setFilters((f) => ({ ...f, date_from: e.target.value || undefined }));
              }}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-on-surface-variant">Até</label>
            <input
              type="datetime-local"
              className="rounded-xl border border-outline-variant bg-white dark:bg-surface-container px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              value={filters.date_to ?? ""}
              onChange={(e) => {
                setPage(1);
                setFilters((f) => ({ ...f, date_to: e.target.value || undefined }));
              }}
            />
          </div>

          {(filters.action || filters.date_from || filters.date_to) && (
            <button
              onClick={() => { setPage(1); setFilters({ page_size: 25 }); }}
              className="flex items-center gap-1 rounded-xl border border-outline-variant px-3 py-2 text-sm text-on-surface-variant transition-colors hover:bg-surface-container-high"
            >
              <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>close</span>
              Limpar
            </button>
          )}
        </div>

        {/* Tabela */}
        <AuditTable items={items} isLoading={isLoading} />

        {/* Paginação */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-on-surface-variant">
              {total} registro{total !== 1 ? "s" : ""}
            </p>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="flex h-9 w-9 items-center justify-center rounded-xl border border-outline-variant text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:opacity-40"
              >
                <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>chevron_left</span>
              </button>
              <span className="text-sm text-on-surface">
                {page} / {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="flex h-9 w-9 items-center justify-center rounded-xl border border-outline-variant text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:opacity-40"
              >
                <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>chevron_right</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </RequirePermission>
  );
}
```

- [ ] **Verificar typecheck**

```bash
cd apps/web
npx tsc --noEmit
```

Esperado: sem erros

- [ ] **Commit**

```bash
git add apps/web/src/features/audit/ \
        apps/web/src/app/\(admin\)/administracao/
git commit -m "feat(audit): audit page + AuditTable component"
```

---

### Task 15: Sidebar — grupo "Administração"

**Files:**
- Modify: `apps/web/src/shared/components/layout/Sidebar.tsx`
- Modify: `apps/web/src/features/auth/lib/routePermissions.ts`

- [ ] **Verificar a estrutura atual do Sidebar**

```bash
grep -n "Configurações\|profiles\|users\|group\|section" apps/web/src/shared/components/layout/Sidebar.tsx | head -30
```

- [ ] **Adicionar item de rota no `routePermissions.ts`**

Abrir `apps/web/src/features/auth/lib/routePermissions.ts` e adicionar o mapeamento:

```typescript
"/administracao/auditoria": "audit.view",
```

- [ ] **Adicionar grupo "Administração" no Sidebar**

Localizar onde o grupo de "Configurações" termina no Sidebar e adicionar após ele um novo grupo visível somente quando `can("audit.view")`. O grupo deve seguir exatamente o mesmo padrão dos outros grupos existentes (collapsible ou fixo — conforme o padrão do arquivo).

Adicionar o item:

```typescript
// Dentro do grupo "Administração" — visível só para admin
{
  href: "/administracao/auditoria",
  label: "Auditoria",
  icon: "policy",
  perm: "audit.view",
}
```

O grupo "Administração" usa ícone `admin_panel_settings` no cabeçalho do grupo.

- [ ] **Verificar typecheck**

```bash
cd apps/web
npx tsc --noEmit
```

Esperado: sem erros

- [ ] **Rodar linting completo**

```bash
cd apps/web
npm run lint
```

Esperado: sem erros

- [ ] **Commit**

```bash
git add apps/web/src/shared/components/layout/Sidebar.tsx \
        apps/web/src/features/auth/lib/routePermissions.ts
git commit -m "feat(audit): Sidebar grupo Administração + rota de auditoria"
```

---

## Checklist de verificação final

- [ ] `uv run alembic upgrade heads` — sem erros
- [ ] `uv run pytest tests/unit -v` — todos passando
- [ ] `uv run mypy src` — sem erros
- [ ] `uv run ruff check src tests` — sem warnings
- [ ] `npx tsc --noEmit` — sem erros
- [ ] Login no painel → aparece em `/administracao/auditoria`
- [ ] Criar/editar/excluir um produto → aparece com label correto
- [ ] Geo aparece após alguns segundos (BackgroundTask)
- [ ] Usuário com role=operator NÃO vê o menu "Administração"
- [ ] Filtro por ação funciona
- [ ] Paginação funciona
