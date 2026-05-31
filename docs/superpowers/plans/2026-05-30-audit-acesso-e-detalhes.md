# Audit: Histórico de Acesso + Drawer de Detalhes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separar login/logout em uma página "Histórico de Acesso" com colunas Navegador/SO/Dispositivo; adicionar drawer "Ver Detalhes" na página de Auditoria existente; excluir eventos auth da tabela de auditoria de ações.

**Architecture:** Backend recebe filtros `resource_type` (include) e `exclude_auth` (boolean) no endpoint existente, e passa a expor `metadata` e `user_email` na resposta. O header `User-Agent` é gravado em `metadata_json` nos eventos de login/logout. Frontend parseia UA client-side (sem lib) para exibir Browser/OS/Device. O drawer de detalhes exibe metadados como JSON formatado.

**Tech Stack:** Python/FastAPI, SQLAlchemy async, Next.js 15 App Router, TypeScript, Tailwind + design system NexoIA, Material Symbols.

---

## File Map

**Backend — modificar:**
- `apps/api/src/shared/domain/ports/audit_repository.py` — adicionar `resource_type` e `exclude_auth` ao Protocol
- `apps/api/src/shared/adapters/db/repositories/audit_repo.py` — implementar filtros
- `apps/api/src/shared/application/use_cases/admin/list_audit_events.py` — adicionar campos ao input
- `apps/api/src/interface/http/routers/admin/audit.py` — novos query params + expor `metadata` + `user_email`
- `apps/api/src/interface/http/routers/admin/auth.py` — capturar `User-Agent` em `_save_auth_audit`

**Frontend — criar:**
- `apps/web/src/features/audit/lib/parseUserAgent.ts`
- `apps/web/src/features/audit/components/AuditDetailDrawer.tsx`
- `apps/web/src/features/audit/components/AccessTable.tsx`
- `apps/web/src/app/(admin)/administracao/acesso/page.tsx`

**Frontend — modificar:**
- `apps/web/src/features/audit/types.ts` — adicionar `metadata`, `user_email`
- `apps/web/src/lib/api.ts` — adicionar `resource_type`, `exclude_auth` a `listAuditEvents`
- `apps/web/src/app/(admin)/administracao/auditoria/page.tsx` — excluir auth, adicionar botão Ver Detalhes
- `apps/web/src/shared/components/layout/Sidebar.tsx` — adicionar "Histórico de Acesso"
- `apps/web/src/features/auth/lib/routePermissions.ts` — mapear rota acesso

---

### Task 1: Backend — filtros resource_type + exclude_auth + expor metadata e user_agent

**Files:**
- Modify: `apps/api/src/shared/domain/ports/audit_repository.py`
- Modify: `apps/api/src/shared/adapters/db/repositories/audit_repo.py`
- Modify: `apps/api/src/shared/application/use_cases/admin/list_audit_events.py`
- Modify: `apps/api/src/interface/http/routers/admin/audit.py`
- Modify: `apps/api/src/interface/http/routers/admin/auth.py`

- [ ] **Atualizar `apps/api/src/shared/domain/ports/audit_repository.py`**

Substituir o método `paginate` no Protocol para incluir `resource_type` e `exclude_auth`:

```python
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
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        exclude_auth: bool = False,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[AuditEvent], int]: ...
```

- [ ] **Atualizar `apps/api/src/shared/adapters/db/repositories/audit_repo.py`**

Localizar o método `paginate` e adicionar os dois filtros novos após o filtro de `actor != "system"`:

