# NexoIA — Account Settings: Página de Configuração de Credenciais

**Data:** 2026-05-06  
**Status:** Aprovado  
**Subsistema:** Admin Dashboard — Settings

---

## Visão Geral

Implementar uma página de configurações no painel web que permita editar as credenciais de integração e parâmetros de comportamento do agente sem acessar manualmente o `.env.local` ou o servidor de produção. As alterações têm efeito imediato — o agente usa os novos valores na próxima mensagem processada, sem reiniciar o processo.

---

## Requisitos Funcionais

| # | Requisito |
|---|-----------|
| RF-S01 | Página `/settings` exibe dois grupos: "Integrações" (Grupo A) e "Comportamento" (Grupo B) |
| RF-S02 | Grupo A contém: ChatNexo (URL + key), Hubla (webhook secret), Cademi (URL + key + max_retries + retry_base_seconds), OpenAI (key), Meta (key) |
| RF-S03 | Grupo B contém: idle_ping_minutes, idle_close_minutes, intent_confidence_threshold, message_buffer_wait_seconds, refund_deadline_days, welcome_d1_delay_hours, loja_express_d1/D3/D5/D7_delay_hours |
| RF-S04 | Campos de API key/secret mostram valor mascarado (`sk-proj-****abcd`); ao clicar "Editar" o campo vira input em branco |
| RF-S05 | Se o usuário não editar um campo sensível (valor contém `****`), o campo não é sobrescrito no banco |
| RF-S06 | Botão "Salvar" por seção dispara `PUT /admin/settings` com apenas os campos alterados |
| RF-S07 | Toasts de sucesso/erro usando `useToast` do projeto |
| RF-S08 | Sidebar exibe item "Configurações" com ícone `settings` |
| RF-S09 | `GET /admin/settings` retorna config atual com campos sensíveis mascarados |
| RF-S10 | Valores ausentes no banco fazem fallback para variável de ambiente correspondente |

## Requisitos Não-Funcionais

| # | Requisito |
|---|-----------|
| RNF-S01 | Campos sensíveis são criptografados com Fernet (INTEGRATION_CREDENTIALS_KEY) antes de persistir no JSONB |
| RNF-S02 | Nenhuma migration nova é necessária — usa `AccountModel.settings: JSONB` já existente |
| RNF-S03 | O endpoint exige JWT admin válido (mesmo `_require_admin` dos outros routers) |
| RNF-S04 | `AccountConfigRepository` segue o padrão `@dataclass` com `session: AsyncSession` dos demais repositórios |
| RNF-S05 | Use cases injetados via construtor (`__init__`), sem acoplamento a implementações concretas |
| RNF-S06 | Adapters ChatNexo/Cademi/OpenAI ganham `from_account_config()` factory ao lado do `from_settings()` existente (OCP) |

---

## Arquitetura

### Camada de Domínio

**`shared/domain/entities/account_config.py`**

```python
@dataclass(frozen=True)
class IntegrationConfig:
    chatnexo_base_url: str
    chatnexo_api_key: str
    hubla_webhook_secret: str
    cademi_api_url: str
    cademi_api_key: str
    cademi_max_retries: int
    cademi_retry_base_seconds: float
    openai_api_key: str
    meta_api_key: str

@dataclass(frozen=True)
class BehaviorConfig:
    idle_ping_minutes: int
    idle_close_minutes: int
    intent_confidence_threshold: float
    message_buffer_wait_seconds: int
    refund_deadline_days: int
    welcome_d1_delay_hours: int
    loja_express_d1_delay_hours: int
    loja_express_d3_delay_hours: int
    loja_express_d5_delay_hours: int
    loja_express_d7_delay_hours: int

@dataclass(frozen=True)
class AccountConfig:
    integration: IntegrationConfig
    behavior: BehaviorConfig

@dataclass
class AccountConfigPatch:
    # Todos os campos são Optional — só os enviados são atualizados
    chatnexo_base_url: str | None = None
    chatnexo_api_key: str | None = None
    hubla_webhook_secret: str | None = None
    cademi_api_url: str | None = None
    cademi_api_key: str | None = None
    cademi_max_retries: int | None = None
    cademi_retry_base_seconds: float | None = None
    openai_api_key: str | None = None
    meta_api_key: str | None = None
    idle_ping_minutes: int | None = None
    idle_close_minutes: int | None = None
    intent_confidence_threshold: float | None = None
    message_buffer_wait_seconds: int | None = None
    refund_deadline_days: int | None = None
    welcome_d1_delay_hours: int | None = None
    loja_express_d1_delay_hours: int | None = None
    loja_express_d3_delay_hours: int | None = None
    loja_express_d5_delay_hours: int | None = None
    loja_express_d7_delay_hours: int | None = None
```

