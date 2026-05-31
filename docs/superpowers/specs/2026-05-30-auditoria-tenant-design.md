# Sistema de Auditoria por Tenant — design

**Data:** 2026-05-30  
**Status:** Aprovado.

## Contexto

O painel admin não registra quem fez o quê. A tabela `audit_events` já existe no banco mas está praticamente sem uso (apenas o handler de resync escreve nela). Faltam os campos de IP/geolocalização e qualquer endpoint de consulta. O objetivo é capturar automaticamente todas as **ações de escrita** (create/edit/delete/login/logout) feitas no painel de cada tenant, exibi-las em uma página de Auditoria acessível somente ao `role=admin` do tenant.

## Escopo

- **Tenant-scoped:** cada conta vê apenas seus próprios eventos (`account_id` em todo acesso)
- **Visibilidade:** somente `role=admin` dentro do tenant (`audit.view` em `ADMIN_ONLY_KEYS`)
- **Captura:** apenas ações de escrita (POST/PUT/PATCH/DELETE) com label mapeado — leituras ignoradas
- **Geolocalização:** cidade + país via `ip-api.com` (gratuito, sem chave), assíncrona (BackgroundTask)
- **Sem painel de plataforma:** auditoria cross-tenant fica para fase futura

## Arquitetura — Clean Architecture

```
domain/
  entities/audit_event.py          ← entidade expandida (+ ip, geo, user_name)
  ports/audit_repository.py        ← Protocol: save() + paginate()

shared/adapters/
  geo/
    port.py                        ← Protocol GeoService
    ip_api.py                      ← implementação ip-api.com
  db/repositories/
    audit_repo.py                  ← SqlAuditRepository

application/use_cases/admin/
  list_audit_events.py             ← ListAuditEventsUseCase

interface/http/
  middleware/
    audit.py                       ← AuditMiddleware
  routers/admin/
    audit.py                       ← router GET /admin/audit-events
```

## Migration

Nova migration Alembic sobre `audit_events`:

```sql
ALTER TABLE audit_events ALTER COLUMN actor TYPE VARCHAR(120);
ALTER TABLE audit_events ADD COLUMN ip_address  VARCHAR(45);
ALTER TABLE audit_events ADD COLUMN geo_city    VARCHAR(100);
ALTER TABLE audit_events ADD COLUMN geo_country VARCHAR(100);
ALTER TABLE audit_events ADD COLUMN geo_region  VARCHAR(100);
ALTER TABLE audit_events ADD COLUMN user_id     UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE audit_events ADD COLUMN user_name   VARCHAR(120);
```

Índice adicional: `(account_id, created_at DESC)` já existe. Adicionar `(account_id, user_id)` para filtro por usuário.

## Entidade `AuditEvent` — expansão

```python
@dataclass(slots=True)
class AuditEvent:
    id: UUID
    account_id: UUID
    actor: str          # email ou label (mantém compat)
    user_id: UUID | None
    user_name: str | None
    action: str         # label legível: "Criou usuário"
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    geo_city: str | None
    geo_country: str | None
    geo_region: str | None
    metadata: dict[str, Any]
    correlation_id: str | None
    created_at: datetime | None
```

## Port `AuditRepository`

```python
class AuditRepository(Protocol):
    async def save(self, event: AuditEvent) -> None: ...
    async def update_geo(
        self, event_id: UUID, *, city: str, country: str, region: str
    ) -> None: ...
    async def paginate(
        self,
        account_id: UUID,
        *,
        user_id: UUID | None,
        action: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        page_size: int,
    ) -> tuple[list[AuditEvent], int]: ...
```

## Port `GeoService`

```python
class GeoService(Protocol):
    async def lookup(self, ip: str) -> GeoResult | None: ...

@dataclass
class GeoResult:
    city: str
    country: str
    region: str
```

`IpApiGeoService` implementa consultando `http://ip-api.com/json/{ip}?fields=status,city,country,regionName`. Timeout de 3s; em caso de erro retorna `None` silenciosamente (auditoria não pode derrubar request).

## AuditMiddleware

```
POST/PUT/PATCH/DELETE  /admin/*
  ↓
call_next(request)
  ↓  (durante a rota, AdminAuth seta request.state.audit_ctx)
resposta pronta
  ↓
lê request.state.audit_ctx  → {account_id, user_id, user_name}
resolve label por (method, path) no ACTION_MAP
extrai IP de CF-Connecting-IP → X-Forwarded-For → client host
salva AuditEventModel (sem geo ainda)
add BackgroundTask: IpApiGeoService.lookup(ip) → audit_repo.update_geo(event_id)
```

Requests sem `audit_ctx` (não autenticados, 401/403 antes da rota) **não** geram evento — falha de auth não é ação do usuário.

### ACTION_MAP (método × path regex → label + resource_type)