```python
    async def paginate(
        self,
        account_id: UUID,
        *,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        exclude_auth: bool = False,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[AuditEvent], int]:
        base = (
            select(AuditEventModel)
            .where(AuditEventModel.account_id == account_id)
            .where(AuditEventModel.actor != "system")
        )
        if resource_type is not None:
            base = base.where(AuditEventModel.resource_type == resource_type)
        if exclude_auth:
            base = base.where(AuditEventModel.resource_type != "auth")
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

- [ ] **Atualizar `apps/api/src/shared/application/use_cases/admin/list_audit_events.py`**

Substituir o conteúdo completo:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared.domain.entities.audit_event import AuditEvent
from shared.domain.ports.audit_repository import AuditRepository


@dataclass
class ListAuditEventsInput:
    account_id: UUID
    user_id: str | None = None
    action: str | None = None
    resource_type: str | None = None
    exclude_auth: bool = False
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
            resource_type=inp.resource_type,
            exclude_auth=inp.exclude_auth,
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

- [ ] **Atualizar `apps/api/src/interface/http/routers/admin/audit.py`**

Substituir o conteúdo completo — adiciona `resource_type`, `exclude_auth`, expõe `metadata` e `user_email`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
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
    user_email: str | None
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    geo_city: str | None
    geo_country: str | None
    geo_region: str | None
    metadata: dict[str, Any]
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
        user_email=e.actor or None,
        action=e.action,
        resource_type=e.resource_type,
        resource_id=e.resource_id,
        ip_address=e.ip_address,
        geo_city=e.geo_city,
        geo_country=e.geo_country,
        geo_region=e.geo_region,
        metadata=e.metadata,
        created_at=e.created_at,
    )


@router.get("/audit-events", response_model=AuditEventListResponse)
async def list_audit_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    user_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    exclude_auth: bool = Query(default=False),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    auth: AdminAuth = Depends(require_permission("audit.view")),
) -> AuditEventListResponse:
    if auth.account_id is None:
        raise HTTPException(status_code=400, detail="account_id ausente no token")
    async with session_scope() as session:
        repo = SqlAuditRepository(session=session)
        use_case = ListAuditEventsUseCase(repo=repo)
        result = await use_case.execute(
            ListAuditEventsInput(
                account_id=auth.account_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                exclude_auth=exclude_auth,
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

- [ ] **Capturar `User-Agent` em `_save_auth_audit` em `apps/api/src/interface/http/routers/admin/auth.py`**

Modificar a assinatura de `_save_auth_audit` para aceitar `user_agent`:

```python
async def _save_auth_audit(
    *, account_id: str, user_id: str, user_email: str, ip: str, action: str = "Login",
    user_agent: str = "",
) -> None:
```

E na construção do `AuditEvent`, substituir `metadata={}` por `metadata={"user_agent": user_agent}` — ou seja, passar para o `AuditEvent`:

```python
        event = AuditEvent(
            id=event_id,
            account_id=_account_id,
            actor=user_email,
            user_id=user_id or None,
            user_name=user_email,
            action=action,
            resource_type="auth",
            resource_id=None,
            ip_address=ip or None,
            geo_city=None,
            geo_country=None,
            geo_region=None,
            metadata={"user_agent": user_agent} if user_agent else {},
        )
```

Modificar as duas chamadas de `_save_auth_audit` para passar o header:

Em `login`:
```python
    _login_task = asyncio.create_task(_save_auth_audit(
        account_id=str(snapshot["account_id"]),
        user_id=str(snapshot["id"]),
        user_email=snapshot["email"],
        ip=_extract_login_ip(request),
        action="Login",
        user_agent=request.headers.get("user-agent", ""),
    ))
    del _login_task
```

Em `logout`:
```python
            _logout_task = asyncio.create_task(_save_auth_audit(
                account_id=str(payload.get("account_id", "")),
                user_id=str(payload.get("user_id", "")),
                user_email=payload.get("sub", ""),
                ip=_extract_login_ip(request),
                action="Logout",
                user_agent=request.headers.get("user-agent", ""),
            ))
            del _logout_task
```

- [ ] **Rodar testes**

```bash
cd /home/fabio/www/agente-plug/apps/api && uv run pytest tests/unit -q --tb=short 2>&1 | tail -5
```
Esperado: `617 passed` (ou mais)

- [ ] **Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/api/src/shared/domain/ports/audit_repository.py apps/api/src/shared/adapters/db/repositories/audit_repo.py apps/api/src/shared/application/use_cases/admin/list_audit_events.py apps/api/src/interface/http/routers/admin/audit.py apps/api/src/interface/http/routers/admin/auth.py && git commit -m "feat(audit): resource_type filter + exclude_auth + user_agent capture + expose metadata"
```

---

### Task 2: Frontend — tipos e função de API atualizados

**Files:**
- Modify: `apps/web/src/features/audit/types.ts`
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Substituir `apps/web/src/features/audit/types.ts`**

```typescript
export interface AuditEventItem {
  id: string;
  user_name: string | null;
  user_email: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string | null;
  geo_city: string | null;
  geo_country: string | null;
  geo_region: string | null;
  metadata: Record<string, unknown>;
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
  resource_type?: string;
  exclude_auth?: boolean;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}
```