Não há Port (Protocol) para `AccountConfig` — não é uma fronteira que precisa ser mockada no domínio do agente. É uma entidade de configuração, não de negócio.

---

### Camada de Adapter — Repositório

**`shared/adapters/db/repositories/account_config_repo.py`**

Segue o padrão `@dataclass` com `session: AsyncSession`. Responsável por:

1. **`get(account_id)`**: busca `AccountModel`, lê `settings` JSONB, descriptografa campos sensíveis, preenche ausentes com valores de `Settings` (env vars).
2. **`update(account_id, patch)`**: criptografa campos sensíveis do patch, faz `deep_merge` no JSONB existente, salva via `session.flush()`.

**Schema JSONB interno** (dentro de `AccountModel.settings`):
```json
{
  "integration": {
    "chatnexo_base_url": "http://...",
    "chatnexo_api_key": "gAAAAAB...",
    "openai_api_key": "gAAAAAB...",
    ...
  },
  "behavior": {
    "idle_ping_minutes": 30,
    ...
  }
}
```

**Campos sensíveis criptografados** (Fernet):
- `chatnexo_api_key`
- `hubla_webhook_secret`
- `cademi_api_key`
- `openai_api_key`
- `meta_api_key`

**Mascaramento na API** (função utilitária):
```python
def _mask(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return value[:8] + "****"
```

**Regra do patch**: se valor recebido contém `"****"`, campo é ignorado (não sobrescreve).

---

### Camada de Application — Use Cases

**`shared/application/use_cases/admin/get_account_config.py`**

```python
class GetAccountConfig:
    def __init__(self, repo: AccountConfigRepository) -> None:
        self._repo = repo

    async def execute(self, account_id: int) -> AccountConfig:
        return await self._repo.get(account_id=account_id)
```

**`shared/application/use_cases/admin/update_account_config.py`**

```python
class UpdateAccountConfig:
    def __init__(self, repo: AccountConfigRepository) -> None:
        self._repo = repo

    async def execute(self, account_id: int, patch: AccountConfigPatch) -> AccountConfig:
        self._validate(patch)
        return await self._repo.update(account_id=account_id, patch=patch)

    def _validate(self, patch: AccountConfigPatch) -> None:
        if patch.intent_confidence_threshold is not None:
            if not 0.0 <= patch.intent_confidence_threshold <= 1.0:
                raise ValueError("intent_confidence_threshold deve estar entre 0 e 1")
        if patch.cademi_max_retries is not None and patch.cademi_max_retries < 0:
            raise ValueError("cademi_max_retries não pode ser negativo")
```

---

### Camada de Interface — Router HTTP

**`interface/http/routers/admin/settings.py`**

```
GET  /admin/settings   → AccountConfigResponse  (campos sensíveis mascarados)
PUT  /admin/settings   → AccountConfigResponse  (campos sensíveis mascarados)
```

Ambos usam `Depends(_require_admin)` do `api_tokens.py` — extraído para `interface/http/deps/admin_auth.py` para ser compartilhado (sem duplicação).

**Schemas Pydantic** em `interface/http/schemas/admin_settings.py`:

- `AccountConfigResponse` — flat (sem aninhamento de IntegrationConfig/BehaviorConfig) para facilitar serialização
- `AccountConfigUpdateRequest` — todos os campos `Optional[str | int | float]`

---

### Mudança nos Adapters (OCP)

`ChatNexoClient` e `CademiClient` ganham factory alternativa:

```python
# shared/adapters/chatnexo/client.py
@classmethod
def from_account_config(cls, config: AccountConfig) -> ChatNexoClient:
    return cls(http=httpx.AsyncClient(
        base_url=config.integration.chatnexo_base_url,
        headers={"X-Api-Key": config.integration.chatnexo_api_key},
        timeout=httpx.Timeout(10.0, connect=3.0),
    ))
```

O `from_settings()` existente não é removido — continua funcionando para testes e contextos sem DB.

---

### Mudança no Worker

**`interface/worker/handlers/message.py`**

Dentro do `session_scope()` já existente, antes de criar adapters:

```python
async with session_scope() as session:
    fernet = Fernet(settings.integration_credentials_key)
    config_repo = AccountConfigRepository(session, fernet)
    account_config = await config_repo.get(account_id=account_id)

    chatnexo = ChatNexoClient.from_account_config(account_config)
    cademi = CademiClient.from_account_config(account_config)
    openai_client = AsyncOpenAI(api_key=account_config.integration.openai_api_key)
    # ... restante igual
```

---

### Frontend

**Estrutura de arquivos:**

```
apps/web/src/
  features/settings/
    types.ts
    components/
      IntegrationSection.tsx
      BehaviorSection.tsx
  app/(admin)/settings/
    page.tsx
```

