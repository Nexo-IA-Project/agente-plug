# ChatNexo account_id / inbox_id no Banco Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mover `chatnexo_account_id` e `chatnexo_inbox_id` do `.env.local` para o banco (`accounts.settings.integration` JSONB), expor via UI de Settings, manter `.env` como fallback.

**Architecture:** Adicionar 2 campos em `IntegrationConfig`/`AccountConfigPatch`, persistir no JSONB existente (sem migration), trocar `get_settings().chatnexo_account_id` por leitura via `account_config` nos call sites, expor via `InlineEditField` no card ChatNexo da página Settings.

**Tech Stack:** Python 3.11 + FastAPI + SQLAlchemy 2 (async) + Pydantic; Next.js 15 + TypeScript + react-hook-form (UI já tem `InlineEditField` pronto).

**Spec:** `docs/superpowers/specs/2026-05-26-chatnexo-account-inbox-to-db-design.md`

---

## Task 1: Entidades de domínio ganham `chatnexo_account_id` e `chatnexo_inbox_id`

**Files:**
- Modify: `apps/api/src/shared/domain/entities/account_config.py`

- [ ] **Step 1: Adicionar os 2 campos em `IntegrationConfig`**

Em `apps/api/src/shared/domain/entities/account_config.py`, no `@dataclass(frozen=True) class IntegrationConfig`, adicionar após `chatnexo_api_key: str`:

```python
@dataclass(frozen=True)
class IntegrationConfig:
    chatnexo_base_url: str
    chatnexo_api_key: str
    chatnexo_account_id: int
    chatnexo_inbox_id: int
    hubla_webhook_secret: str
    openai_api_key: str
    meta_api_key: str
    meta_waba_id: str
    meta_app_id: str
    chatnexo_agents: list[ChatNexoAgent] = field(default_factory=list)
```

- [ ] **Step 2: Adicionar os 2 campos em `AccountConfigPatch`**

No mesmo arquivo, em `AccountConfigPatch`, adicionar após `chatnexo_api_key: str | None`:

```python
    chatnexo_account_id: int | None = field(default=None)
    chatnexo_inbox_id: int | None = field(default=None)
```

- [ ] **Step 3: Verificar typecheck**

Run: `cd apps/api && uv run mypy src/shared/domain/entities/account_config.py`
Expected: nenhum erro

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared/domain/entities/account_config.py
git commit -m "feat(domain): adiciona chatnexo_account_id e chatnexo_inbox_id em IntegrationConfig"
```

---

## Task 2: `AccountConfigRepository.get()` carrega os 2 campos com fallback ao `.env`

**Files:**
- Modify: `apps/api/src/shared/adapters/db/repositories/account_config_repo.py:108-124`
- Test: `apps/api/tests/unit/adapters/test_account_config_repo.py`

- [ ] **Step 1: Escrever teste falhando para fallback do `.env`**

Em `apps/api/tests/unit/adapters/test_account_config_repo.py`, adicionar:

```python
async def test_get_chatnexo_account_and_inbox_ids_fallback_to_env(
    async_session: AsyncSession,
) -> None:
    """Quando JSONB não tem os IDs, usa os defaults do Settings (.env)."""
    # account vazia (sem settings)
    account = AccountModel(name="test", settings={})
    async_session.add(account)
    await async_session.flush()

    fernet = Fernet(Fernet.generate_key())
    repo = AccountConfigRepository(session=async_session, fernet=fernet)
    cfg = await repo.get(account_id=1)

    # Settings tem defaults = 1 para ambos (ver shared/config/settings.py)
    assert cfg.integration.chatnexo_account_id == 1
    assert cfg.integration.chatnexo_inbox_id == 1


async def test_get_chatnexo_account_and_inbox_ids_from_jsonb(
    async_session: AsyncSession,
) -> None:
    """Quando JSONB tem os IDs, prevalece sobre .env."""
    account = AccountModel(
        name="test",
        settings={"integration": {"chatnexo_account_id": 42, "chatnexo_inbox_id": 7}},
    )
    async_session.add(account)
    await async_session.flush()

    fernet = Fernet(Fernet.generate_key())
    repo = AccountConfigRepository(session=async_session, fernet=fernet)
    cfg = await repo.get(account_id=1)

    assert cfg.integration.chatnexo_account_id == 42
    assert cfg.integration.chatnexo_inbox_id == 7