- [ ] **Atualizar `listAuditEvents` em `apps/web/src/lib/api.ts`**

Substituir a função existente:

```typescript
export async function listAuditEvents(params: {
  page?: number;
  page_size?: number;
  user_id?: string;
  action?: string;
  resource_type?: string;
  exclude_auth?: boolean;
  date_from?: string;
  date_to?: string;
} = {}): Promise<import("@/features/audit/types").AuditEventListResponse> {
  const qs = new URLSearchParams();
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  if (params.user_id) qs.set("user_id", params.user_id);
  if (params.action) qs.set("action", params.action);
  if (params.resource_type) qs.set("resource_type", params.resource_type);
  if (params.exclude_auth) qs.set("exclude_auth", "true");
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  return apiFetch(`/admin/audit-events?${qs.toString()}`);
}
```

- [ ] **Verificar typecheck**

```bash
cd /home/fabio/www/agente-plug/apps/web && npx tsc --noEmit 2>&1 | tail -5
```
Esperado: sem erros

- [ ] **Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/web/src/features/audit/types.ts apps/web/src/lib/api.ts && git commit -m "feat(audit): update types + API function with resource_type/exclude_auth/metadata/user_email"
```

---

### Task 3: `parseUserAgent` util

**Files:**
- Create: `apps/web/src/features/audit/lib/parseUserAgent.ts`

- [ ] **Criar `apps/web/src/features/audit/lib/parseUserAgent.ts`**

```typescript
export interface ParsedUA {
  browser: string;
  os: string;
  device: "desktop" | "mobile" | "tablet";
}

export function parseUserAgent(ua: string | null | undefined): ParsedUA {
  if (!ua) return { browser: "—", os: "—", device: "desktop" };

  const browser =
    /Edg\//.test(ua) ? "Edge" :
    /OPR\/|Opera/.test(ua) ? "Opera" :
    /Chrome\//.test(ua) ? "Chrome" :
    /Firefox\//.test(ua) ? "Firefox" :
    /Safari\//.test(ua) ? "Safari" :
    "—";

  const os =
    /Windows NT/.test(ua) ? "Windows" :
    /Mac OS X/.test(ua) && !/iPhone|iPad/.test(ua) ? "macOS" :
    /Android/.test(ua) ? "Android" :
    /iPhone/.test(ua) ? "iOS" :
    /iPad/.test(ua) ? "iPadOS" :
    /Linux/.test(ua) ? "Linux" :
    "—";

  const device: ParsedUA["device"] =
    /iPad/.test(ua) ? "tablet" :
    /Mobile|Android|iPhone/.test(ua) ? "mobile" :
    "desktop";

  return { browser, os, device };
}
```

- [ ] **Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/web/src/features/audit/lib/parseUserAgent.ts && git commit -m "feat(audit): parseUserAgent client-side utility"
```

---

### Task 4: `AuditDetailDrawer` — drawer de detalhes da ação

**Files:**
- Create: `apps/web/src/features/audit/components/AuditDetailDrawer.tsx`

- [ ] **Criar `apps/web/src/features/audit/components/AuditDetailDrawer.tsx`**

