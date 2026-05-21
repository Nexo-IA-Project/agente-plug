# NexoIA — Meta Templates com Upload de Mídia

**Data:** 2026-05-08
**Status:** Aprovado
**Subsistema:** Meta Template Manager — fase 2 (upload de mídia + validações + storage R2)
**Depende de:** Meta Template Manager (Spec A — 2026-05-07), Account Settings, Follow-up Engine

---

## Visão Geral

Hoje o cadastro de templates Meta aceita apenas URL externa para o header de mídia, sem upload, sem armazenamento próprio e com validações mínimas. Esta fase entrega:

1. **Upload nativo** de imagem, vídeo e documento direto no formulário
2. **Bucket Cloudflare R2** próprio para guardar a mídia (URL pública estável usada em todos os disparos futuros)
3. **Resumable upload na Meta** durante a criação do template (handle obrigatório no `header_handle`)
4. **Validação completa** das regras Meta no formulário e no backend (caracteres, variáveis, botões, mídia)
5. **Sincronização sob demanda** do status `PENDING/APPROVED/REJECTED` ao listar `/templates`
6. **Disparo com mídia** — `ChatNexoClient.send_template` ganha `header_link` + `header_kind`
7. **Schema persistente** dos componentes do template para preview offline e bloqueio de exclusão se em uso

---

## Decisões Consolidadas (clarificações)

| Decisão | Escolha |
|---|---|
| Storage de mídia | **Cloudflare R2** (S3-compatible, sem egress) |
| Caminho de disparo | **Estender `ChatNexoClient`** (ChatNexo já aceita `header.link`) |
| Validações | **Completas** — todas as regras Meta no frontend e backend |
| Persistência local | **Componentes JSONB + `media_url` no `MetaTemplate`** |
| Sincronização de status | **Polling sob demanda** ao listar `/templates` |
| Edição/Exclusão | **Sem edição. Excluir bloqueia se em uso por `FollowupStep`** |
| Categorias suportadas | **MARKETING e UTILITY** (sem AUTHENTICATION) |
| Variáveis | **Apenas posicionais** `{{1}}`, `{{2}}`... (sem nomeadas) |

---

## Requisitos Funcionais

| # | Requisito |
|---|-----------|
| RF-MT2-01 | Formulário aceita upload de IMAGE/VIDEO/DOCUMENT via drag-and-drop ou file picker |
| RF-MT2-02 | Mídia é enviada para R2 imediatamente após seleção (preview com URL pública) |
| RF-MT2-03 | Trocar a mídia no form remove o objeto antigo do R2 antes de subir o novo |
| RF-MT2-04 | Submissão do template faz resumable upload na Meta (`POST /{app_id}/uploads` → handle) e cria o template usando o handle no `header_handle` |
| RF-MT2-05 | Componentes (header/body/footer/buttons) e referência da mídia (URL R2 + object key) ficam persistidos na tabela `meta_templates` |
| RF-MT2-06 | Listagem `/templates` faz polling sob demanda dos templates `PENDING` na Meta e atualiza status |
| RF-MT2-07 | Templates `REJECTED` exibem `rejection_reason` da Meta |
| RF-MT2-08 | Disparo via `dispatch_followup_step` envia `header_link` + `header_kind` ao ChatNexo quando o template tem mídia |
| RF-MT2-09 | Excluir template valida se há `FollowupStep` referenciando — bloqueia com **409** + lista de flows em uso |
| RF-MT2-10 | Excluir template (quando permitido) remove na Meta, no R2 e no DB nessa ordem |
| RF-MT2-11 | Form valida em tempo real: limites de caracteres, variáveis sequenciais sem adjacentes, formato/tamanho de arquivo, regras de botões |
| RF-MT2-12 | Categorias disponíveis: `MARKETING` e `UTILITY` |
| RF-MT2-13 | Variáveis aceitas no body são apenas posicionais `{{1}}`, `{{2}}`...; cada variável detectada exige um exemplo |

