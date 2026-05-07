# Meta Template Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a gestão de templates WhatsApp Business diretamente no painel NexoIA: listar templates aprovados da Meta API e criar novos templates com preview ao vivo.

**Architecture:** Port `MetaTemplatePort` em domain, adapter `MetaTemplateClient` em adapters, admin router, feature module `templates` no frontend. Credenciais `META_API_KEY` e `META_WABA_ID` lidas do `AccountConfig`.

**Tech Stack:** Python 3.12, FastAPI, httpx (async HTTP), Next.js 15, TypeScript, Tailwind NexoIA

---

## File Map

### Criar
```
apps/api/src/shared/domain/ports/meta_template.py
apps/api/src/shared/adapters/meta/__init__.py
apps/api/src/shared/adapters/meta/template_client.py
apps/api/src/interface/http/routers/admin/meta_templates.py
apps/api/src/interface/http/schemas/meta_templates.py
apps/api/tests/unit/interface/admin/test_meta_templates_router.py

apps/web/src/features/templates/types.ts
apps/web/src/features/templates/hooks/useMetaTemplates.ts
apps/web/src/features/templates/components/TemplateStatusBadge.tsx
apps/web/src/features/templates/components/TemplateList.tsx
apps/web/src/features/templates/components/TemplatePreview.tsx
apps/web/src/features/templates/components/TemplateForm.tsx
apps/web/src/app/(admin)/templates/page.tsx
apps/web/src/app/(admin)/templates/new/page.tsx
```

### Modificar
```
apps/api/src/shared/config/settings.py                + META_WABA_ID
apps/api/src/shared/domain/entities/account_config.py + meta_waba_id field
apps/api/src/main.py                                  + router meta_templates
apps/web/src/lib/api.ts                               + funções de templates
apps/web/src/shared/components/layout/Sidebar.tsx     + item "Templates"
```

---

### Task 1: Domain port e settings

**Files:**
- Create: `apps/api/src/shared/domain/ports/meta_template.py`
- Modify: `apps/api/src/shared/config/settings.py`

- [ ] **Step 1: Criar port**

```python
# apps/api/src/shared/domain/ports/meta_template.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class MetaTemplateComponent:
    type: str          # HEADER | BODY | FOOTER | BUTTONS
    format: str | None = None   # TEXT | IMAGE | VIDEO | DOCUMENT (para HEADER)
    text: str | None = None
    buttons: list[dict[str, Any]] | None = None
    example: dict[str, Any] | None = None


@dataclass
class MetaTemplate:
    id: str
    name: str
    category: str       # MARKETING | UTILITY | AUTHENTICATION
    language: str       # pt_BR | en_US
    status: str         # APPROVED | PENDING | REJECTED
    components: list[MetaTemplateComponent]
    rejection_reason: str | None = None


@dataclass
class CreateTemplatePayload:
    name: str
    category: str
    language: str
    components: list[dict[str, Any]]


class MetaTemplatePort(Protocol):
    async def list_templates(self, waba_id: str) -> list[MetaTemplate]: ...
    async def create_template(
        self, waba_id: str, payload: CreateTemplatePayload
    ) -> MetaTemplate: ...
```

- [ ] **Step 2: Adicionar `META_WABA_ID` em settings**

Em `apps/api/src/shared/config/settings.py`, adicionar junto com `meta_api_key`:

```python
    meta_waba_id: str = ""
```

- [ ] **Step 3: Verificar importação**

```bash
cd apps/api && uv run python -c "from shared.domain.ports.meta_template import MetaTemplate, MetaTemplatePort; print('OK')"
```
Esperado: `OK`

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared/domain/ports/meta_template.py \
        apps/api/src/shared/config/settings.py
git commit -m "feat(meta-templates): domain port e settings META_WABA_ID"
```

---

### Task 2: MetaTemplateClient adapter

**Files:**
- Create: `apps/api/src/shared/adapters/meta/__init__.py`
- Create: `apps/api/src/shared/adapters/meta/template_client.py`

- [ ] **Step 1: Criar `__init__.py`**

```bash
touch apps/api/src/shared/adapters/meta/__init__.py
```

- [ ] **Step 2: Criar `template_client.py`**

```python
# apps/api/src/shared/adapters/meta/template_client.py
from __future__ import annotations