```tsx
"use client";

import { useEffect, useRef } from "react";
import type { AuditEventItem } from "@/features/audit/types";

const RESOURCE_LABELS: Record<string, string> = {
  auth: "Autenticação",
  user: "Usuário",
  product: "Produto",
  flow: "Flow de Onboarding",
  flow_step: "Step de Flow",
  document: "Documento KB",
  meta_template: "Template Meta",
  settings: "Configurações",
  api_token: "Token de API",
  profile: "Perfil",
  dlq: "Dead-Letter Queue",
};

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).format(new Date(iso));
}

interface Props {
  item: AuditEventItem | null;
  onClose: () => void;
}

export function AuditDetailDrawer({ item, onClose }: Props) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!item) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [item, onClose]);

  if (!item) return null;

  const hasMetadata = item.metadata && Object.keys(item.metadata).length > 0;
  const metaWithoutUA = item.metadata
    ? Object.fromEntries(Object.entries(item.metadata).filter(([k]) => k !== "user_agent"))
    : {};
  const hasActionMetadata = Object.keys(metaWithoutUA).length > 0;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div className="relative mx-4 w-full max-w-xl overflow-hidden rounded-2xl border border-outline-variant bg-white shadow-2xl dark:bg-surface-container">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-outline-variant px-6 py-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
              Detalhes do Evento
            </p>
            <p className="mt-0.5 font-mono text-xs text-on-surface-variant/60">{item.id}</p>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-container-high"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>close</span>
          </button>
        </div>

        {/* Body */}
        <div className="space-y-5 px-6 py-5">
          {/* Ação + Tipo */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Ação</p>
              <span className="mt-1.5 inline-flex items-center rounded-full bg-primary-container px-3 py-1 text-xs font-medium text-on-primary-container">
                {item.action}
              </span>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Entidade</p>
              <p className="mt-1.5 text-sm text-on-surface">
                {RESOURCE_LABELS[item.resource_type] ?? item.resource_type}
              </p>
            </div>
          </div>

          {/* ID da entidade */}
          {item.resource_id && item.resource_id !== "auth" && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">ID da Entidade</p>
              <p className="mt-1.5 font-mono text-xs text-on-surface">{item.resource_id}</p>
            </div>
          )}

          {/* Usuário */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Usuário</p>
            <div className="mt-1.5 flex items-center gap-2">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary-container text-xs font-semibold text-on-secondary-container">
                {item.user_name ? item.user_name.charAt(0).toUpperCase() : "?"}
              </div>
              <div>
                <p className="text-sm font-medium text-on-surface">{item.user_name ?? "—"}</p>
                {item.user_email && item.user_email !== item.user_name && (
                  <p className="text-xs text-on-surface-variant">{item.user_email}</p>
                )}
              </div>
            </div>
          </div>

          {/* Data/Hora + IP/Geo */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Data e Hora</p>
              <p className="mt-1.5 text-sm text-on-surface">{formatDate(item.created_at)}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Origem</p>
              <p className="mt-1.5 font-mono text-xs text-on-surface">{item.ip_address ?? "—"}</p>
              {item.geo_city && (
                <p className="text-xs text-on-surface-variant">
                  {item.geo_city}, {item.geo_country}
                </p>
              )}
            </div>
          </div>

          {/* Metadados JSON */}
          {hasActionMetadata && (
            <div>
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
                  Metadados
                </p>
                <button
                  onClick={() => navigator.clipboard.writeText(JSON.stringify(metaWithoutUA, null, 2))}
                  className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-on-surface-variant transition-colors hover:bg-surface-container-high"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>content_copy</span>
                  Copiar JSON
                </button>
              </div>
              <pre className="mt-2 max-h-48 overflow-auto rounded-xl bg-surface-container-high p-3 font-mono text-xs text-on-surface">
                {JSON.stringify(metaWithoutUA, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-outline-variant px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-xl border border-outline-variant px-4 py-2 text-sm text-on-surface-variant transition-colors hover:bg-surface-container-high"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Verificar typecheck**

```bash
cd /home/fabio/www/agente-plug/apps/web && npx tsc --noEmit 2>&1 | tail -5
```

- [ ] **Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/web/src/features/audit/components/AuditDetailDrawer.tsx && git commit -m "feat(audit): AuditDetailDrawer com metadados JSON e info completa"
```

---

### Task 5: Atualizar página de Auditoria de Ações

**Files:**
- Modify: `apps/web/src/app/(admin)/administracao/auditoria/page.tsx`

- [ ] **Substituir o conteúdo completo de `apps/web/src/app/(admin)/administracao/auditoria/page.tsx`**

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { listAuditEvents } from "@/lib/api";
import { RequirePermission } from "@/features/auth/components/RequirePermission";
import { AuditTable } from "@/features/audit/components/AuditTable";
import { AuditDetailDrawer } from "@/features/audit/components/AuditDetailDrawer";
import type { AuditEventItem, AuditFilters } from "@/features/audit/types";