## Requisitos Não-Funcionais

| # | Requisito |
|---|-----------|
| RNF-MT2-01 | Credenciais R2 e `META_APP_ID` ficam exclusivamente em `.env.local` (regra do projeto) |
| RNF-MT2-02 | Adapter `R2Storage` segue o padrão de port em `shared/domain/ports/storage.py` |
| RNF-MT2-03 | Validação completa dos componentes Meta é compartilhada entre frontend e backend (mesma fonte de regras) |
| RNF-MT2-04 | Falha em qualquer etapa após upload R2 deleta o objeto pra não deixar órfão |
| RNF-MT2-05 | `media_url` no R2 deve ser pública e estável (sem expiração) para a Meta consumir em cada disparo |
| RNF-MT2-06 | Rate limit Meta de 200 criações/hora respeitado — sem batch automático |
| RNF-MT2-07 | Cobertura de testes unitários ≥80% em validators e R2 adapter |

---

## Arquitetura

### Fluxo 1 — Criação de Template com Mídia

```
[Frontend /templates (modal)]
  1. Usuário escolhe tipo de header (IMAGE/VIDEO/DOCUMENT) e seleciona arquivo
  2. Frontend valida formato/tamanho local
  3. POST /admin/meta-templates/upload-media (multipart) ─────┐
                                                              │
[Backend]                                                     │
  4. Valida arquivo (mime, tamanho por tipo)                  │
  5. Calcula sha256 + gera key: accounts/{account_id}/templates/{uuid}.{ext}
  6. Sobe para R2 com Content-Type correto                    │
  7. Retorna { media_url, media_object_key, media_kind, sha256, size } ─┘

  8. Usuário preenche restante e clica "Criar template"
  9. POST /admin/meta-templates { name, category, language, components, media_url, media_object_key, media_kind }

[Backend create_template_use_case]
 10. Valida payload completo (todas as regras Meta)
 11. Baixa bytes do R2 (httpx.get(media_url))
 12. POST /{app_id}/uploads → upload session ID
 13. POST /{session_id} com bytes binários → recebe handle
 14. Substitui header.example.header_handle = [handle] no payload
 15. POST /{waba_id}/message_templates (Meta API)
 16. Recebe meta_template_id e status (geralmente PENDING)
 17. INSERT em meta_templates com components JSONB + media_url + status
 18. Retorna 201 com o template criado

[Em caso de erro nas etapas 12–16:] DELETE objeto R2 + retorna 502
```

### Fluxo 2 — Listagem com Sincronização

```
GET /admin/meta-templates
 → SELECT * FROM meta_templates WHERE account_id = :account
 → Se houver registros com status='PENDING':
     GET /{waba_id}/message_templates (Meta API)
     Para cada PENDING: UPDATE status (APPROVED/REJECTED + rejection_reason)
 → Retorna lista atualizada
```

### Fluxo 3 — Disparo no Worker

```
DispatchFollowupStep (use case existente, atualizado):
  - Carrega step + meta_template
  - Se template.media_url and template.media_kind:
      header_link  = template.media_url
      header_kind  = template.media_kind.lower()  # "image" | "video" | "document"
  - chatnexo.send_template(name=..., variables=..., header_link=..., header_kind=...)
```

### Fluxo 4 — Exclusão

```
DELETE /admin/meta-templates/{id}
 1. SELECT FollowupStep WHERE meta_template_name = :name AND account_id = :account
    → Se existir: 409 Conflict { code: "META_TEMPLATE_IN_USE", flows: [...] }
 2. DELETE Meta API: DELETE /{waba_id}/message_templates?name=:name
    → Se falhar: 502 META_API_ERROR
 3. R2Storage.delete(media_object_key) (se houver mídia)
    → Se falhar: log warning + audit_event (r2_cleanup_pending), prossegue
 4. DELETE FROM meta_templates WHERE id = :id
 5. INSERT INTO audit_events (kind='meta_template.deleted', ...)
 6. 204 No Content
```

