# Spec: Mídia de template no Postgres + Webhook URL na /settings

**Data:** 2026-05-27
**Status:** Em design — aguardando aprovação do usuário
**Branch alvo:** `feat/step-sequence-and-media` (mesma branch da Spec A já implementada — vai abrir 1 PR único)
**Spec anterior na mesma branch:** `2026-05-27-step-sequence-refinement-design.md`

---

## Contexto

Durante o uso do painel em produção, foram identificados 2 atritos no fluxo de templates Meta + onboarding:

1. **Upload de imagem/vídeo/documento em templates está quebrado.** O endpoint `POST /admin/meta-templates/upload-media` retorna **422** com mensagem `R2 não configurado: defina R2_* em .env.local`. A causa raiz é que o backend tenta usar `R2Storage.from_settings(settings)` (Cloudflare R2) e exige que as 5 variáveis R2 estejam preenchidas no `.env.local`. Em dev/prod elas estão vazias, então qualquer upload falha. O usuário não quer depender de provider externo (R2 / Supabase) — quer guardar a mídia no **nosso Postgres**.

2. **A tela de onboarding (passo 3 — mensagens) não mostra a mídia do template selecionado.** Hoje só aparece o nome do template. Quando o usuário escolhe um template com header de imagem/vídeo/documento, a UI deveria renderizar preview da mídia inline — tanto no formulário de edição do step (`StepInlineForm`) quanto no card resumido (`StepItem`). O usuário citou o projeto `polum-app` como referência (`TemplateIPhonePreview` que renderiza a "bolha do WhatsApp" com a mídia embutida).

3. **A tela `/settings` não tem a URL do webhook Hubla nem instruções de como configurar.** Hoje só aparece o campo "Webhook Secret" — quem está configurando o webhook na Hubla pela primeira vez tem que adivinhar a URL e os passos.

Esta spec resolve os 3 itens. A Spec A (refinamento da sequência de mensagens) já está implementada na mesma branch — ao terminar a Spec B, abrimos **1 PR único** com tudo.

---

## Objetivos

1. **Storage de mídia no Postgres** (BYTEA), sem dependência externa.
2. **Endpoint público `GET /public/media/{id}`** servindo bytes com `Content-Type` correto e `Cache-Control` longo (sha256 garante imutabilidade).
3. **Refactor de `POST /admin/meta-templates/upload-media`** para:
   - Continuar fazendo resumable upload pra Meta (pega `handle`)
   - Salvar BYTEA na tabela nova
   - Retornar `media_url` apontando pro nosso endpoint público
4. **Remover** o adapter `R2Storage` e suas variáveis de configuração (`R2_*`).
5. **Preview de mídia inline** no `StepInlineForm` (modal de edição do step):
   - Hook `useMetaTemplateDetail(name)` que carrega template completo
   - Componente `TemplatePreview` (novo, inspirado no `TemplateIPhonePreview` do polum-app) com bolha WhatsApp + mídia embutida + body + footer + botões
6. **Thumbnail compacto** no `StepItem` quando o template referenciado tem mídia.
7. **Card "Webhook Hubla"** na seção `/settings`:
   - URL completa do endpoint `/webhook/hubla` com botão "Copiar"
   - Lista numerada de passos pra configurar na Hubla
   - Botão "Copiar" no campo Webhook Secret existente

## Não-objetivos

- **Não migra mídias antigas** (templates pré-existentes na Meta cuja mídia foi feita antes desta spec). Continuam funcionando via handle interno da Meta no envio — só não terão preview no nosso painel até re-upload.
- **Não implementa streaming chunked** do BYTEA (read completo na memória) — viável por causa dos limites (max 16MB). Se virar gargalo, otimização futura.
- **Não toca no fluxo de envio** (`ChatNexoClient.send_template`). O `header_link` que o ChatNexo recebe passa a apontar pro nosso `/public/media/{id}` — funciona porque a URL é pública e estável.
- **Não muda o stepper de 3 passos** já refatorado.
- **Não toca a Spec A** (já implementada).

---

## Arquitetura

### Backend