from typing import Any

import httpx
import structlog

from shared.domain.ports.meta_template import (
    CreateTemplatePayload,
    MetaTemplate,
    MetaTemplateComponent,
)

log = structlog.get_logger(__name__)

_BASE_URL = "https://graph.facebook.com/v19.0"


def _parse_component(raw: dict[str, Any]) -> MetaTemplateComponent:
    return MetaTemplateComponent(
        type=raw.get("type", ""),
        format=raw.get("format"),
        text=raw.get("text"),
        buttons=raw.get("buttons"),
        example=raw.get("example"),
    )


def _parse_template(raw: dict[str, Any]) -> MetaTemplate:
    components = [_parse_component(c) for c in raw.get("components", [])]
    return MetaTemplate(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        category=raw.get("category", ""),
        language=raw.get("language", ""),
        status=raw.get("status", "PENDING"),
        components=components,
        rejection_reason=raw.get("rejected_reason"),
    )


class MetaTemplateClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @classmethod
    def from_account_config(cls, config: Any) -> "MetaTemplateClient":
        return cls(api_key=config.integration.meta_api_key)

    @classmethod
    def from_settings(cls, settings: Any) -> "MetaTemplateClient":
        return cls(api_key=settings.meta_api_key)

    async def list_templates(self, waba_id: str) -> list[MetaTemplate]:
        url = f"{_BASE_URL}/{waba_id}/message_templates"
        params = {"fields": "id,name,category,language,status,components,rejected_reason"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=15,
            )
        if resp.status_code != 200:
            log.warning(
                "meta_list_templates_error",
                status=resp.status_code,
                body=resp.text[:200],
            )
            resp.raise_for_status()
        data = resp.json()
        return [_parse_template(t) for t in data.get("data", [])]

    async def create_template(
        self, waba_id: str, payload: CreateTemplatePayload
    ) -> MetaTemplate:
        url = f"{_BASE_URL}/{waba_id}/message_templates"
        body = {
            "name": payload.name,
            "category": payload.category,
            "language": payload.language,
            "components": payload.components,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
        if resp.status_code not in (200, 201):
            error_body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"message": resp.text}
            log.warning("meta_create_template_error", status=resp.status_code, body=error_body)
            resp.raise_for_status()
        raw = resp.json()
        # A Meta retorna apenas id, name, status na criação — reconstruir com dados do payload
        return MetaTemplate(
            id=raw.get("id", ""),
            name=payload.name,
            category=payload.category,
            language=payload.language,
            status=raw.get("status", "PENDING"),
            components=[_parse_component(c) for c in payload.components],
        )
```

- [ ] **Step 3: Verificar importação**

```bash
cd apps/api && uv run python -c "from shared.adapters.meta.template_client import MetaTemplateClient; print('OK')"
```
Esperado: `OK`

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared/adapters/meta/
git commit -m "feat(meta-templates): MetaTemplateClient adapter"
```

---

### Task 3: Admin API — Schemas e Router

**Files:**
- Create: `apps/api/src/interface/http/schemas/meta_templates.py`
- Create: `apps/api/src/interface/http/routers/admin/meta_templates.py`

- [ ] **Step 1: Criar schemas**

```python
# apps/api/src/interface/http/schemas/meta_templates.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TemplateComponentResponse(BaseModel):
    type: str
    format: str | None = None
    text: str | None = None
    buttons: list[dict[str, Any]] | None = None


class MetaTemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    language: str
    status: str
    components: list[TemplateComponentResponse]
    rejection_reason: str | None = None


class CreateTemplateRequest(BaseModel):
    name: str
    category: str          # MARKETING | UTILITY | AUTHENTICATION
    language: str          # pt_BR | en_US
    components: list[dict[str, Any]]  # estrutura raw da Meta API
```

- [ ] **Step 2: Criar router**

```python
# apps/api/src/interface/http/routers/admin/meta_templates.py
from __future__ import annotations

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
from cryptography.fernet import Fernet

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
    """Returns (client, waba_id) from account config."""
    settings = get_settings()
    fernet = Fernet(settings.integration_credentials_key.encode())
    async with session_scope() as session:
        repo = AccountConfigRepository(session=session, fernet=fernet)
        config = await repo.get(account_id=auth.account_id)
    client = MetaTemplateClient.from_account_config(config)
    waba_id = settings.meta_waba_id
    return client, waba_id


@router.get("/meta-templates", response_model=list[MetaTemplateResponse])
async def list_templates(
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> list[MetaTemplateResponse]:
    client, waba_id = await _get_client(auth)
    if not waba_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="META_WABA_ID não configurado em Settings",
        )
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
```

