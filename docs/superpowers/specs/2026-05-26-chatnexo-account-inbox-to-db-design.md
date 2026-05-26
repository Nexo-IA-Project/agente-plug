# Design: Mover `chatnexo_account_id` e `chatnexo_inbox_id` do `.env` para o banco

**Data:** 2026-05-26
**Status:** Aprovado

---

## Problema

Hoje os IDs `CHATNEXO_ACCOUNT_ID` e `CHATNEXO_INBOX_ID` estão fixos no `.env.local`. Para trocar a conta ChatNexo conectada ao sistema, é preciso editar o `.env`, reiniciar containers e fazer deploy — o que torna a troca lenta e cara para algo que muda eventualmente conforme o negócio expande contas/inboxes.

## Objetivo

Tornar a troca de conta ChatNexo uma operação de **dois cliques na UI de Settings** — sem deploy, sem mexer em arquivo de configuração.

## Escopo

**Movem para o banco:**
- `chatnexo_account_id` (int) — ID da conta no ChatNexo
- `chatnexo_inbox_id` (int) — ID da inbox dentro da conta

**Permanecem no `.env` como fallback:**
- `CHATNEXO_ACCOUNT_ID=1`
- `CHATNEXO_INBOX_ID=1`

Quando o valor existe no banco (`accounts.settings.integration.chatnexo_account_id`), prevalece sobre o `.env`. Quando não existe (deploy novo sem configuração), o sistema usa o `.env`.

---

## Mudanças

### 1. Domain (`shared/domain/entities/account_config.py`)

Adicionar os 2 campos em `IntegrationConfig`:

```python
@dataclass(frozen=True)
class IntegrationConfig:
    chatnexo_base_url: str
    chatnexo_api_key: str
    chatnexo_account_id: int      # ← novo
    chatnexo_inbox_id: int        # ← novo
    hubla_webhook_secret: str
    ...
```

E em `AccountConfigPatch` como opcionais:

```python
@dataclass
class AccountConfigPatch:
    ...
    chatnexo_account_id: int | None = field(default=None)
    chatnexo_inbox_id: int | None = field(default=None)
```

### 2. Repositório (`shared/adapters/db/repositories/account_config_repo.py`)

Em `get()`, carregar do JSONB com fallback para `.env` (mesmo padrão de `cademi_max_retries` que existia antes da remoção):

```python
chatnexo_account_id=int(i.get("chatnexo_account_id", s.chatnexo_account_id)),
chatnexo_inbox_id=int(i.get("chatnexo_inbox_id", s.chatnexo_inbox_id)),
```

Em `update()`, persistir como int direto (sem encriptação):

```python
if patch.chatnexo_account_id is not None:
    i["chatnexo_account_id"] = patch.chatnexo_account_id
if patch.chatnexo_inbox_id is not None:
    i["chatnexo_inbox_id"] = patch.chatnexo_inbox_id
```

**Não entram em `_SENSITIVE`** — são IDs públicos, não secrets.

### 3. Schemas HTTP (`interface/http/schemas/admin_settings.py`)

Adicionar nos dois schemas:

```python
class AccountSettingsResponse(BaseModel):
    ...
    chatnexo_account_id: int
    chatnexo_inbox_id: int

class AccountSettingsUpdateRequest(BaseModel):
    ...
    chatnexo_account_id: int | None = None
    chatnexo_inbox_id: int | None = None
```

### 4. Router (`interface/http/routers/admin/settings.py`)

`_to_response()`:
```python
chatnexo_account_id=i.chatnexo_account_id,
chatnexo_inbox_id=i.chatnexo_inbox_id,
```

`update_settings_endpoint()` (no `AccountConfigPatch(...)`):
```python
chatnexo_account_id=body.chatnexo_account_id,
chatnexo_inbox_id=body.chatnexo_inbox_id,
```

### 5. Call sites — trocar `get_settings().chatnexo_*` por `account_config.integration.chatnexo_*`

| Arquivo | Linha | Mudança |
|---|---|---|
| `shared/application/purchase_handler.py` | 61 | `get_settings().chatnexo_account_id` → recebido via parâmetro/construtor — usar `self._account_config.integration.chatnexo_account_id` |
| `shared/application/hubla_event_handler.py` | 233 | mesma coisa |
| `shared/application/use_cases/onboarding/dispatch_onboarding_step.py` | 78, 131, 187 | aceitar `chatnexo_account_id: int` como parâmetro no `execute()`; o caller (`scheduled.py`) já carrega `account_config` e passa adiante |

Os handlers (`purchase`, `hubla_event`, `scheduled`) **já carregam `account_config`** — só trocar a leitura.

O use case `DispatchOnboardingStep` é o único que não tem `account_config` direto. Solução: adicionar parâmetro `chatnexo_account_id: int` no `execute()`. Chamador (`scheduled.py:handle_scheduled`) já tem `account_config` carregado, então passa via:
```python
result = await dispatch.execute(
    ...,
    chatnexo_account_id=config.integration.chatnexo_account_id,
)
```

### 6. Frontend — Type (`apps/web/src/features/settings/types.ts`)

```typescript
export interface AccountSettings {
  chatnexo_base_url: string;
  chatnexo_api_key: string;
  chatnexo_account_id: number;    // ← novo
  chatnexo_inbox_id: number;      // ← novo
  ...
}
```

### 7. Frontend — UI (`apps/web/src/features/settings/components/IntegrationSection.tsx`)

Adicionar 2 fields no card ChatNexo (em sequência, após `chatnexo_api_key`):

```typescript
{
  key: "chatnexo_account_id",
  label: "Account ID",
  type: "number",
  description: "ID da conta no ChatNexo",
},
{
  key: "chatnexo_inbox_id",
  label: "Inbox ID",
  type: "number",
  description: "ID da inbox dentro da conta",
},
```

O `InlineEditField` já suporta `type="number"` — animação, validação, save individual já vêm de graça.

---

## Sem migration

Como `accounts.settings` é JSONB, adicionar keys ao dict não requer migration. Sistemas existentes continuam funcionando com fallback para `.env` até alguém editar pela UI.

---

## Critérios de Aceite

- [ ] `GET /admin/settings` retorna `chatnexo_account_id` e `chatnexo_inbox_id`
- [ ] `PUT /admin/settings` aceita e persiste os dois campos
- [ ] Após editar pela UI, novos disparos de mensagem usam o ID novo (sem reiniciar processo)
- [ ] Quando não há valor no banco, `.env` continua sendo usado
- [ ] Page `/settings` mostra os 2 campos no card ChatNexo com edição inline
- [ ] Lint, typecheck e testes passam (`ruff`, `mypy`, `tsc`, `pytest tests/unit`)

---

## Não-objetivos

- Validação custom dos IDs (a Meta/ChatNexo retorna 404 se o ID for inválido — basta logar)
- UI de "trocar conta" como wizard separado (over-engineering — basta editar os 2 campos)
- Migração de dados existentes (deploys existentes continuam usando `.env` até editar pela UI)