---

## Schema do Banco

### Migration: `f3a4b5c6d7e8_meta_templates_media.py`

```sql
ALTER TABLE meta_templates
  ADD COLUMN category VARCHAR(32) NOT NULL DEFAULT 'UTILITY',
  ADD COLUMN components JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN media_url TEXT,
  ADD COLUMN media_object_key TEXT,
  ADD COLUMN media_kind VARCHAR(16),               -- 'IMAGE' | 'VIDEO' | 'DOCUMENT'
  ADD COLUMN media_sha256 VARCHAR(64),
  ADD COLUMN media_size BIGINT,
  ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'PENDING',  -- 'PENDING' | 'APPROVED' | 'REJECTED'
  ADD COLUMN rejection_reason TEXT;

UPDATE meta_templates SET status = 'APPROVED' WHERE approved = TRUE;
ALTER TABLE meta_templates DROP COLUMN approved;

ALTER TABLE meta_templates ADD CONSTRAINT chk_media_consistency
  CHECK ((media_url IS NULL AND media_kind IS NULL AND media_object_key IS NULL) OR
         (media_url IS NOT NULL AND media_kind IS NOT NULL AND media_object_key IS NOT NULL));

ALTER TABLE meta_templates ADD CONSTRAINT uq_meta_template_account_name
  UNIQUE (account_id, name);

CREATE INDEX ix_meta_templates_status ON meta_templates(status);
```

### Modelo SQLAlchemy

```python
class MetaTemplate(Base):
    __tablename__ = "meta_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"))
    name: Mapped[str]
    meta_template_id: Mapped[str | None]
    category: Mapped[str]                                    # MARKETING | UTILITY
    language: Mapped[str]
    components: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    variables_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    media_url: Mapped[str | None]
    media_object_key: Mapped[str | None]
    media_kind: Mapped[str | None]                           # IMAGE | VIDEO | DOCUMENT
    media_sha256: Mapped[str | None]
    media_size: Mapped[int | None]
    status: Mapped[str] = mapped_column(default="PENDING")
    rejection_reason: Mapped[str | None]
    last_synced_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("account_id", "name", name="uq_meta_template_account_name"),
        Index("ix_meta_templates_status", "status"),
    )
```

### Estrutura do `components` JSONB

Espelha exatamente o que enviamos pra Meta. Exemplo:

```json
[
  {
    "type": "HEADER",
    "format": "IMAGE",
    "example": {"header_handle": ["4::aW1hZ2UvanBlZw=="]}
  },
  {
    "type": "BODY",
    "text": "Olá {{1}}, sua compra de {{2}} foi confirmada!",
    "example": {"body_text": [["Fabio", "Curso de Vendas"]]}
  },
  {"type": "FOOTER", "text": "Equipe NexoIA"},
  {
    "type": "BUTTONS",
    "buttons": [
      {"type": "URL", "text": "Acessar", "url": "https://app.com/{{1}}", "example": ["abc123"]},
      {"type": "QUICK_REPLY", "text": "Cancelar"}
    ]
  }
]
```

> O `header_handle` é descartado depois da criação (válido só pra aprovação Meta). A `media_url` no R2 é o que sobrevive pra todos os disparos.

---

## Backend

### Estrutura de Diretórios Novos

```
apps/api/src/
├── shared/
│   ├── adapters/
│   │   ├── storage/                          ← NOVO
│   │   │   ├── __init__.py
│   │   │   └── r2.py                         ← R2Storage adapter
│   │   └── meta/
│   │       └── template_client.py            ← ATUALIZADO: resumable upload
│   ├── application/
│   │   └── use_cases/
│   │       └── meta_templates/               ← NOVO (módulo dedicado)
│   │           ├── __init__.py
│   │           ├── upload_template_media.py
│   │           ├── create_template.py
│   │           ├── list_templates.py
│   │           ├── delete_template.py
│   │           └── validators.py             ← regras Meta centralizadas
│   └── domain/
│       └── ports/
│           └── storage.py                    ← NOVO: StoragePort
└── interface/
    └── http/
        └── routers/
            └── admin/
                └── meta_templates.py         ← ATUALIZADO: + upload + delete
```