**`types.ts`** — espelha `AccountConfigResponse` e `AccountConfigUpdateRequest` do backend.

**`IntegrationSection.tsx`** — renderiza cada campo de integração. Campos sensíveis:
- Exibem valor mascarado em texto cinza
- Botão "Editar" ao lado
- Ao clicar: campo vira `<input type="password">` em branco
- Botão "Salvar seção" chama `PUT /admin/settings` com só os campos modificados

**`BehaviorSection.tsx`** — inputs numéricos simples (sem mascaramento). Salva da mesma forma.

**`Sidebar.tsx`** — novo item na `NAV_ITEMS`:
```ts
{ label: "Configurações", href: "/settings", icon: "settings" }
```

**`apps/web/src/lib/api.ts`** — duas funções novas:
```ts
export async function getSettings(): Promise<AccountConfigResponse>
export async function updateSettings(patch: AccountConfigUpdateRequest): Promise<AccountConfigResponse>
```

---

## Fluxo de Dados

```
[Frontend PUT /admin/settings]
       ↓
[Router: _require_admin → AccountConfigUpdateRequest]
       ↓
[UpdateAccountConfig.execute(account_id, patch)]
       ↓
[AccountConfigRepository.update → criptografa sensíveis → JSONB merge → flush]
       ↓
[Retorna AccountConfig → Router mascara → AccountConfigResponse]
       ↓
[Frontend atualiza UI com novos valores mascarados]

[Worker processa próxima mensagem]
       ↓
[AccountConfigRepository.get → descriptografa → overlay com env vars]
       ↓
[ChatNexoClient.from_account_config(config)]
       ↓
[Agente usa novas credenciais imediatamente]
```

---

## Arquivos a Criar / Modificar

### Criar
| Arquivo | Descrição |
|---|---|
| `shared/domain/entities/account_config.py` | Entidade + Patch dataclasses |
| `shared/adapters/db/repositories/account_config_repo.py` | Repositório com criptografia |
| `shared/application/use_cases/admin/get_account_config.py` | Use case leitura |
| `shared/application/use_cases/admin/update_account_config.py` | Use case escrita + validação |
| `interface/http/routers/admin/settings.py` | Router GET/PUT /admin/settings |
| `interface/http/schemas/admin_settings.py` | Pydantic schemas da API |
| `interface/http/deps/admin_auth.py` | `_require_admin` extraído (DRY) |
| `apps/web/src/features/settings/types.ts` | Tipos TypeScript |
| `apps/web/src/features/settings/components/IntegrationSection.tsx` | UI grupo A |
| `apps/web/src/features/settings/components/BehaviorSection.tsx` | UI grupo B |
| `apps/web/src/app/(admin)/settings/page.tsx` | Página /settings |

### Modificar
| Arquivo | Mudança |
|---|---|
| `shared/adapters/chatnexo/client.py` | Adicionar `from_account_config()` |
| `shared/adapters/cademi/client.py` | Adicionar `from_account_config()` |
| `interface/worker/handlers/message.py` | Carregar AccountConfig do DB |
| `interface/http/routers/admin/api_tokens.py` | Importar `_require_admin` de `admin_auth.py` |
| `apps/api/src/main.py` | Registrar router de settings |
| `apps/web/src/lib/api.ts` | Adicionar `getSettings`, `updateSettings` |
| `apps/web/src/shared/components/layout/Sidebar.tsx` | Adicionar item "Configurações" |
| `docs/superpowers/INDEX.md` | Atualizar tabela |

### Não precisa
- Nenhuma migration Alembic (`AccountModel.settings` JSONB já existe)
- Nenhum novo Port (Protocol) de domínio

---

## Tratamento de Erros

| Cenário | Comportamento |
|---|---|
| `AccountModel` não encontrado para o `account_id` | Retorna config com todos os valores de env vars (sem erro) |
| JSONB corrompido / campo com tipo errado | Log de warning, usa valor default de env var para aquele campo |
| Fernet falha ao descriptografar (key rotacionada) | Campo retorna string vazia, log de erro |
| Valor de patch inválido (threshold fora de 0-1) | HTTP 422 com mensagem descritiva |
| Campo de API key com `****` no valor | Campo ignorado silenciosamente (não sobrescreve) |

---

## Testes

- **Unit**: `TestUpdateAccountConfig` — validação de ranges; `TestAccountConfigRepository` com DB fake (AccountModel mockado)
- **Unit**: mascaramento de campos sensíveis em `_mask()`
- **Unit**: overlay com env vars quando JSONB está vazio
- **Integration**: `GET /admin/settings` → `PUT /admin/settings` → `GET /admin/settings` verifica persistência