```
apps/api/src/
├── shared/
│   ├── adapters/
│   │   ├── db/
│   │   │   ├── models.py                            ← + MetaTemplateMediaModel (BYTEA + metadata)
│   │   │   └── repositories/
│   │   │       └── meta_template_media_repo.py     ← NOVO: insert + get + dedup por sha256
│   │   ├── meta/
│   │   │   └── template_client.py                  ← inalterado (upload resumable mantém)
│   │   └── storage/                                 ← REMOVIDO o diretório inteiro (era só R2 + Null)
│   ├── application/
│   │   └── use_cases/
│   │       └── meta_templates/
│   │           ├── upload_template_media.py         ← refatorado: usa repo do Postgres
│   │           └── create_template.py               ← usa media_url do nosso endpoint
│   ├── config/
│   │   └── settings.py                              ← removidas vars R2_*
│   └── domain/
│       └── ports/
│           └── storage.py                           ← REMOVIDO (StoragePort)
├── interface/
│   └── http/
│       ├── routers/
│       │   ├── admin/meta_templates.py              ← upload-media usa repo novo
│       │   └── public_media.py                      ← NOVO router público (sem auth)
│       └── schemas/
│           └── meta_templates.py                    ← inalterado
└── migrations/versions/
    └── <rev>_meta_template_media_table.py           ← NOVO
```

### Frontend

```
apps/web/src/
├── features/
│   ├── onboarding/
│   │   ├── components/
│   │   │   ├── StepItem.tsx                         ← + thumbnail compacto (40×40) quando template tem mídia
│   │   │   ├── StepInlineForm.tsx                   ← + preview iPhone do template selecionado
│   │   │   └── TemplatePreview.tsx                  ← NOVO: bolha WhatsApp + mídia + body + buttons
│   │   └── hooks/
│   │       └── useMetaTemplateDetail.ts             ← NOVO: fetch + cache de 1 template por nome
│   ├── settings/
│   │   └── components/
│   │       └── HublaWebhookCard.tsx                 ← NOVO: URL copiável + instruções
│   └── templates/
│       └── components/
│           └── MediaUploadField.tsx                 ← inalterado (continua chamando upload-media)
├── app/(admin)/settings/page.tsx                    ← adiciona <HublaWebhookCard /> na seção Hubla
└── lib/api.ts                                       ← inalterado (uploadTemplateMedia retorna mesmo shape)
```

---

## Detalhamento por demanda

### 1. Tabela `meta_template_media` (migration nova)

```sql
CREATE TABLE meta_template_media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    kind VARCHAR(16) NOT NULL CHECK (kind IN ('IMAGE', 'VIDEO', 'DOCUMENT')),
    mime VARCHAR(128) NOT NULL,
    sha256 CHAR(64) NOT NULL,
    size_bytes INTEGER NOT NULL,
    data BYTEA NOT NULL,
    original_filename VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Dedup por sha256 dentro da conta (evita guardar mesma imagem 2x)
CREATE UNIQUE INDEX uq_meta_template_media_account_sha
    ON meta_template_media (account_id, sha256);

-- Índice de lookup rápido (servir o endpoint público)
CREATE INDEX ix_meta_template_media_id ON meta_template_media (id);
```

Limites por `kind` (validados no use case antes do INSERT):

| kind | max_size_bytes | rejeição |
|---|---|---|
| IMAGE | 5_242_880 (5 MB) | HTTP 413 com mensagem clara |
| VIDEO | 16_777_216 (16 MB) | idem |
| DOCUMENT | 16_777_216 (16 MB) | idem |

### 2. Endpoint `POST /admin/meta-templates/upload-media` — refactor

**Pipeline novo:**

1. Validar `kind ∈ {IMAGE, VIDEO, DOCUMENT}`.
2. Ler bytes do `UploadFile` (await `file.read()`).
3. Validar `len(data) <= limite[kind]` — rejeitar com 413 se exceder.
4. Calcular `sha256 = hashlib.sha256(data).hexdigest()`.
5. Verificar se já existe registro em `meta_template_media (account_id, sha256)`:
   - Existe → reusar `id`, retornar a mesma `media_url`.
   - Não existe → INSERT novo registro com bytes + metadata.
6. (Mantém) chamar `MetaTemplateClient.create_resumable_upload_session` + `upload_media_resumable` pra pegar o `handle` da Meta. **Esse passo já existe — não muda.**
7. Retornar:
   ```json
   {
     "media_url": "https://api-iag2.ianexo.com.br/public/media/<id>",
     "media_object_key": "<id>",
     "media_kind": "IMAGE",
     "sha256": "<sha>",
     "size": 12345
   }
   ```

**Schema do response (`UploadMediaResponse`) mantém shape compatível** — só o domínio de `media_url` muda (passa a apontar pra nós em vez do R2). `media_object_key` agora é o UUID do registro em `meta_template_media`.