```

Imports no topo do arquivo (se faltarem):
```python
from cryptography.fernet import Fernet
from shared.adapters.db.models import AccountModel
from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
```

- [ ] **Step 2: Rodar teste para confirmar falha**

Run:
```bash
cd apps/api && INTEGRATION_CREDENTIALS_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") DATABASE_URL=postgresql+asyncpg://test:test@localhost/test REDIS_URL=redis://localhost OPENAI_API_KEY=test CHATNEXO_BASE_URL=test CHATNEXO_API_KEY=test HUBLA_WEBHOOK_SECRET=test ADMIN_API_KEY=test META_API_KEY=test JWT_SECRET=test-jwt-secret-with-enough-entropy-for-ci uv run pytest tests/unit/adapters/test_account_config_repo.py::test_get_chatnexo_account_and_inbox_ids_fallback_to_env -x -q
```

Expected: FAIL com `AttributeError: 'IntegrationConfig' object has no attribute 'chatnexo_account_id'` (porque ainda não passamos no construtor)

- [ ] **Step 3: Atualizar `get()` para carregar os 2 IDs**

Em `apps/api/src/shared/adapters/db/repositories/account_config_repo.py`, no método `get()`, dentro do `IntegrationConfig(...)`, **após** `chatnexo_api_key=` e **antes** de `hubla_webhook_secret=`, adicionar:

```python
                chatnexo_account_id=int(i.get("chatnexo_account_id", s.chatnexo_account_id)),
                chatnexo_inbox_id=int(i.get("chatnexo_inbox_id", s.chatnexo_inbox_id)),
```

- [ ] **Step 4: Rodar teste e confirmar PASS**

Run:
```bash
cd apps/api && INTEGRATION_CREDENTIALS_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") DATABASE_URL=postgresql+asyncpg://test:test@localhost/test REDIS_URL=redis://localhost OPENAI_API_KEY=test CHATNEXO_BASE_URL=test CHATNEXO_API_KEY=test HUBLA_WEBHOOK_SECRET=test ADMIN_API_KEY=test META_API_KEY=test JWT_SECRET=test-jwt-secret-with-enough-entropy-for-ci uv run pytest tests/unit/adapters/test_account_config_repo.py -x -q
```

Expected: PASS em ambos os testes novos + os existentes

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/account_config_repo.py apps/api/tests/unit/adapters/test_account_config_repo.py
git commit -m "feat(repo): AccountConfigRepository.get() carrega chatnexo_account/inbox_id"
```

---

## Task 3: `AccountConfigRepository.update()` persiste os 2 IDs

**Files:**
- Modify: `apps/api/src/shared/adapters/db/repositories/account_config_repo.py` (método `update()`)
- Test: `apps/api/tests/unit/adapters/test_account_config_repo.py`

- [ ] **Step 1: Escrever teste falhando**

Adicionar em `test_account_config_repo.py`:

```python
async def test_update_persists_chatnexo_account_and_inbox_ids(
    async_session: AsyncSession,
) -> None:
    """update() persiste os IDs no JSONB sem encriptar."""
    fernet = Fernet(Fernet.generate_key())
    repo = AccountConfigRepository(session=async_session, fernet=fernet)

    patch = AccountConfigPatch(chatnexo_account_id=99, chatnexo_inbox_id=3)
    await repo.update(account_id=1, patch=patch)
    await async_session.flush()

    # Lê de novo e verifica que persistiu
    cfg = await repo.get(account_id=1)
    assert cfg.integration.chatnexo_account_id == 99
    assert cfg.integration.chatnexo_inbox_id == 3
```

Import (se faltar):
```python
from shared.domain.entities.account_config import AccountConfigPatch
```

- [ ] **Step 2: Rodar teste e confirmar FALHA**