### `shared/domain/ports/storage.py`

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass
class StorageObject:
    url: str
    object_key: str
    size: int
    sha256: str
    content_type: str

class StoragePort(Protocol):
    async def upload(
        self, key: str, data: bytes, content_type: str
    ) -> StorageObject: ...
    async def delete(self, key: str) -> None: ...
    async def head(self, key: str) -> StorageObject | None: ...
```

### `shared/adapters/storage/r2.py`

Implementa `StoragePort` usando `boto3` com endpoint customizado:

```python
class R2Storage(StoragePort):
    def __init__(
        self, *, account_id: str, access_key_id: str,
        secret_access_key: str, bucket_name: str, public_base_url: str
    ):
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )
        self._bucket = bucket_name
        self._public_base_url = public_base_url

    async def upload(self, key, data, content_type):
        sha256 = hashlib.sha256(data).hexdigest()
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket, Key=key, Body=data,
            ContentType=content_type, Metadata={"sha256": sha256},
        )
        return StorageObject(
            url=f"{self._public_base_url}/{key}",
            object_key=key, size=len(data),
            sha256=sha256, content_type=content_type,
        )

    async def delete(self, key):
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._bucket, Key=key
        )

    async def head(self, key): ...
```

### `shared/adapters/meta/template_client.py` — Adições

```python
async def create_resumable_upload_session(
    self, *, app_id: str, file_size: int, file_type: str
) -> str:
    """POST /{app_id}/uploads?file_length=...&file_type=... → retorna session ID."""

async def upload_media_resumable(
    self, *, session_id: str, data: bytes
) -> str:
    """POST /{session_id} com header file_offset=0 + body binário → retorna handle."""

async def delete_template(
    self, *, waba_id: str, name: str
) -> None:
    """DELETE /{waba_id}/message_templates?name=:name"""
```

### `shared/application/use_cases/meta_templates/validators.py`

Função pura `validate_template_payload(payload: dict) -> list[ValidationError]`:

```python
HEADER_TEXT_MAX = 60
BODY_TEXT_MAX = 1024
FOOTER_MAX = 60
BUTTON_LABEL_MAX = 25
BUTTON_URL_MAX = 2000
QUICK_REPLY_MAX = 10
CTA_MAX = 2

MEDIA_LIMITS = {
    "IMAGE":    {"mimes": ["image/jpeg", "image/png"],          "max_bytes": 5  * 1024 * 1024},
    "VIDEO":    {"mimes": ["video/mp4"],                          "max_bytes": 16 * 1024 * 1024},
    "DOCUMENT": {"mimes": ["application/pdf"],                    "max_bytes": 100 * 1024 * 1024},
}

def validate_template_payload(payload: dict) -> list[ValidationError]:
    errors = []
    # nome: snake_case, 3-512 chars, lowercase
    # categoria: MARKETING | UTILITY
    # idioma: pt_BR | en_US
    # HEADER text: ≤60, ≤1 var ; HEADER media: kind+url combinam
    # BODY: ≤1024, vars sequenciais (1,2,3 sem pular), sem adjacentes ({{1}}{{2}}), exemplo por variável
    # FOOTER: ≤60, sem variáveis
    # BUTTONS: total ≤10 quick reply OR ≤2 CTA, label ≤25, URL ≤2000 + URL válida, phone E.164
    return errors