### 3. Endpoint `GET /public/media/{id}` (router novo, sem auth)

`apps/api/src/interface/http/routers/public_media.py`:

```python
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
    """Serve o conteúdo binário de um template media.

    PÚBLICO (sem auth) — necessário porque a Meta e o ChatNexo precisam
    baixar o arquivo via URL. SHA256 garante imutabilidade do conteúdo,
    então Cache-Control longo é seguro.
    """
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

Montar o router em `main.py`:
```python
from interface.http.routers.public_media import router as public_media_router
app.include_router(public_media_router)
```

### 4. Repository `MetaTemplateMediaRepository`

`apps/api/src/shared/adapters/db/repositories/meta_template_media_repo.py`:

```python
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

### 5. `UploadTemplateMedia` use case — refactor

`apps/api/src/shared/application/use_cases/meta_templates/upload_template_media.py`:

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

# Limites por tipo (em bytes)
_SIZE_LIMITS = {
    "IMAGE": 5 * 1024 * 1024,
    "VIDEO": 16 * 1024 * 1024,
    "DOCUMENT": 16 * 1024 * 1024,
}


class MediaTooLargeError(Exception):
    def __init__(self, kind: str, size: int, limit: int) -> None:
        super().__init__(f"{kind} de {size} bytes excede o limite de {limit} bytes")
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
    media_object_key: str  # = str(media_id)
    media_kind: str
    sha256: str
    size: int


class UploadTemplateMedia:
    """Salva mídia no Postgres (dedup por sha256) e retorna URL pública servida pelo nosso endpoint."""

    def __init__(self, *, repo, public_base_url: str) -> None:
        self._repo = repo
        self._public_base_url = public_base_url.rstrip("/")

    async def execute(self, input_: UploadTemplateMediaInput) -> UploadTemplateMediaOutput:
        limit = _SIZE_LIMITS[input_.kind]
        if len(input_.data) > limit:
            raise MediaTooLargeError(input_.kind, len(input_.data), limit)

        sha256 = hashlib.sha256(input_.data).hexdigest()
        existing = await self._repo.get_by_sha(account_id=input_.account_id, sha256=sha256)
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

    def _to_output(self, record) -> UploadTemplateMediaOutput:
        return UploadTemplateMediaOutput(
            media_id=record.id,
            media_url=f"{self._public_base_url}/public/media/{record.id}",
            media_object_key=str(record.id),
            media_kind=record.kind,
            sha256=record.sha256,
            size=record.size_bytes,
        )
```

A nova configuração: `settings.public_base_url` (ex: `https://api-iag2.ianexo.com.br`). Adicionar em `Settings`:

```python
class Settings(BaseSettings):
    # ... existing ...
    public_base_url: str  # ex: "https://api-iag2.ianexo.com.br"
```

E em `.env.example`:
```
PUBLIC_BASE_URL=
```

Em `.env.local` (dev):
```
PUBLIC_BASE_URL=https://api-iag2-dev.ianexo.com.br
```

### 6. Remover `R2Storage` adapter

- Apagar `apps/api/src/shared/adapters/storage/` (diretório inteiro: `r2.py`, `null_storage.py` se houver, `__init__.py`).
- Apagar `apps/api/src/shared/domain/ports/storage.py` (StoragePort).
- Remover do `Settings`: `r2_account_id`, `r2_access_key_id`, `r2_secret_access_key`, `r2_bucket_name`, `r2_public_base_url`.
- Remover de `.env.example`: linhas `R2_*`.
- Remover imports e usos em:
  - `apps/api/src/interface/http/routers/admin/meta_templates.py` (linhas que importam `R2Storage` e fazem `from_settings`/`from_settings_or_null`)
  - Outros lugares onde `StoragePort` é injetado

Manter `MetaTemplateClient.create_resumable_upload_session` + `upload_media_resumable` (continuam usados pra pegar o handle da Meta).

### 7. Frontend — `TemplatePreview` (componente novo)

`apps/web/src/features/onboarding/components/TemplatePreview.tsx`:

Bolha de WhatsApp simplificada (não precisa ser o iPhone completo do polum — pode ser só o quadro de mensagem), com:

- Se header existe e é IMAGE: `<img src={media_url} class="rounded mb-2 max-h-48 w-full object-cover" />`
- Se header é VIDEO: `<video src={media_url} controls class="rounded mb-2 max-h-48 w-full" />`
- Se header é DOCUMENT: ícone + nome do documento + link
- Se header é TEXT: bold-text com variáveis renderizadas em `{{n}}`
- Body do template (`text-sm`, multiline com `whitespace-pre-wrap`)
- Footer cinza-pequeno (se houver)
- Botões (se houver) renderizados como pills