- [ ] **Step 3: Escrever teste básico**

```python
# apps/api/tests/unit/interface/admin/test_meta_templates_router.py
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_app():
    from fastapi import FastAPI
    from interface.http.routers.admin.meta_templates import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    return app


def _mock_auth_override():
    from interface.http.deps.admin_auth import AdminAuth
    from uuid import UUID

    auth = AdminAuth(
        account_id=UUID("00000000-0000-0000-0000-000000000001"),
        user_email="a@b.com",
        user_role="admin",
    )

    def _override():
        return auth

    return _override


@pytest.fixture
def client():
    app = _make_app()
    from interface.http.deps.admin_auth import require_admin
    app.dependency_overrides[require_admin] = _mock_auth_override()
    return TestClient(app)


def test_list_templates_returns_502_on_meta_error(client):
    with patch(
        "interface.http.routers.admin.meta_templates._get_client",
        new_callable=AsyncMock,
    ) as mock_get:
        from shared.adapters.meta.template_client import MetaTemplateClient

        mock_client = AsyncMock(spec=MetaTemplateClient)
        mock_client.list_templates.side_effect = Exception("meta down")
        mock_get.return_value = (mock_client, "waba-123")

        resp = client.get("/admin/meta-templates")

    assert resp.status_code == 502
    assert "Meta" in resp.json()["detail"]
```

- [ ] **Step 4: Rodar teste**

```bash
cd apps/api && uv run pytest tests/unit/interface/admin/test_meta_templates_router.py -v
```
Esperado: `PASSED`

- [ ] **Step 5: Registrar router em `main.py`**

```python
# Em main.py, adicionar import:
from interface.http.routers.admin import meta_templates as admin_meta_templates

# Em create_app():
app.include_router(admin_meta_templates.router, prefix="/admin")
```

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/interface/http/schemas/meta_templates.py \
        apps/api/src/interface/http/routers/admin/meta_templates.py \
        apps/api/src/main.py \
        apps/api/tests/unit/interface/admin/test_meta_templates_router.py
git commit -m "feat(meta-templates): admin API de templates Meta"
```

---

### Task 4: Frontend — Tipos, API e hook

**Files:**
- Create: `apps/web/src/features/templates/types.ts`
- Modify: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/features/templates/hooks/useMetaTemplates.ts`

- [ ] **Step 1: Criar tipos**

```typescript
// apps/web/src/features/templates/types.ts
export interface TemplateComponent {
  type: "HEADER" | "BODY" | "FOOTER" | "BUTTONS";
  format?: "TEXT" | "IMAGE" | "VIDEO" | "DOCUMENT";
  text?: string;
  buttons?: TemplateButton[];
}

export interface TemplateButton {
  type: "QUICK_REPLY" | "URL" | "PHONE_NUMBER";
  text: string;
  url?: string;
  phone_number?: string;
}

export type TemplateStatus = "APPROVED" | "PENDING" | "REJECTED";

export interface MetaTemplate {
  id: string;
  name: string;
  category: "MARKETING" | "UTILITY" | "AUTHENTICATION";
  language: string;
  status: TemplateStatus;
  components: TemplateComponent[];
  rejection_reason?: string | null;
}

export interface CreateTemplateDto {
  name: string;
  category: "MARKETING" | "UTILITY" | "AUTHENTICATION";
  language: string;
  components: Record<string, unknown>[];
}
```

- [ ] **Step 2: Adicionar funções em `api.ts`**

```typescript
// Adicionar ao final de apps/web/src/lib/api.ts
import type { CreateTemplateDto, MetaTemplate } from "@/features/templates/types";

export async function listMetaTemplates(): Promise<MetaTemplate[]> {
  return apiFetch("/admin/meta-templates");
}

export async function createMetaTemplate(dto: CreateTemplateDto): Promise<MetaTemplate> {
  return apiFetch("/admin/meta-templates", {
    method: "POST",
    body: JSON.stringify(dto),
  });
}
```