```

As constantes (`MEDIA_LIMITS`, `BODY_TEXT_MAX`, `QUICK_REPLY_MAX`, etc.) são duplicadas manualmente em duas fontes:
- Backend: `apps/api/src/shared/application/use_cases/meta_templates/validators.py` (Python)
- Frontend: `apps/web/src/features/templates/validation.ts` (TypeScript)

Mudança em uma exige mudança equivalente na outra. PR review valida o paralelo. Sem geração automática nesta fase para evitar overhead de toolchain.

### Use Cases

**`upload_template_media.py`:**
1. Recebe `(account_id, file_bytes, content_type, declared_kind)`
2. Valida MIME e tamanho contra `MEDIA_LIMITS[declared_kind]`
3. Gera key `accounts/{account_id}/templates/{uuid4}.{ext}`
4. `r2.upload(key, file_bytes, content_type)`
5. Retorna `{media_url, media_object_key, media_kind, sha256, size}`

**`create_template.py`:**
1. Valida payload via `validate_template_payload`
2. Se houver mídia: baixa do R2, abre resumable session na Meta, sobe bytes, recebe `handle`, injeta em `components[HEADER].example.header_handle`
3. `POST /{waba_id}/message_templates` (Meta API)
4. Em sucesso: INSERT em `meta_templates` (status `PENDING`)
5. Em falha pós-upload: `r2.delete(media_object_key)` + raise

**`list_templates.py`:**
1. SELECT da tabela
2. Se houver `PENDING`: chama Meta `GET /{waba_id}/message_templates`, atualiza status no banco
3. Atualiza `last_synced_at`
4. Retorna lista

**`delete_template.py`:**
1. Verifica `FollowupStep WHERE meta_template_name = template.name`
2. Se em uso: raise `MetaTemplateInUse(flows=[...])` (router converte em 409)
3. Senão: `meta_client.delete_template` → `r2.delete(media_object_key)` → `DELETE FROM meta_templates`

### Endpoints HTTP

```
POST   /admin/meta-templates/upload-media   → 201 { media_url, media_object_key, media_kind, sha256, size }
POST   /admin/meta-templates                → 201 MetaTemplate (aceita media_* no body)
GET    /admin/meta-templates                → [MetaTemplate] (com sync de PENDING)
DELETE /admin/meta-templates/{id}           → 204 | 409 (em uso) | 404
```

### `ChatNexoClient.send_template` — Atualização

```python
async def send_template(
    self,
    *, phone: str, template_name: str, language: str,
    variables: list[str],
    header_link: str | None = None,
    header_kind: Literal["image", "video", "document"] | None = None,
) -> SendResult:
    payload = {
        "type": "template",
        "phone": phone,
        "template_name": template_name,
        "language": language,
        "variables": variables,
    }
    if header_link and header_kind:
        payload["header"] = {"type": header_kind, "link": header_link}
    return await self._post("/messages/template", json=payload)
```

### `DispatchFollowupStep` — Atualização

```python
async def execute(self, *, enrollment_step_id: UUID) -> None:
    step = await self._steps.get_with_template(enrollment_step_id)
    template = step.template

    header_link = template.media_url if template.media_url else None
    header_kind = template.media_kind.lower() if template.media_kind else None

    await self._chatnexo.send_template(
        phone=step.contact.phone,
        template_name=template.name,
        language=template.language,
        variables=step.resolved_variables,
        header_link=header_link,
        header_kind=header_kind,
    )
```

---

## Frontend

### Estrutura

```
apps/web/src/features/templates/
├── components/
│   ├── TemplateForm.tsx                    ← ATUALIZADO
│   ├── MediaUploadField.tsx                ← NOVO (drag-and-drop + preview)
│   ├── ButtonsEditor.tsx                   ← NOVO (extraído do form)
│   ├── VariablesEditor.tsx                 ← NOVO (detecta vars + exemplos)
│   ├── TemplatePreview.tsx                 ← ATUALIZADO (preview com mídia)
│   ├── TemplateListItem.tsx                ← ATUALIZADO (badge de status)
│   └── DeleteConfirmDialog.tsx             ← NOVO (com lista de flows em uso)
├── hooks/
│   └── useTemplateValidation.ts            ← NOVO (validação inline)
├── validation.ts                           ← NOVO (regras Meta — mirror do backend)
└── types.ts                                ← ATUALIZADO
```

### `MediaUploadField`

Props:
```ts
interface MediaUploadFieldProps {
  kind: 'IMAGE' | 'VIDEO' | 'DOCUMENT';
  value: UploadedMedia | null;
  onChange: (media: UploadedMedia | null) => void;
}