Tokens NexoIA: `bg-surface-container`, `text-on-surface`, `border-outline-variant`.

### 8. Hook `useMetaTemplateDetail`

`apps/web/src/features/onboarding/hooks/useMetaTemplateDetail.ts`:

```ts
"use client";

import { useEffect, useState } from "react";
import { listMetaTemplates } from "@/lib/api";
import type { MetaTemplate } from "@/features/templates/types";

/**
 * Busca o template Meta pelo `name` e retorna os componentes completos
 * (incluindo media_url/media_kind). Cache simples em módulo entre chamadas.
 */
const _cache: Record<string, MetaTemplate> = {};

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
    setLoading(true);
    listMetaTemplates()
      .then((all) => {
        const found = all.find((t) => t.name === name) ?? null;
        if (found) {
          _cache[name] = found;
          setTemplate(found);
        }
      })
      .finally(() => setLoading(false));
  }, [name]);

  return { template, loading };
}
```

### 9. Refactor `StepInlineForm` — preview de mídia

No `StepInlineForm.tsx`, abaixo do select de template + preview do body atual, adicionar:

```tsx
const { template: detail } = useMetaTemplateDetail(selectedTemplate);

// ... dentro do JSX, dentro do bloco template-mode:
<Collapse open={!!detail} durationMs={380}>
  <TemplatePreview template={detail} />
</Collapse>
```

O componente `TemplatePreview` lê `detail.components` e renderiza com `media_url` quando há header de mídia.

### 10. Refactor `StepItem` — thumbnail compacto

Quando `step.meta_template_name` está setado, o `StepItem` puxa o `useMetaTemplateDetail(name)` e exibe um thumb 40×40 à esquerda do ícone padrão:

```tsx
{detail && hasMedia(detail) ? (
  <MediaThumbnail
    url={getMediaUrl(detail)}
    kind={getMediaKind(detail)}
    className="h-10 w-10"
  />
) : (
  <span className="material-symbols-outlined ...">description</span>
)}
```

Helpers `hasMedia`, `getMediaUrl`, `getMediaKind` em `apps/web/src/features/onboarding/lib/templateMediaHelpers.ts` (utilitário simples extraindo do `components[]` do template).

### 11. Webhook URL + instruções na `/settings`

Novo componente `apps/web/src/features/settings/components/HublaWebhookCard.tsx`:

```tsx
"use client";

import { useToast } from "@/shared/hooks/useToast";

const HUBLA_WEBHOOK_URL = "https://api-iag2.ianexo.com.br/webhook/hubla";

export function HublaWebhookCard() {
  const toast = useToast();

  async function copy(value: string, label: string) {
    await navigator.clipboard.writeText(value);
    toast.success(`${label} copiado`);
  }

  return (
    <div className="rounded-lg border border-outline-variant bg-surface-container-low p-4">
      <h4 className="text-sm font-semibold text-on-surface">URL do Webhook</h4>
      <p className="mt-1 text-xs text-on-surface-variant">
        Configure essa URL no painel da Hubla para receber eventos.
      </p>
      <div className="mt-3 flex items-center gap-2 rounded-md border border-outline-variant bg-surface px-3 py-2">
        <code className="flex-1 text-xs font-mono text-on-surface truncate">
          {HUBLA_WEBHOOK_URL}
        </code>
        <button
          type="button"
          onClick={() => void copy(HUBLA_WEBHOOK_URL, "URL")}
          className="rounded-md p-1.5 text-on-surface-variant hover:bg-surface-container-high"
          aria-label="Copiar URL"
        >
          <span className="material-symbols-outlined text-base">content_copy</span>
        </button>
      </div>

      <h4 className="mt-5 text-sm font-semibold text-on-surface">Como configurar na Hubla</h4>
      <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-xs text-on-surface-variant">
        <li>Acesse o painel da Hubla → Configurações → Webhooks.</li>
        <li>Crie um webhook novo e cole a URL acima no campo "URL do endpoint".</li>
        <li>
          No campo "Secret" / "Token", cole o mesmo valor configurado em <strong>Webhook Secret</strong> acima.
        </li>
        <li>
          Selecione os eventos que quer disparar fluxos de onboarding (ex:{" "}
          <code>subscription.activated</code>, <code>lead.abandoned_cart</code>, etc).
        </li>
        <li>
          Salve. A partir daí, qualquer evento dispara automaticamente os fluxos
          configurados em <strong>/onboarding</strong>.
        </li>
      </ol>
    </div>
  );
}
```