Run:
```bash
cd apps/api && INTEGRATION_CREDENTIALS_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") DATABASE_URL=postgresql+asyncpg://test:test@localhost/test REDIS_URL=redis://localhost OPENAI_API_KEY=test CHATNEXO_BASE_URL=test CHATNEXO_API_KEY=test HUBLA_WEBHOOK_SECRET=test ADMIN_API_KEY=test META_API_KEY=test JWT_SECRET=test-jwt-secret-with-enough-entropy-for-ci uv run pytest tests/unit/adapters/test_account_config_repo.py::test_update_persists_chatnexo_account_and_inbox_ids -x -q
```

Expected: FAIL (a propriedade existe mas patch não persiste — o teste deve falhar no assert de 99)

- [ ] **Step 3: Atualizar `update()` para persistir os IDs**

Em `apps/api/src/shared/adapters/db/repositories/account_config_repo.py`, no método `update()`, **após** o loop de strings (`for key in ("chatnexo_base_url", ...)`) e **antes** do loop `for key in ("idle_ping_minutes", ...)`, adicionar:

```python
        if patch.chatnexo_account_id is not None:
            i["chatnexo_account_id"] = patch.chatnexo_account_id
        if patch.chatnexo_inbox_id is not None:
            i["chatnexo_inbox_id"] = patch.chatnexo_inbox_id
```

- [ ] **Step 4: Rodar teste e confirmar PASS**

Run:
```bash
cd apps/api && INTEGRATION_CREDENTIALS_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") DATABASE_URL=postgresql+asyncpg://test:test@localhost/test REDIS_URL=redis://localhost OPENAI_API_KEY=test CHATNEXO_BASE_URL=test CHATNEXO_API_KEY=test HUBLA_WEBHOOK_SECRET=test ADMIN_API_KEY=test META_API_KEY=test JWT_SECRET=test-jwt-secret-with-enough-entropy-for-ci uv run pytest tests/unit/adapters/test_account_config_repo.py -x -q
```