interface UploadedMedia {
  url: string;
  objectKey: string;
  kind: 'IMAGE' | 'VIDEO' | 'DOCUMENT';
  size: number;
  sha256: string;
  fileName: string;
}
```

Estados visuais: `idle` (drop zone) → `validating` → `uploading` (progresso) → `success` (preview com nome + tamanho + ações Trocar/Remover) → `error` (toast + retry).

Trocar arquivo dispara `DELETE` do objeto antigo no R2 antes de subir o novo.

### Validações Inline (`validation.ts`)

Constantes espelhadas do backend e funções puras:

```ts
export const HEADER_TEXT_MAX = 60;
export const BODY_TEXT_MAX = 1024;
export const FOOTER_MAX = 60;
export const BUTTON_LABEL_MAX = 25;
export const BUTTON_URL_MAX = 2000;
export const QUICK_REPLY_MAX = 10;
export const CTA_MAX = 2;

export const MEDIA_LIMITS = {
  IMAGE:    { mimes: ['image/jpeg', 'image/png'], maxBytes: 5  * 1024 * 1024 },
  VIDEO:    { mimes: ['video/mp4'],                maxBytes: 16 * 1024 * 1024 },
  DOCUMENT: { mimes: ['application/pdf'],          maxBytes: 100 * 1024 * 1024 },
};