- [ ] **Step 3: Criar hook**

```typescript
// apps/web/src/features/templates/hooks/useMetaTemplates.ts
"use client";

import { useCallback, useEffect, useState } from "react";
import { createMetaTemplate, listMetaTemplates } from "@/lib/api";
import type { CreateTemplateDto, MetaTemplate } from "../types";

export function useMetaTemplates() {
  const [templates, setTemplates] = useState<MetaTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listMetaTemplates();
      setTemplates(data);
    } catch {
      setError("Não foi possível carregar os templates. Verifique META_WABA_ID nas configurações.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const create = useCallback(async (dto: CreateTemplateDto): Promise<MetaTemplate> => {
    const template = await createMetaTemplate(dto);
    setTemplates((prev) => [...prev, template]);
    return template;
  }, []);

  return { templates, loading, error, reload: load, create };
}
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/templates/types.ts \
        apps/web/src/features/templates/hooks/ \
        apps/web/src/lib/api.ts
git commit -m "feat(meta-templates-ui): tipos, funções API e hook"
```

---

### Task 5: Componentes frontend

**Files:**
- Create: `apps/web/src/features/templates/components/TemplateStatusBadge.tsx`
- Create: `apps/web/src/features/templates/components/TemplatePreview.tsx`
- Create: `apps/web/src/features/templates/components/TemplateList.tsx`
- Create: `apps/web/src/features/templates/components/TemplateForm.tsx`

- [ ] **Step 1: Criar `TemplateStatusBadge.tsx`**

```tsx
// apps/web/src/features/templates/components/TemplateStatusBadge.tsx
import type { TemplateStatus } from "../types";

const STATUS_STYLES: Record<TemplateStatus, string> = {
  APPROVED: "bg-success/20 text-success",
  PENDING: "bg-warning/20 text-warning",
  REJECTED: "bg-error/20 text-error",
};

const STATUS_LABELS: Record<TemplateStatus, string> = {
  APPROVED: "Aprovado",
  PENDING: "Pendente",
  REJECTED: "Rejeitado",
};

export function TemplateStatusBadge({ status }: { status: TemplateStatus }) {
  return (
    <span
      className={`rounded-full px-2.5 py-0.5 text-label-sm font-medium ${STATUS_STYLES[status]}`}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}
```

- [ ] **Step 2: Criar `TemplatePreview.tsx`**

```tsx
// apps/web/src/features/templates/components/TemplatePreview.tsx
interface Props {
  body: string;
  header?: string;
  footer?: string;
}

export function TemplatePreview({ body, header, footer }: Props) {
  const highlighted = body.replace(/\{\{(\d+)\}\}/g, (_, n) => `[variável ${n}]`);

  return (
    <div className="rounded-2xl bg-[#075e54] p-3">
      <div className="rounded-xl bg-white px-3 py-2 shadow-sm">
        {header && (
          <p className="mb-1 text-label-sm font-semibold text-gray-900">{header}</p>
        )}
        <p className="whitespace-pre-wrap text-body-sm text-gray-800">{highlighted}</p>
        {footer && (
          <p className="mt-1 text-label-sm text-gray-400">{footer}</p>
        )}
        <p className="mt-1 text-right text-label-sm text-gray-400">agora ✓✓</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Criar `TemplateList.tsx`**

```tsx
// apps/web/src/features/templates/components/TemplateList.tsx
import Link from "next/link";
import type { MetaTemplate } from "../types";
import { TemplateStatusBadge } from "./TemplateStatusBadge";

interface Props {
  templates: MetaTemplate[];
  onRefresh: () => void;
}