**Integração** em `apps/web/src/app/(admin)/settings/page.tsx`:

Localizar a seção Hubla (já existe via `IntegrationSection` config). Adicionar logo após o campo "Webhook Secret":

```tsx
<HublaWebhookCard />
```

A URL `HUBLA_WEBHOOK_URL` é hardcoded por enquanto (poderia vir de env var `NEXT_PUBLIC_WEBHOOK_BASE_URL`, mas pra simplicidade e dado que o painel é single-tenant, hardcoded basta).

### 12. Botão Copiar no campo Webhook Secret existente

O input `Webhook Secret` em `IntegrationSection.tsx` é um `<input type="password">` padrão. Adicionar um botão de copiar à direita do campo (mostra valor descriptografado em texto temporário ao copiar, mas o input permanece em password mask).

> Detalhe técnico: o frontend recebe o secret descriptografado do backend (já é o comportamento atual via `useIntegrationForm`). O botão copiar usa o valor em estado JS.

Mudança pequena — não muda o layout da seção.

---

## Data flow

### Fluxo de upload de mídia

```
1. Usuário escolhe arquivo no MediaUploadField (TemplateForm)
2. POST /admin/meta-templates/upload-media (multipart: file + kind)
3. Backend:
   a. Valida kind + tamanho (rejeita 413 se exceder)
   b. Calcula sha256 dos bytes
   c. dedup: se já existe em meta_template_media (account_id, sha256), reusa id
   d. Senão, INSERT novo registro com BYTEA
   e. MetaTemplateClient.create_resumable_upload_session + upload_media_resumable → handle Meta
4. Retorna { media_url=https://api-iag2.../public/media/<id>, media_object_key=<id>, media_kind, sha256, size, meta_handle? }
5. Frontend usa media_url no preview do TemplateForm + envia ao criar template
```

### Fluxo de preview no onboarding

```
1. Usuário abre StepInlineForm (editar/criar step)
2. Seleciona um template no select
3. useMetaTemplateDetail(template_name) → fetch da lista (1x, cache em módulo)
4. detail.components → procura HEADER → se IMAGE/VIDEO/DOCUMENT, pega media_url
5. <TemplatePreview template={detail} /> renderiza bolha com mídia + body + footer
6. StepItem (linha compacta) usa mesmo hook + helper hasMedia/getMediaUrl
```

### Fluxo de envio (ChatNexo recebe URL pública)

```
Worker → DispatchOnboardingStep → ChatNexoClient.send_template
  → body.template_params.header.link = "https://api-iag2.../public/media/<id>"
  → ChatNexo encaminha pra Meta:
    a. Dentro de janela 24h: ChatNexo envia como texto livre com `content` + downloads a URL
    b. Fora da janela: ChatNexo dispara Meta WhatsApp template; Meta baixa do nosso /public/media/{id}
```

(Hoje o `ChatNexoClient.send_template` já tem campo `header_link` — só passamos o URL novo.)

---

## Error handling

- **Upload > limite:** `MediaTooLargeError` → router converte em HTTP **413** com mensagem clara (`IMAGE de 8388608 bytes excede o limite de 5242880 bytes`).
- **Meta resumable upload falha (network/auth):** mesmo comportamento atual — propaga como 502.
- **Insert no Postgres falha (deadlock):** retry no nível do session_scope ou retorna 500. Não comum.
- **GET /public/media/{id} com UUID inválido:** FastAPI retorna 422 automaticamente. UUID válido + sem registro → 404.
- **`useMetaTemplateDetail` com template não-aprovado:** o `listMetaTemplates` retorna todos os templates da conta — se template foi excluído entre `listFollowupSteps` e o fetch, hook retorna `null` e o preview some (sem erro visível).

---

## Testes

### Backend

- **Unit test `UploadTemplateMedia`**: matrix de (kind, size) cobrindo casos válidos (5MB image OK), inválidos (6MB image → MediaTooLargeError), dedup (sha repetido reusa id).
- **Unit test `MetaTemplateMediaRepository`**: insert + get_by_id + get_by_sha + unique constraint via integration test (opcional).
- **Integration test** (se rodar postgres): `GET /public/media/{id}` retorna Content-Type correto + bytes íntegros (assert SHA do response).
- **Migration test:** upgrade cria tabela com colunas + constraint; downgrade dropa.