export function validateName(name: string): string | null { ... }
export function detectVariables(text: string): number[] { ... }
export function validateBody(text: string, variableExamples: Record<string, string>): ValidationError[] { ... }
export function validateButtons(buttons: TemplateButton[]): ValidationError[] { ... }
```

### Form (TemplateForm.tsx)

- Categoria: select com **`MARKETING`** e **`UTILITY`** apenas
- Header: `NONE | TEXT | IMAGE | VIDEO | DOCUMENT`. Quando media, renderiza `MediaUploadField`.
- Body: textarea com contador `N/1024`; vermelho ao passar. Lista de variáveis detectadas em `VariablesEditor` com input por variável (exemplo).
- Footer: textarea com contador `N/60`; bloqueia variáveis.
- Botões: `ButtonsEditor` lista botões; "+ Adicionar" abre menu (`QUICK_REPLY | URL | PHONE_NUMBER`). Lógica de limite: 10 quick reply OU 2 CTA, sem mistura livre.
- Submit desabilitado se `validateAll()` retorna erros.

### Listagem `/templates`

- Badge de status: PENDING (amarelo), APPROVED (verde), REJECTED (vermelho com tooltip do motivo)
- Coluna com thumbnail da mídia (se houver `media_url`)
- Ação "Excluir": abre `DeleteConfirmDialog`. Em 409, mostra lista clicável dos flows que usam.
- Ao montar, dispara `GET /admin/meta-templates` que faz sync server-side dos PENDING.

### API Client (`apps/web/src/lib/api.ts`)

```ts
uploadTemplateMedia(file: File, kind: MediaKind, onProgress?: (pct: number) => void): Promise<UploadedMedia>
createMetaTemplate(payload: CreateTemplateDto): Promise<MetaTemplate>
deleteMetaTemplate(id: string): Promise<void>
```

`uploadTemplateMedia` usa `FormData` + `XMLHttpRequest` (pra ter `onProgress`).

---

## Validações (regras Meta consolidadas)

| Campo | Regra |
|---|---|
| Nome | `^[a-z0-9_]{3,512}$` |
| Categoria | `MARKETING` ou `UTILITY` |
| Idioma | Lista fixa (pt_BR, en_US, ...) |
| Header text | ≤60 chars, ≤1 variável (`{{1}}` apenas) |
| Header mídia | tipo bate com `media_kind`; tamanho ≤ `MEDIA_LIMITS[kind]` |
| Body | ≤1024 chars; variáveis posicionais sequenciais (`{{1}}` antes de `{{2}}`); sem adjacentes (`{{1}}{{2}}`); exemplo obrigatório por variável |
| Footer | ≤60 chars; sem variáveis |
| Botão (geral) | label ≤25 chars |
| Botão URL | URL válida ≤2000 chars |
| Botão PHONE | E.164: `^\+\d{8,15}$` |
| Botão QUICK_REPLY | Sem fields adicionais |
| Total botões | ≤10 botões no total. CTA (URL/PHONE) limitados a ≤2. Pode misturar QUICK_REPLY com CTA respeitando esses limites. Implementação segue regras Meta WhatsApp Cloud API v19.0 — função `validate_buttons` é a fonte da verdade |
| Variáveis sem exemplo | Bloqueia submit |
| Mídia tamanho | IMAGE ≤5MB, VIDEO ≤16MB, DOCUMENT ≤100MB |
| Mídia formato | IMAGE jpg/png; VIDEO mp4; DOCUMENT pdf |

---

## Tratamento de Erros e Edge Cases

| Cenário | Tratamento |
|---|---|
| Upload R2 OK, Meta create falha | `r2.delete(object_key)` + 502 |
| Resumable upload Meta falha | Mantém R2 (válido), 502 com `META_API_ERROR` |
| Template REJECTED na criação | Salva `rejection_reason`, status REJECTED |
| Trocar mídia no form | DELETE objeto antigo no R2 antes de subir o novo |
| Excluir template em uso | 409 com `{ flows: [{id, name, step_position}] }` |
| Excluir + falha em DELETE Meta | Aborta antes de tocar R2/DB; 502 |
| Excluir + falha em DELETE R2 | Loga warning, registra `audit_event` `r2_cleanup_pending`, prossegue |
| Sync APPROVED → REJECTED retroativo | Atualiza status + `rejection_reason` + warning estruturado |
| Race em GET /meta-templates | Idempotente; pior caso 2 chamadas Meta |
| Variável sem exemplo no submit | 400 com `META_TEMPLATE_VALIDATION_FAILED` |
| Nome duplicado na Meta (criado fora) | Mapeia código `2388023` → `META_TEMPLATE_NAME_DUPLICATE` |
| Upload >100MB | Frontend bloqueia; backend `max_request_size=120MB` |

### Códigos de erro estruturados

```
META_TEMPLATE_VALIDATION_FAILED
META_TEMPLATE_NAME_DUPLICATE
META_TEMPLATE_IN_USE
MEDIA_UPLOAD_FAILED
MEDIA_TYPE_INVALID
MEDIA_SIZE_EXCEEDED
META_API_ERROR
R2_UPLOAD_FAILED
R2_DELETE_FAILED
```

Formato:
```json
{
  "error": {
    "code": "META_TEMPLATE_VALIDATION_FAILED",
    "message": "Template tem erros de validação",
    "details": [
      {"field": "components[1].text", "code": "BODY_TEXT_TOO_LONG", "message": "Body excede 1024 caracteres"}
    ]
  }
}
```

---

## Observabilidade

### Métricas Prometheus (`shared/adapters/observability/metrics.py`)

```
meta_template_create_total{result="success|rejected|error"}
meta_template_create_duration_seconds
meta_template_media_upload_total{kind, result}
meta_template_media_upload_bytes_total{kind}
meta_template_sync_total{result}
meta_template_delete_total{result}
```

### Logs estruturados

| Ponto | Campos |
|---|---|
| Upload R2 start | `kind`, `size`, `sha256`, `account_id` |
| Upload R2 done | `kind`, `size`, `duration_ms`, `object_key` |
| Resumable upload Meta | `app_id`, `session_id`, `handle`, `duration_ms` |
| Create template Meta | `template_name`, `meta_template_id`, `status`, `duration_ms` |
| Sync template | `account_id`, `pending_count`, `resolved_count` |
| Delete template | `template_id`, `meta_status`, `r2_status`, `db_status` |

---

## Testes

### Unit (`apps/api/tests/unit/`)

```
meta_templates/
  test_validators.py            # ≥30 casos cobrindo cada regra Meta
  test_create_template.py       # use case com mocks
  test_delete_template.py       # bloqueio em uso, ordem de cleanup
  test_list_templates.py        # sync de PENDING