export function TemplateList({ templates, onRefresh }: Props) {
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-headline-sm font-bold text-on-surface">Templates WhatsApp</h1>
        <div className="flex gap-3">
          <button
            onClick={onRefresh}
            className="flex items-center gap-2 rounded-lg border border-outline px-4 py-2 text-label-md text-on-surface-variant hover:bg-surface-container-low"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>refresh</span>
            Atualizar
          </button>
          <Link
            href="/templates/new"
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-label-md font-semibold text-on-primary hover:opacity-90"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>add</span>
            Novo Template
          </Link>
        </div>
      </div>

      {templates.length === 0 ? (
        <div className="rounded-xl border border-outline-variant bg-surface-container-low py-16 text-center text-on-surface-variant">
          Nenhum template encontrado. Crie o primeiro!
        </div>
      ) : (
        <div className="space-y-3">
          {templates.map((t) => (
            <div
              key={t.id}
              className="flex items-center justify-between rounded-xl border border-outline-variant bg-surface-container-low px-5 py-4"
            >
              <div>
                <p className="font-mono text-body-md font-semibold text-on-surface">{t.name}</p>
                <p className="text-label-sm text-on-surface-variant">
                  {t.category} · {t.language}
                </p>
                {t.rejection_reason && (
                  <p className="mt-1 text-label-sm text-error">Motivo: {t.rejection_reason}</p>
                )}
              </div>
              <TemplateStatusBadge status={t.status} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Criar `TemplateForm.tsx`**

```tsx
// apps/web/src/features/templates/components/TemplateForm.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { CreateTemplateDto } from "../types";
import { TemplatePreview } from "./TemplatePreview";

interface Props {
  onCreate: (dto: CreateTemplateDto) => Promise<void>;
}

export function TemplateForm({ onCreate }: Props) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [category, setCategory] = useState<"MARKETING" | "UTILITY" | "AUTHENTICATION">("MARKETING");
  const [language, setLanguage] = useState("pt_BR");
  const [bodyText, setBodyText] = useState("");
  const [headerText, setHeaderText] = useState("");
  const [footerText, setFooterText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function buildComponents(): Record<string, unknown>[] {
    const components: Record<string, unknown>[] = [];

    if (headerText.trim()) {
      components.push({ type: "HEADER", format: "TEXT", text: headerText.trim() });
    }

    if (bodyText.trim()) {
      const vars = [...bodyText.matchAll(/\{\{(\d+)\}\}/g)].map((m) => m[1]);
      const bodyComp: Record<string, unknown> = { type: "BODY", text: bodyText.trim() };
      if (vars.length > 0) {
        bodyComp.example = {
          body_text: [vars.map((v) => `Exemplo variável ${v}`)],
        };
      }
      components.push(bodyComp);
    }

    if (footerText.trim()) {
      components.push({ type: "FOOTER", text: footerText.trim() });
    }

    return components;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!bodyText.trim()) {
      setError("O corpo da mensagem é obrigatório.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onCreate({
        name: name.toLowerCase().replace(/\s+/g, "_"),
        category,
        language,
        components: buildComponents(),
      });
      router.push("/templates");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao criar template na Meta.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-label-sm text-on-surface-variant mb-1">
            Nome do template
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="ex: mv_boas_vindas"
            className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm font-mono text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <p className="mt-1 text-label-sm text-on-surface-variant">
            Somente letras minúsculas, números e underscores.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-label-sm text-on-surface-variant mb-1">Categoria</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as typeof category)}
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="MARKETING">Marketing</option>
              <option value="UTILITY">Utilitário</option>
              <option value="AUTHENTICATION">Autenticação</option>
            </select>
          </div>
          <div>
            <label className="block text-label-sm text-on-surface-variant mb-1">Idioma</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="pt_BR">Português (BR)</option>
              <option value="en_US">English (US)</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-label-sm text-on-surface-variant mb-1">
            Cabeçalho (opcional)
          </label>
          <input
            value={headerText}
            onChange={(e) => setHeaderText(e.target.value)}
            placeholder="Texto do cabeçalho"
            className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-label-sm text-on-surface-variant mb-1">
            Corpo da mensagem <span className="text-error">*</span>
          </label>
          <textarea
            value={bodyText}
            onChange={(e) => setBodyText(e.target.value)}
            required
            rows={5}
            placeholder="Olá {{1}}, seu acesso ao {{2}} está disponível!"
            className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <p className="mt-1 text-label-sm text-on-surface-variant">
            Use {"{{1}}"}, {"{{2}}"} para variáveis dinâmicas.
          </p>
        </div>

        <div>
          <label className="block text-label-sm text-on-surface-variant mb-1">
            Rodapé (opcional)
          </label>
          <input
            value={footerText}
            onChange={(e) => setFooterText(e.target.value)}
            placeholder="Texto do rodapé"
            className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        {error && (
          <div className="rounded-lg border border-error/30 bg-error-container px-4 py-3 text-body-sm text-error">
            {error}
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button
            type="button"
            onClick={() => router.push("/templates")}
            className="rounded-lg px-4 py-2 text-label-md text-on-surface-variant hover:bg-surface-container-high"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-primary px-5 py-2 text-label-md font-semibold text-on-primary disabled:opacity-50"
          >
            {saving ? "Enviando para Meta..." : "Enviar para Meta"}
          </button>
        </div>
      </form>

      <div className="lg:sticky lg:top-6">
        <p className="mb-3 text-label-sm font-semibold uppercase tracking-wider text-on-surface-variant">
          Preview
        </p>
        <TemplatePreview
          body={bodyText || "Escreva o corpo da mensagem..."}
          header={headerText || undefined}
          footer={footerText || undefined}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/templates/components/
git commit -m "feat(meta-templates-ui): componentes TemplateList, TemplateForm e TemplatePreview"
```

---

### Task 6: Páginas e Sidebar

**Files:**
- Create: `apps/web/src/app/(admin)/templates/page.tsx`
- Create: `apps/web/src/app/(admin)/templates/new/page.tsx`
- Modify: `apps/web/src/shared/components/layout/Sidebar.tsx`

- [ ] **Step 1: Criar página `/templates`**

```tsx
// apps/web/src/app/(admin)/templates/page.tsx
"use client";

import { useMetaTemplates } from "@/features/templates/hooks/useMetaTemplates";
import { TemplateList } from "@/features/templates/components/TemplateList";

export default function TemplatesPage() {
  const { templates, loading, error, reload } = useMetaTemplates();

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-on-surface-variant">
        Carregando templates...
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="rounded-xl border border-error/30 bg-error-container px-5 py-4 text-error">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <TemplateList templates={templates} onRefresh={reload} />
    </div>
  );
}
```

- [ ] **Step 2: Criar página `/templates/new`**

```tsx
// apps/web/src/app/(admin)/templates/new/page.tsx
"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMetaTemplates } from "@/features/templates/hooks/useMetaTemplates";
import { TemplateForm } from "@/features/templates/components/TemplateForm";
import { useToast } from "@/shared/hooks/useToast";

export default function NewTemplatePage() {
  const { create } = useMetaTemplates();
  const toast = useToast();
  const router = useRouter();

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-6 flex items-center gap-3">
        <Link href="/templates" className="text-on-surface-variant hover:text-on-surface">
          <span className="material-symbols-outlined" style={{ fontSize: "22px" }}>arrow_back</span>
        </Link>
        <h1 className="text-headline-sm font-bold text-on-surface">Novo Template</h1>
      </div>
      <TemplateForm
        onCreate={async (dto) => {
          await create(dto);
          toast.success("Template enviado para aprovação da Meta");
          router.push("/templates");
        }}
      />
    </div>
  );
}
```

- [ ] **Step 3: Adicionar item "Templates" na Sidebar**

Em `apps/web/src/shared/components/layout/Sidebar.tsx`, no array `NAV_ITEMS`, adicionar:

```typescript
  { label: "Templates", href: "/templates", icon: "sms" },
```

- [ ] **Step 4: Verificar build**

```bash
cd apps/web && npm run build 2>&1 | tail -20
```
Esperado: sem erros de tipo

- [ ] **Step 5: Rodar lint**

```bash
cd apps/web && npm run lint
```
Corrigir qualquer erro.

- [ ] **Step 6: Commit final**

```bash
git add apps/web/src/app/\(admin\)/templates/ \
        apps/web/src/shared/components/layout/Sidebar.tsx
git commit -m "feat(meta-templates-ui): páginas /templates e /templates/new"
```

---

### Task 7: Lint e suite final (backend)

- [ ] **Step 1: Lint backend**

```bash
cd apps/api && uv run ruff check src tests && uv run ruff format --check src tests
```
Corrigir qualquer erro.

- [ ] **Step 2: Suite backend**

```bash
cd apps/api && uv run pytest tests/unit -v --tb=short
```
Esperado: todos `PASSED`

- [ ] **Step 3: Commit de ajustes (se houver)**

```bash
git add -u
git commit -m "style(meta-templates): corrigir lint ruff"
```