### Frontend

- **Smoke manual:** abrir TemplateForm, upload IMAGE 2MB → ver URL retornada apontando pra `/public/media/<id>`. Acessar URL direto no browser → renderiza imagem.
- **Smoke manual:** abrir flow no /onboarding, expandir step com template que tem mídia → preview iPhone aparece com imagem embutida. StepItem mostra thumbnail.
- **Smoke manual:** abrir /settings → card "URL do Webhook" aparece com botão copiar funcional. Lista de passos visível.

---

## Riscos

| Risco | Severidade | Mitigação |
|---|---|---|
| BYTEA grandes (16MB) inflam tamanho dos backups Postgres | Baixa | Limites por kind + dedup por sha256. Em dev/prod com poucos templates (< 100), volume controlado. |
| Endpoint `/public/media/{id}` exposto sem auth | Baixa | UUID gera entropia suficiente pra evitar enumeração. Sem path-traversal ou injection (UUID é tipado). |
| URL `media_url` mudou de R2 → nosso endpoint | Média | Templates pré-existentes em prod tinham `media_url` apontando pro R2 (que provavelmente nunca subiu nada). Sem impacto real. |
| Removendo R2Storage pode quebrar testes que injetam StoragePort | Média | Buscar todos os usos de `StoragePort` / `R2Storage` antes de remover e atualizar/remover testes correspondentes. |
| `useMetaTemplateDetail` faz fetch da lista inteira sempre | Baixa | Cache em módulo evita refetch quando vários StepItem usam mesmo template. Para flows com 10+ steps, ok. |
| Postgres write de 16MB em transação pode bloquear | Baixa | Acontece raramente (só ao criar template). Não está no caminho crítico de envio. |

---

## Critérios de aceite

### Mídia no Postgres
- [ ] Migration cria tabela `meta_template_media` com BYTEA + constraint unique `(account_id, sha256)`.
- [ ] Upload de IMAGE 2MB via TemplateForm completa sem erro 422.
- [ ] Dedup: upload de mesma imagem 2x retorna mesmo `media_url`.
- [ ] Upload de IMAGE 6MB rejeita com 413.
- [ ] `GET /public/media/<id>` (sem auth) retorna bytes com `Content-Type` correto.
- [ ] `Cache-Control: public, max-age=31536000, immutable` no response.

### Preview no onboarding
- [ ] Ao selecionar template com header IMAGE no StepInlineForm, preview mostra a imagem inline.
- [ ] Para VIDEO, renderiza `<video controls>`.
- [ ] Para DOCUMENT, renderiza ícone + nome.
- [ ] StepItem mostra thumbnail 40×40 quando template referenciado tem mídia.
- [ ] Templates sem mídia continuam funcionando (sem preview/thumbnail).

### Webhook na /settings
- [ ] Card "URL do Webhook" aparece logo abaixo do campo "Webhook Secret".
- [ ] URL mostrada: `https://api-iag2.ianexo.com.br/webhook/hubla`.
- [ ] Botão copiar funciona (toast de confirmação).
- [ ] Lista numerada de 5 passos visível.
- [ ] Botão copiar no campo "Webhook Secret" funciona.

### R2 removido
- [ ] Diretório `apps/api/src/shared/adapters/storage/` removido.
- [ ] `StoragePort` removido de `domain/ports/`.
- [ ] Settings limpo (sem `r2_*`).
- [ ] `.env.example` sem linhas `R2_*`, com `PUBLIC_BASE_URL=`.
- [ ] Imports de R2 limpos do router de meta_templates.
- [ ] 484 testes continuam passando (testes que usavam StoragePort mockado ajustados).

---

## Plano de plan-time (próximos passos após aprovação)

1. Confirmar se `MediaUploadField` no frontend precisa adaptar shape do retorno (provavelmente não — mantém `media_url`/`media_object_key`/`media_kind` no shape).
2. Decidir se botão copiar do "Webhook Secret" entra na mesma task que `HublaWebhookCard` ou em task separada (pequeno, vai junto).
3. Validação visual final do `TemplatePreview` — quão fiel ao iPhone do polum? Sugestão: começar simples (bolha + mídia + texto) e iterar se UX validar.

Após implementar, **abrir 1 PR único** com tudo da branch `feat/step-sequence-and-media` (Spec A + Spec B).