storage/
  test_r2.py                    # boto3 mockado: upload/delete/head + sha256
meta/
  test_template_client.py       # httpx mockado: resumable upload, create, delete
followup/
  test_dispatch_with_media.py   # header_link/header_kind passados ao ChatNexo
chatnexo/
  test_send_template_with_header.py
```

### Integration (`apps/api/tests/integration/`)

```
test_meta_templates_flow.py:
  - upload_media → create → list (sync PENDING) → delete fluxo end-to-end
  - delete bloqueado quando template em uso por flow → 409
  - rollback: meta create falha → R2 limpo (sem objeto órfão)
  - exclusão com falha em DELETE R2 → DB limpo + audit_event criado
```

### Frontend (manual + smoke)

- Upload de cada tipo (jpg, png, mp4, pdf)
- Validações inline disparam corretamente em cada campo
- Drag-and-drop e click ambos funcionam
- Estado de progresso visível durante upload
- 409 ao excluir mostra os flows em uso e link clicável
- Submit desabilitado enquanto há erro

---

## Variáveis de Ambiente Novas

Adicionar em `apps/api/.env.example` (sem valor) e `apps/api/.env.local` (com valor real):

```
# Cloudflare R2 (template media storage)
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_BASE_URL=

# Meta (resumable upload)
META_APP_ID=
```

`META_API_KEY`, `META_WABA_ID` já existem.

---

## Migração de Dados Existentes

A migration converte registros pré-existentes:
- `approved=true` → `status='APPROVED'`
- `approved=false` → `status='PENDING'`
- `category` default `'UTILITY'`
- `components` default `'[]'::jsonb` (vazio)

Após primeiro `GET /admin/meta-templates`, o sync polling preenche automaticamente os componentes via Meta API. Templates antigos sem mídia continuam funcionando normalmente.

---

## Fora de Escopo (decidido explicitamente)

- ❌ Editar template (sem versionamento)
- ❌ Webhook Meta (sync é polling sob demanda)
- ❌ Reuso de mídia entre templates (cada template tem sua própria URL R2)
- ❌ Categoria `AUTHENTICATION`
- ❌ Variáveis nomeadas (`{{nome}}` etc.) — só posicionais
- ❌ Soft delete em `meta_templates`
- ❌ Garbage collection automático de objetos órfãos no R2 (manual via audit_event)
- ❌ Suporte a outros formatos de mídia além dos listados (gif, webp, mov, docx, etc.)

---

## Critério de Aceitação

1. Admin sobe imagem/vídeo/documento via drag-and-drop e vê preview imediato
2. Submeter template com mídia chama Meta API com handle correto e cria template em status PENDING
3. Listagem `/templates` mostra status atualizado após sync sob demanda (PENDING → APPROVED/REJECTED)
4. Disparo de followup com template de mídia entrega mensagem WhatsApp com a mídia visível ao destinatário
5. Tentar excluir template em uso retorna 409 com lista de flows
6. Excluir template não-usado remove Meta + R2 + DB sem deixar órfão
7. Validações inline impedem submit com erro (caracteres, variáveis, botões, mídia)
8. Falha em qualquer etapa pós-upload R2 limpa o objeto do R2
9. Cobertura de testes em `validators.py` ≥80%, em `r2.py` ≥80%