const ACTION_OPTIONS = [
  "Criou usuário", "Editou usuário", "Excluiu usuário",
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
  const [selectedItem, setSelectedItem] = useState<AuditEventItem | null>(null);

  const load = useCallback(async (f: AuditFilters, p: number) => {
    setIsLoading(true);
    try {
      const res = await listAuditEvents({ ...f, page: p, exclude_auth: true });
      setItems(res.items);
      setTotal(res.total);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { load(filters, page); }, [filters, page, load]);

  const totalPages = Math.ceil(total / (filters.page_size ?? 25));
  const hasActiveFilters = !!(filters.action || filters.date_from || filters.date_to);

  return (
    <RequirePermission perm="audit.view">
      <div className="space-y-6 p-6">
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
            <div className="flex-1">
              <p className="text-xs font-medium text-on-surface-variant">Administração</p>
              <h1 className="mt-0.5 text-2xl font-bold text-on-surface">Auditoria de Ações</h1>
              <p className="mt-1 text-sm text-on-surface-variant">
                Criações, edições e exclusões realizadas no painel.
              </p>
            </div>
            {total > 0 && (
              <div className="shrink-0 rounded-xl bg-surface-container-high px-4 py-2 text-center">
                <div className="text-2xl font-bold text-on-surface">{total.toLocaleString("pt-BR")}</div>
                <div className="text-xs text-on-surface-variant">eventos</div>
              </div>
            )}
          </div>
        </header>

        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Ação</label>
            <select
              className="min-w-[180px] rounded-xl border border-outline-variant bg-white dark:bg-surface-container px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              value={filters.action ?? ""}
              onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, action: e.target.value || undefined })); }}
            >
              <option value="">Todas as ações</option>
              {ACTION_OPTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">De</label>
            <input type="datetime-local" className="rounded-xl border border-outline-variant bg-white dark:bg-surface-container px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" value={filters.date_from ?? ""} onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, date_from: e.target.value || undefined })); }} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Até</label>
            <input type="datetime-local" className="rounded-xl border border-outline-variant bg-white dark:bg-surface-container px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary" value={filters.date_to ?? ""} onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, date_to: e.target.value || undefined })); }} />
          </div>
          {hasActiveFilters && (
            <button onClick={() => { setPage(1); setFilters({ page_size: 25 }); }} className="flex items-center gap-1.5 rounded-xl border border-outline-variant px-3 py-2 text-sm text-on-surface-variant transition-colors hover:bg-surface-container-high">
              <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>close</span>
              Limpar
            </button>
          )}
        </div>

        <AuditTable items={items} isLoading={isLoading} onDetails={setSelectedItem} />

        {!isLoading && totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-on-surface-variant">
              <span className="font-medium text-on-surface">{total.toLocaleString("pt-BR")}</span> registros
            </p>
            <div className="flex items-center gap-2">
              <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="flex h-9 w-9 items-center justify-center rounded-xl border border-outline-variant text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:opacity-40">
                <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>chevron_left</span>
              </button>
              <span className="min-w-[80px] text-center text-sm text-on-surface">{page} / {totalPages}</span>
              <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="flex h-9 w-9 items-center justify-center rounded-xl border border-outline-variant text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:opacity-40">
                <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>chevron_right</span>
              </button>
            </div>
          </div>
        )}
      </div>
      <AuditDetailDrawer item={selectedItem} onClose={() => setSelectedItem(null)} />
    </RequirePermission>
  );
}
```

- [ ] **Atualizar `AuditTable` para aceitar e exibir o botão "Ver Detalhes"**

Em `apps/web/src/features/audit/components/AuditTable.tsx`, modificar a interface `Props` e adicionar a coluna:

```tsx
interface Props {
  items: AuditEventItem[];
  isLoading: boolean;
  onDetails?: (item: AuditEventItem) => void;
}
```

No `thead`, adicionar última coluna `<th className="px-4 py-3"></th>` (vazia, para o botão).

No `tbody`, na última célula de cada `<tr>`, adicionar:

```tsx
<td className="px-4 py-3 text-right">
  {onDetails && (
    <button
      onClick={() => onDetails(item)}
      className="rounded-lg px-2 py-1 text-xs text-primary transition-colors hover:bg-primary-container/30"
    >
      Ver Detalhes
    </button>
  )}
</td>
```

Também nos dois estados (skeleton e loading) adicionar `<th>` / `<td>` extras para manter o alinhamento de colunas (5 colunas no total).

- [ ] **Verificar typecheck**

```bash
cd /home/fabio/www/agente-plug/apps/web && npx tsc --noEmit 2>&1 | tail -5
```

- [ ] **Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/web/src/app/\(admin\)/administracao/auditoria/page.tsx apps/web/src/features/audit/components/AuditTable.tsx && git commit -m "feat(audit): exclude_auth + Ver Detalhes button + AuditDetailDrawer na página de ações"
```

---