Expected: PASS em todos

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/account_config_repo.py apps/api/tests/unit/adapters/test_account_config_repo.py
git commit -m "feat(repo): AccountConfigRepository.update() persiste chatnexo_account/inbox_id"
```

---

## Task 4: Schemas HTTP + Router expõem os 2 IDs

**Files:**
- Modify: `apps/api/src/interface/http/schemas/admin_settings.py`
- Modify: `apps/api/src/interface/http/routers/admin/settings.py`
- Test: `apps/api/tests/unit/interface/admin/test_settings_router.py`

- [ ] **Step 1: Escrever teste de GET e PUT do router**

Em `apps/api/tests/unit/interface/admin/test_settings_router.py`, adicionar:

```python
async def test_get_settings_returns_chatnexo_account_and_inbox_ids(client) -> None:
    """GET /admin/settings retorna os 2 novos campos."""
    response = await client.get(
        "/admin/settings", headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "chatnexo_account_id" in body
    assert "chatnexo_inbox_id" in body
    assert isinstance(body["chatnexo_account_id"], int)
    assert isinstance(body["chatnexo_inbox_id"], int)


async def test_put_settings_updates_chatnexo_account_and_inbox_ids(client) -> None:
    """PUT /admin/settings aceita e persiste os 2 IDs."""
    response = await client.put(
        "/admin/settings",
        headers={"Authorization": "Bearer test-token"},
        json={"chatnexo_account_id": 77, "chatnexo_inbox_id": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["chatnexo_account_id"] == 77
    assert body["chatnexo_inbox_id"] == 5
```

Se a fixture `client` ou helper `_make_config` existirem com os campos fixos, ajuste `_make_config` adicionando `chatnexo_account_id=1, chatnexo_inbox_id=1` ao constructor de `IntegrationConfig` (o teste já vai exigir isso no Step 2 abaixo).

- [ ] **Step 2: Rodar teste e confirmar FALHA**

Run:
```bash
cd apps/api && INTEGRATION_CREDENTIALS_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") DATABASE_URL=postgresql+asyncpg://test:test@localhost/test REDIS_URL=redis://localhost OPENAI_API_KEY=test CHATNEXO_BASE_URL=test CHATNEXO_API_KEY=test HUBLA_WEBHOOK_SECRET=test ADMIN_API_KEY=test META_API_KEY=test JWT_SECRET=test-jwt-secret-with-enough-entropy-for-ci uv run pytest tests/unit/interface/admin/test_settings_router.py -x -q
```

Expected: FAIL com KeyError em `chatnexo_account_id` (campo não retornado pelo schema)

- [ ] **Step 3: Adicionar os campos no schema `AccountSettingsResponse`**

Em `apps/api/src/interface/http/schemas/admin_settings.py`, em `AccountSettingsResponse`, após `chatnexo_api_key: str` e antes de `hubla_webhook_secret: str`:

```python
    chatnexo_account_id: int
    chatnexo_inbox_id: int
```

- [ ] **Step 4: Adicionar os campos no schema `AccountSettingsUpdateRequest`**

No mesmo arquivo, em `AccountSettingsUpdateRequest`, após `chatnexo_api_key: str | None = None`:

```python
    chatnexo_account_id: int | None = None
    chatnexo_inbox_id: int | None = None
```

- [ ] **Step 5: Atualizar `_to_response()` no router**

Em `apps/api/src/interface/http/routers/admin/settings.py`, dentro de `_to_response()`, no `AccountSettingsResponse(...)`, após `chatnexo_api_key=_mask(i.chatnexo_api_key)` e antes de `hubla_webhook_secret=...`:

```python
        chatnexo_account_id=i.chatnexo_account_id,
        chatnexo_inbox_id=i.chatnexo_inbox_id,
```

- [ ] **Step 6: Atualizar `update_settings_endpoint()` no router**

No mesmo arquivo, no `AccountConfigPatch(...)`, após `chatnexo_api_key=body.chatnexo_api_key` e antes de `hubla_webhook_secret=...`:

```python
        chatnexo_account_id=body.chatnexo_account_id,
        chatnexo_inbox_id=body.chatnexo_inbox_id,
```

- [ ] **Step 7: Rodar testes e confirmar PASS**

Run:
```bash
cd apps/api && INTEGRATION_CREDENTIALS_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") DATABASE_URL=postgresql+asyncpg://test:test@localhost/test REDIS_URL=redis://localhost OPENAI_API_KEY=test CHATNEXO_BASE_URL=test CHATNEXO_API_KEY=test HUBLA_WEBHOOK_SECRET=test ADMIN_API_KEY=test META_API_KEY=test JWT_SECRET=test-jwt-secret-with-enough-entropy-for-ci uv run pytest tests/unit/interface/admin/test_settings_router.py -x -q
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/interface/http/schemas/admin_settings.py apps/api/src/interface/http/routers/admin/settings.py apps/api/tests/unit/interface/admin/test_settings_router.py
git commit -m "feat(http): expor chatnexo_account_id e chatnexo_inbox_id em /admin/settings"
```

---

## Task 5: `PurchaseHandler` aceita `chatnexo_account_id` no constructor

**Files:**
- Modify: `apps/api/src/shared/application/purchase_handler.py`
- Modify: `apps/api/src/interface/worker/handlers/hubla_event.py:60-66` (caller)

- [ ] **Step 1: Adicionar parâmetro `chatnexo_account_id` no `__init__` de `PurchaseHandler`**

Em `apps/api/src/shared/application/purchase_handler.py`, no `__init__` da classe `PurchaseHandler`, adicionar parâmetro `chatnexo_account_id: int` e armazenar como `self._chatnexo_account_id`:

```python
    def __init__(
        self,
        *,
        contact_repo: ContactRepository,
        chatnexo: Any,
        access_case_repo: Any,
        scheduler: Any,
        product_repo: Any,
        chatnexo_account_id: int,
    ) -> None:
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._access_case_repo = access_case_repo
        self._scheduler = scheduler
        self._product_repo = product_repo
        self._chatnexo_account_id = chatnexo_account_id
```

(Mantenha a assinatura exata dos campos existentes — só adicionar o novo no final como keyword-only.)

- [ ] **Step 2: Substituir `get_settings().chatnexo_account_id` por `self._chatnexo_account_id`**

No mesmo arquivo, na linha ~61 (método `_dispatch_welcome`), trocar:

```python
        chatnexo_account_id_int = get_settings().chatnexo_account_id
```

por:

```python
        chatnexo_account_id_int = self._chatnexo_account_id
```

- [ ] **Step 3: Atualizar caller em `hubla_event.py` para passar o novo argumento**

Em `apps/api/src/interface/worker/handlers/hubla_event.py`, no construtor de `PurchaseHandler(...)`:

```python
        purchase_handler = PurchaseHandler(
            contact_repo=contact_repo,
            chatnexo=chatnexo,
            access_case_repo=access_case_repo,
            scheduler=scheduler,
            product_repo=product_repo,
            chatnexo_account_id=account_config.integration.chatnexo_account_id,
        )
```

- [ ] **Step 4: Verificar typecheck**

Run: `cd apps/api && uv run mypy src/shared/application/purchase_handler.py src/interface/worker/handlers/hubla_event.py`
Expected: nenhum erro

- [ ] **Step 5: Rodar testes existentes de purchase**

Run:
```bash
cd apps/api && INTEGRATION_CREDENTIALS_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") DATABASE_URL=postgresql+asyncpg://test:test@localhost/test REDIS_URL=redis://localhost OPENAI_API_KEY=test CHATNEXO_BASE_URL=test CHATNEXO_API_KEY=test HUBLA_WEBHOOK_SECRET=test ADMIN_API_KEY=test META_API_KEY=test JWT_SECRET=test-jwt-secret-with-enough-entropy-for-ci uv run pytest tests/unit/application/test_purchase_handler.py -x -q
```

Expected: testes que instanciam `PurchaseHandler` vão falhar com `missing keyword argument 'chatnexo_account_id'` — corrigir cada um adicionando `chatnexo_account_id=1` no constructor. Rodar de novo até PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/shared/application/purchase_handler.py apps/api/src/interface/worker/handlers/hubla_event.py apps/api/tests/unit/application/test_purchase_handler.py
git commit -m "refactor(purchase): receber chatnexo_account_id via constructor"
```

---

## Task 6: `HublaEventHandler` aceita `chatnexo_account_id` no constructor

**Files:**
- Modify: `apps/api/src/shared/application/hubla_event_handler.py:233`
- Modify: `apps/api/src/interface/worker/handlers/hubla_event.py:69-80` (caller)

- [ ] **Step 1: Adicionar parâmetro `chatnexo_account_id` no `__init__`**

Em `apps/api/src/shared/application/hubla_event_handler.py`, no `__init__` da classe `HublaEventHandler`, adicionar parâmetro keyword-only `chatnexo_account_id: int` e armazenar como `self._chatnexo_account_id`. Mantenha os parâmetros existentes na ordem; coloque o novo após `account_id`.

```python
    def __init__(
        self,
        *,
        product_repo: ...,
        flow_repo: ...,
        contact_repo: ...,
        chatnexo: ...,
        enroll_contact_uc: ...,
        purchase_handler: ...,
        lead_repo: ...,
        hubla_event_repo: ...,
        account_id: UUID,
        chatnexo_account_id: int,
    ) -> None:
        # ... atribuições existentes ...
        self._chatnexo_account_id = chatnexo_account_id
```

(Use os tipos exatos dos parâmetros existentes — não reinvente.)

- [ ] **Step 2: Substituir `get_settings().chatnexo_account_id` por `self._chatnexo_account_id`**

Na linha 233 do mesmo arquivo, trocar:

```python
        chatnexo_account_id = str(get_settings().chatnexo_account_id)
```

por:

```python
        chatnexo_account_id = str(self._chatnexo_account_id)
```

- [ ] **Step 3: Atualizar caller em `hubla_event.py`**

Em `apps/api/src/interface/worker/handlers/hubla_event.py`, na instância de `HublaEventHandler(...)`, adicionar:

```python
        handler = HublaEventHandler(
            product_repo=product_repo,
            flow_repo=flow_repo,
            contact_repo=contact_repo,
            chatnexo=chatnexo,
            enroll_contact_uc=enroll_uc,
            purchase_handler=purchase_handler,
            lead_repo=lead_repo,
            hubla_event_repo=hubla_event_repo,
            account_id=account_uuid,
            chatnexo_account_id=account_config.integration.chatnexo_account_id,
        )
```

- [ ] **Step 4: Verificar typecheck**

Run: `cd apps/api && uv run mypy src/shared/application/hubla_event_handler.py src/interface/worker/handlers/hubla_event.py`
Expected: nenhum erro

- [ ] **Step 5: Rodar testes existentes de hubla_event**

Run:
```bash
cd apps/api && INTEGRATION_CREDENTIALS_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") DATABASE_URL=postgresql+asyncpg://test:test@localhost/test REDIS_URL=redis://localhost OPENAI_API_KEY=test CHATNEXO_BASE_URL=test CHATNEXO_API_KEY=test HUBLA_WEBHOOK_SECRET=test ADMIN_API_KEY=test META_API_KEY=test JWT_SECRET=test-jwt-secret-with-enough-entropy-for-ci uv run pytest tests/unit/application/test_hubla_event_handler.py -x -q
```

Expected: testes que instanciam `HublaEventHandler` vão falhar com missing kwarg — adicionar `chatnexo_account_id=1` em cada constructor. Rodar até PASS.

- [ ] **Step 6: Remover import `get_settings` se ficou sem uso em `hubla_event_handler.py`**

Verifique se `get_settings` ainda é referenciado no arquivo:
```bash
grep -n "get_settings" apps/api/src/shared/application/hubla_event_handler.py
```

Se houver outras referências, deixe o import. Se essa era a única, remova a linha:
```python
from shared.config.settings import get_settings
```

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/shared/application/hubla_event_handler.py apps/api/src/interface/worker/handlers/hubla_event.py apps/api/tests/unit/application/test_hubla_event_handler.py
git commit -m "refactor(hubla-event): receber chatnexo_account_id via constructor"
```

---

## Task 7: `DispatchOnboardingStep.execute()` recebe `chatnexo_account_id` por parâmetro

**Files:**
- Modify: `apps/api/src/shared/application/use_cases/onboarding/dispatch_onboarding_step.py`
- Modify: `apps/api/src/interface/worker/handlers/scheduled.py` (caller)

- [ ] **Step 1: Adicionar parâmetro `chatnexo_account_id: int` ao `execute()`**

Em `apps/api/src/shared/application/use_cases/onboarding/dispatch_onboarding_step.py`, no método `execute()`, após `contact_phone: str,` adicionar:

```python
    async def execute(
        self,
        *,
        enrollment_step_id: UUID,
        account_id: UUID,
        conversation_id: str,
        contact_phone: str,
        chatnexo_account_id: int,
    ) -> DispatchResult:
```

- [ ] **Step 2: Substituir as 3 ocorrências de `get_settings().chatnexo_account_id`**

No mesmo arquivo, trocar nas linhas 78, 131 (no log warning) e 187:

Linha ~78 (envio de message_text):
```python
                    account_id=str(chatnexo_account_id),
```

Linha ~131 (log warning de template não encontrado):
```python
                        account_id=str(chatnexo_account_id),
```

Linha ~187 (envio de template):
```python
                    account_id=str(chatnexo_account_id),
```

- [ ] **Step 3: Remover import `get_settings` se ficou sem uso**

Verifique:
```bash
grep -n "get_settings" apps/api/src/shared/application/use_cases/onboarding/dispatch_onboarding_step.py
```

Se sumiu, remova:
```python
from shared.config.settings import get_settings
```

- [ ] **Step 4: Atualizar caller em `scheduled.py`**

Em `apps/api/src/interface/worker/handlers/scheduled.py`, no `result = await dispatch.execute(...)`, adicionar `chatnexo_account_id`:

```python
            result = await dispatch.execute(
                enrollment_step_id=_UUID(payload["enrollment_step_id"]),
                account_id=_UUID(payload["account_id"]),
                conversation_id=payload["conversation_id"],
                contact_phone=payload.get("contact_phone", ""),
                chatnexo_account_id=config.integration.chatnexo_account_id,
            )
```

(O `config` já existe no escopo — vem de `config = await config_repo.get(account_id=1)` algumas linhas acima.)

- [ ] **Step 5: Verificar typecheck**

Run: `cd apps/api && uv run mypy src/shared/application/use_cases/onboarding/dispatch_onboarding_step.py src/interface/worker/handlers/scheduled.py`
Expected: nenhum erro

- [ ] **Step 6: Rodar testes de dispatch_onboarding_step**

Run:
```bash
cd apps/api && INTEGRATION_CREDENTIALS_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") DATABASE_URL=postgresql+asyncpg://test:test@localhost/test REDIS_URL=redis://localhost OPENAI_API_KEY=test CHATNEXO_BASE_URL=test CHATNEXO_API_KEY=test HUBLA_WEBHOOK_SECRET=test ADMIN_API_KEY=test META_API_KEY=test JWT_SECRET=test-jwt-secret-with-enough-entropy-for-ci uv run pytest tests/unit/application/test_dispatch_onboarding_step.py -x -q
```

Expected: testes que chamam `execute()` vão falhar com missing kwarg — adicionar `chatnexo_account_id=1` em cada chamada. Rodar até PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/shared/application/use_cases/onboarding/dispatch_onboarding_step.py apps/api/src/interface/worker/handlers/scheduled.py apps/api/tests/unit/application/test_dispatch_onboarding_step.py
git commit -m "refactor(onboarding-step): receber chatnexo_account_id como parametro"
```

---

## Task 8: Frontend — tipo `AccountSettings` ganha os 2 campos

**Files:**
- Modify: `apps/web/src/features/settings/types.ts`

- [ ] **Step 1: Adicionar os campos no tipo**

Em `apps/web/src/features/settings/types.ts`, dentro de `interface AccountSettings`, após `chatnexo_api_key: string` e antes de `hubla_webhook_secret: string`:

```typescript
export interface AccountSettings {
  chatnexo_base_url: string;
  chatnexo_api_key: string;
  chatnexo_account_id: number;
  chatnexo_inbox_id: number;
  hubla_webhook_secret: string;
  openai_api_key: string;
  meta_api_key: string;
  meta_waba_id: string;
  meta_app_id: string;
  idle_ping_minutes: number;
  idle_close_minutes: number;
  intent_confidence_threshold: number;
  message_buffer_wait_seconds: number;
  refund_deadline_days: number;
  welcome_d1_delay_hours: number;
  ai_memory_messages: number;
}
```

- [ ] **Step 2: Verificar typecheck**

Run: `cd apps/web && npx tsc --noEmit`
Expected: nenhum erro

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/settings/types.ts
git commit -m "feat(web): AccountSettings ganha chatnexo_account_id e chatnexo_inbox_id"
```

---

## Task 9: Frontend — `IntegrationSection` mostra os 2 campos na seção ChatNexo

**Files:**
- Modify: `apps/web/src/features/settings/components/IntegrationSection.tsx`

- [ ] **Step 1: Adicionar os 2 campos na config do card ChatNexo**

Em `apps/web/src/features/settings/components/IntegrationSection.tsx`, no array `SECTIONS`, dentro do objeto com `id: "chatnexo"`, no array `fields`, adicionar os 2 novos campos **após** `chatnexo_api_key`:

```typescript
  {
    id: "chatnexo",
    title: "ChatNexo",
    subtitle: "Plataforma de mensagens WhatsApp",
    icon: "chat",
    fields: [
      {
        key: "chatnexo_base_url",
        label: "Base URL",
        type: "url",
        placeholder: "https://api.chatnexo.com.br",
      },
      {
        key: "chatnexo_api_key",
        label: "API Key (fallback)",
        type: "secret",
        description: "Usada quando nenhum atendente está configurado",
      },
      {
        key: "chatnexo_account_id",
        label: "Account ID",
        type: "number",
        description: "ID da conta no ChatNexo (troca de conta sem deploy)",
      },
      {
        key: "chatnexo_inbox_id",
        label: "Inbox ID",
        type: "number",
        description: "ID da inbox dentro da conta",
      },
    ],
  },
```

- [ ] **Step 2: Verificar typecheck**

Run: `cd apps/web && npx tsc --noEmit`
Expected: nenhum erro

- [ ] **Step 3: Verificar visualmente (manual)**

Subir o stack:
```bash
docker compose up postgres redis -d
cd apps/api && uv run uvicorn main:app --reload &
cd apps/web && npm run dev
```

Abrir `http://localhost:3000/settings`, conferir:
- Card ChatNexo agora tem 4 campos (Base URL, API Key, Account ID, Inbox ID)
- Clicar no lápis de "Account ID" → input numérico aparece com animação
- Digitar valor + Enter → toast de sucesso aparece
- Recarregar a página → valor persistiu
- Trocar de volta para o valor anterior

Expected: tudo funciona end-to-end

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/settings/components/IntegrationSection.tsx
git commit -m "feat(web): UI mostra Account ID e Inbox ID do ChatNexo em Settings"
```

---

## Task 10: Validação final + push

**Files:** todos modificados

- [ ] **Step 1: Lint + format backend**

```bash
cd apps/api && uv run ruff check src tests && uv run ruff format --check src tests
```

Expected: All checks passed!

- [ ] **Step 2: Typecheck backend**

```bash
cd apps/api && uv run mypy src
```

Expected: Success: no issues found

- [ ] **Step 3: Testes backend completos**

```bash
cd apps/api && INTEGRATION_CREDENTIALS_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") DATABASE_URL=postgresql+asyncpg://test:test@localhost/test REDIS_URL=redis://localhost OPENAI_API_KEY=test CHATNEXO_BASE_URL=test CHATNEXO_API_KEY=test HUBLA_WEBHOOK_SECRET=test ADMIN_API_KEY=test META_API_KEY=test JWT_SECRET=test-jwt-secret-with-enough-entropy-for-ci uv run pytest tests/unit -x -q
```

Expected: todos passam

- [ ] **Step 4: Typecheck frontend**

```bash
cd apps/web && npx tsc --noEmit
```

Expected: sem output (sucesso)

- [ ] **Step 5: Push da branch**

```bash
git push
```

- [ ] **Step 6: Verificar CI no PR**

Aguardar o CI rodar. Esperado: 7 checks verdes (Lint, Tests, Type Check, Security Audit, Docker api/worker/web).

---

## Checklist final (espelha Critérios de Aceite do Spec)

- [ ] `GET /admin/settings` retorna `chatnexo_account_id` e `chatnexo_inbox_id`
- [ ] `PUT /admin/settings` aceita e persiste os dois
- [ ] Trocar valor pela UI faz disparos novos usarem o ID novo (sem restart)
- [ ] Quando JSONB vazio, `.env` continua sendo usado
- [ ] Page `/settings` mostra os 2 campos com edição inline
- [ ] `ruff`, `mypy`, `tsc`, `pytest tests/unit` passam
- [ ] CI verde no PR

---

## Self-Review

**Spec coverage:**
- Domain entities (spec §1): Task 1 ✅
- Repository (spec §2): Tasks 2, 3 ✅
- HTTP schemas (spec §3): Task 4 ✅
- Router (spec §4): Task 4 ✅
- Call sites (spec §5): Tasks 5, 6, 7 ✅
- Frontend types (spec §6): Task 8 ✅
- Frontend UI (spec §7): Task 9 ✅
- "Sem migration": confirmado — não há nenhum task de migration ✅
- ".env permanece como fallback": confirmado em Task 2 Step 3 ✅

**Placeholder scan:** zero TBDs, todo código está completo, todos os file paths são exatos.

**Type consistency:** `chatnexo_account_id: int` no Python e `: number` no TypeScript; mesmo nome em todos os lugares.

**Sem gaps.**