| Método | Path regex | Label | resource_type |
|--------|-----------|-------|---------------|
| POST | `/admin/auth/login` | Login | auth |
| POST | `/admin/auth/logout` | Logout | auth |
| POST | `/admin/users` | Criou usuário | user |
| PUT | `/admin/users/[^/]+$` | Editou usuário | user |
| DELETE | `/admin/users/[^/]+$` | Excluiu usuário | user |
| POST | `/admin/users/[^/]+/reset-password` | Resetou senha de usuário | user |
| PUT | `/admin/me/password` | Alterou própria senha | user |
| PUT | `/admin/me/avatar` | Alterou avatar | user |
| PUT | `/admin/me` | Editou perfil próprio | user |
| POST | `/admin/products` | Criou produto | product |
| PUT | `/admin/products/[^/]+$` | Editou produto | product |
| DELETE | `/admin/products/[^/]+$` | Excluiu produto | product |
| POST | `/admin/documents/upload` | Enviou documento KB | document |
| DELETE | `/admin/documents/[^/]+$` | Excluiu documento KB | document |
| POST | `/admin/followup/flows` | Criou flow de follow-up | flow |
| PUT | `/admin/followup/flows/[^/]+$` | Editou flow de follow-up | flow |
| DELETE | `/admin/followup/flows/[^/]+$` | Excluiu flow de follow-up | flow |
| POST | `/admin/followup/flows/[^/]+/steps` | Adicionou step ao flow | flow_step |
| PUT | `/admin/followup/flows/[^/]+/steps/[^/]+$` | Editou step do flow | flow_step |
| DELETE | `/admin/followup/flows/[^/]+/steps/[^/]+$` | Excluiu step do flow | flow_step |
| PATCH | `/admin/followup/flows/[^/]+/steps/reorder` | Reordenou steps do flow | flow_step |
| POST | `/admin/meta-templates` | Criou template Meta | meta_template |
| DELETE | `/admin/meta-templates/[^/]+$` | Excluiu template Meta | meta_template |
| PUT | `/admin/settings` | Editou configurações | settings |
| PUT | `/admin/smtp-config` | Editou configuração SMTP | settings |
| POST | `/admin/api-tokens` | Criou token de API | api_token |
| DELETE | `/admin/api-tokens/[^/]+$` | Revogou token de API | api_token |
| POST | `/admin/profiles` | Criou perfil | profile |
| PUT | `/admin/profiles/[^/]+$` | Editou perfil | profile |
| DELETE | `/admin/profiles/[^/]+$` | Excluiu perfil | profile |
| POST | `/admin/dlq/[^/]+/requeue` | Reprocessou job DLQ | dlq |
| POST | `/admin/dlq/requeue-all` | Reprocessou todos os jobs DLQ | dlq |
| DELETE | `/admin/dlq/[^/]+$` | Excluiu job DLQ | dlq |

Paths que não casam com nenhuma entrada são silenciosamente ignorados.

## Endpoint `GET /admin/audit-events`

```
GET /admin/audit-events
  query params:
    page: int = 1
    page_size: int = 25 (max 100)
    user_id: UUID | None
    action: str | None        (label exato)
    date_from: datetime | None
    date_to: datetime | None
  guard: require_permission("audit.view")
  response: AuditEventListResponse
    items: [AuditEventResponse]
    total: int
    page: int
    page_size: int
```

`AuditEventResponse`:
```
id, user_name, action, resource_type, resource_id,
ip_address, geo_city, geo_country, geo_region,
created_at
```

Router injeta `account_id` do JWT (`auth.account_id`) — nunca do body.

## Permissão

```python
_p("audit", "view", "Ver auditoria")
```

Entra em `PERMISSION_CATALOG` e em `ADMIN_ONLY_KEYS`. Operadores não têm acesso.

## Frontend

### Sidebar — novo grupo "Administração"

Visível apenas quando `can("audit.view")` (equivalente a `role=admin` na prática). Posição: após grupo "Configurações". Contém somente "Auditoria" nesta fase; estruturado como grupo expansível para receber outros itens futuros.

### Página `/administracao/auditoria`

```
apps/web/src/app/(admin)/administracao/auditoria/page.tsx
```

- Guard `<RequirePermission perm="audit.view">`
- Tabela com colunas: **Usuário**, **Ação**, **IP · Localidade**, **Data e Hora**
- **Localidade** = `geo_city, geo_country` quando disponível, IP puro como fallback
- Filtros no topo: seletor de usuário (lista de nomes do tenant), seletor de ação (lista de labels únicos), date-range (date_from / date_to)
- Paginação padrão do projeto (mesma estrutura de `/leads`)
- Sem drawer de detalhe — todas as informações cabem na linha

### Tipos TypeScript

```ts
// features/audit/types.ts
interface AuditEventItem {
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

interface AuditEventListResponse {
  items: AuditEventItem[];
  total: number;
  page: number;
  page_size: number;
}
```

### Função `listAuditEvents` em `lib/api.ts`

```ts
listAuditEvents(params: {
  page?: number;
  page_size?: number;
  user_id?: string;
  action?: string;
  date_from?: string;
  date_to?: string;
}) → Promise<AuditEventListResponse>
```

## Não-objetivos

- Auditoria cross-tenant (plataforma) — fase futura
- Export CSV da auditoria — fase futura
- Captura de ações de leitura (GET)
- Retenção/expiração automática de logs
- Geolocalização em produção atrás de IP privado (retorna `None` silenciosamente)