### Task 6: `AccessTable` + página Histórico de Acesso

**Files:**
- Create: `apps/web/src/features/audit/components/AccessTable.tsx`
- Create: `apps/web/src/app/(admin)/administracao/acesso/page.tsx`

- [ ] **Criar `apps/web/src/features/audit/components/AccessTable.tsx`**

```tsx
"use client";

import type { AuditEventItem } from "@/features/audit/types";
import { parseUserAgent } from "@/features/audit/lib/parseUserAgent";

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  }).format(new Date(iso));
}

const DEVICE_ICONS: Record<string, string> = {
  desktop: "computer",
  mobile: "smartphone",
  tablet: "tablet",
};

interface Props {
  items: AuditEventItem[];
  isLoading: boolean;
}

export function AccessTable({ items, isLoading }: Props) {
  if (isLoading) {
    return (
      <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-outline-variant bg-surface-container-low">
              {["Data/Hora", "Evento", "Usuário", "IP", "Localização", "Navegador", "SO", "Dispositivo"].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...Array(5)].map((_, i) => (
              <tr key={i} className="border-b border-outline-variant last:border-0">
                {[...Array(8)].map((_, j) => (
                  <td key={j} className="px-4 py-3">
                    <div className="h-3.5 w-16 animate-pulse rounded-full bg-surface-container-high" />
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
          <span className="material-symbols-outlined" style={{ fontSize: "40px", fontVariationSettings: "'FILL' 0, 'wght' 300" }}>login</span>
          <p className="text-sm font-medium">Nenhum acesso registrado</p>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-outline-variant bg-surface-container-low">
            {["Data/Hora", "Evento", "Usuário", "IP", "Localização", "Navegador", "SO", "Dispositivo"].map((h) => (
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const ua = parseUserAgent(item.metadata?.user_agent as string | null);
            const isLogin = item.action === "Login";
            return (
              <tr key={item.id} className="border-b border-outline-variant last:border-0 transition-colors hover:bg-surface-container-low/50">
                <td className="whitespace-nowrap px-4 py-3 text-xs tabular-nums text-on-surface-variant">
                  {formatDate(item.created_at)}
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${
                    isLogin
                      ? "bg-[#d1fae5] text-[#064e3b] dark:bg-[#064e3b] dark:text-[#d1fae5]"
                      : "bg-surface-container-high text-on-surface-variant"
                  }`}>
                    <span className="material-symbols-outlined" style={{ fontSize: "12px" }}>
                      {isLogin ? "login" : "logout"}
                    </span>
                    {item.action}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary-container text-xs font-semibold text-on-secondary-container">
                      {item.user_name ? item.user_name.charAt(0).toUpperCase() : "?"}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-on-surface max-w-[120px]">
                        {item.user_name ?? "—"}
                      </p>
                      {item.user_email && item.user_email !== item.user_name && (
                        <p className="truncate text-xs text-on-surface-variant max-w-[120px]">
                          {item.user_email}
                        </p>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-on-surface-variant whitespace-nowrap">
                  {item.ip_address ?? "—"}
                </td>
                <td className="px-4 py-3 text-xs text-on-surface-variant whitespace-nowrap">
                  {item.geo_city ? `${item.geo_city}, ${item.geo_region} - ${item.geo_country}` : "—"}
                </td>
                <td className="px-4 py-3 text-xs text-on-surface whitespace-nowrap">{ua.browser}</td>
                <td className="px-4 py-3 text-xs text-on-surface whitespace-nowrap">{ua.os}</td>
                <td className="px-4 py-3 text-xs text-on-surface-variant whitespace-nowrap">
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
                      {DEVICE_ICONS[ua.device]}
                    </span>
                    {ua.device}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Criar `apps/web/src/app/(admin)/administracao/acesso/page.tsx`**

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { listAuditEvents } from "@/lib/api";
import { RequirePermission } from "@/features/auth/components/RequirePermission";
import { AccessTable } from "@/features/audit/components/AccessTable";
import type { AuditEventItem } from "@/features/audit/types";

export default function AcessoPage() {
  const [items, setItems] = useState<AuditEventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const PAGE_SIZE = 25;

  const load = useCallback(async (p: number) => {
    setIsLoading(true);
    try {
      const res = await listAuditEvents({ resource_type: "auth", page: p, page_size: PAGE_SIZE });
      setItems(res.items);
      setTotal(res.total);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { load(page); }, [page, load]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <RequirePermission perm="audit.view">
      <div className="space-y-6 p-6">
        <header className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
          <div className="flex items-center gap-5 px-7 py-6">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary-container">
              <span
                className="material-symbols-outlined text-on-primary-container"
                style={{ fontSize: "28px", fontVariationSettings: "'FILL' 1" }}
              >
                manage_accounts
              </span>
            </div>
            <div className="flex-1">
              <p className="text-xs font-medium text-on-surface-variant">Administração</p>
              <h1 className="mt-0.5 text-2xl font-bold text-on-surface">Histórico de Acesso</h1>
              <p className="mt-1 text-sm text-on-surface-variant">
                Registros de login e logout com IP, localização e dispositivo.
              </p>
            </div>
            {total > 0 && (
              <div className="shrink-0 rounded-xl bg-surface-container-high px-4 py-2 text-center">
                <div className="text-2xl font-bold text-on-surface">{total.toLocaleString("pt-BR")}</div>
                <div className="text-xs text-on-surface-variant">acessos</div>
              </div>
            )}
          </div>
        </header>

        <AccessTable items={items} isLoading={isLoading} />

        {!isLoading && totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-on-surface-variant">
              <span className="font-medium text-on-surface">{total.toLocaleString("pt-BR")}</span> registros
            </p>
            <div className="flex items-center gap-2">
              <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="flex h-9 w-9 items-center justify-center rounded-xl border border-outline-variant text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:opacity-40">
                <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>chevron_left</span>
              </button>
              <span className="min-w-[80px] text-center text-sm text-on-surface">{page} / {totalPages}</span>
              <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="flex h-9 w-9 items-center justify-center rounded-xl border border-outline-variant text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:opacity-40">
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
cd /home/fabio/www/agente-plug/apps/web && npx tsc --noEmit 2>&1 | tail -5
```

- [ ] **Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/web/src/features/audit/components/AccessTable.tsx apps/web/src/app/\(admin\)/administracao/acesso/ && git commit -m "feat(audit): AccessTable + página Histórico de Acesso"
```

---

### Task 7: Sidebar + routePermissions

**Files:**
- Modify: `apps/web/src/shared/components/layout/Sidebar.tsx`
- Modify: `apps/web/src/features/auth/lib/routePermissions.ts`

- [ ] **Adicionar "Histórico de Acesso" em `ADMIN_CHILDREN` no Sidebar**

Localizar a constante `ADMIN_CHILDREN` e substituir por:

```typescript
const ADMIN_CHILDREN: NavEntry[] = [
  { label: "Auditoria", href: "/administracao/auditoria", icon: "policy", perm: "audit.view" },
  { label: "Histórico de Acesso", href: "/administracao/acesso", icon: "manage_accounts", perm: "audit.view" },
];
```

- [ ] **Adicionar rota em `routePermissions.ts`**

Adicionar a linha:

```typescript
"/administracao/acesso": "audit.view",
```

- [ ] **Verificar typecheck e linting**

```bash
cd /home/fabio/www/agente-plug/apps/web && npx tsc --noEmit 2>&1 | tail -5
```

```bash
cd /home/fabio/www/agente-plug/apps/web && npm run lint 2>&1 | tail -5
```

- [ ] **Commit**

```bash
cd /home/fabio/www/agente-plug && git add apps/web/src/shared/components/layout/Sidebar.tsx apps/web/src/features/auth/lib/routePermissions.ts && git commit -m "feat(audit): Sidebar adiciona Histórico de Acesso"
```

---

## Checklist de verificação final

- [ ] `uv run pytest tests/unit -q` — todos passando
- [ ] `uv run ruff check src tests` — limpo
- [ ] `npx tsc --noEmit` — sem erros
- [ ] Fazer logout + login → aparece em Histórico de Acesso com Cidade/Estado, Navegador, SO, Dispositivo
- [ ] IP mostra versão completa; localização no formato "Cidade, Estado - País"
- [ ] Auditoria de Ações não mostra Login/Logout (exclude_auth=true)
- [ ] Botão "Ver Detalhes" abre drawer com metadados, usuário e IP
- [ ] Drawer fecha com ESC e clique fora
- [ ] Sidebar mostra "Auditoria" e "Histórico de Acesso" sob "Administração"
- [ ] Operadores não veem o grupo "Administração"
