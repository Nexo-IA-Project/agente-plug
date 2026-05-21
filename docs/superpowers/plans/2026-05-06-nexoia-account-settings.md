# Account Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar página de configurações no painel web que persiste credenciais de integração e parâmetros do agente no banco de dados (AccountModel.settings JSONB), com efeito imediato sem reiniciar o servidor.

**Architecture:** Entidade `AccountConfig` no domínio → `AccountConfigRepository` no adapter (criptografa campos sensíveis com Fernet, lê AccountModel.settings JSONB, fallback para env vars) → Use Cases na camada de application → Router FastAPI GET/PUT `/admin/settings` → Worker carrega config do DB para instanciar adapters → Frontend com dois grupos de formulário (Integrações e Comportamento).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async, `cryptography.fernet.Fernet`, Next.js 15, Tailwind, NexoIA design system tokens.

---

## File Map

### Criar
| Arquivo | Responsabilidade |
|---|---|
| `apps/api/src/shared/domain/entities/account_config.py` | Entidade AccountConfig + AccountConfigPatch |
| `apps/api/src/shared/adapters/db/repositories/account_config_repo.py` | Repositório: lê/escreve JSONB com criptografia Fernet |
| `apps/api/src/interface/http/deps/admin_auth.py` | `AdminAuth` dataclass + `_require_admin` dep (extraído de api_tokens.py) |
| `apps/api/src/shared/application/use_cases/admin/__init__.py` | Package marker |
| `apps/api/src/shared/application/use_cases/admin/get_account_config.py` | Use case: lê config e mascara sensíveis |
| `apps/api/src/shared/application/use_cases/admin/update_account_config.py` | Use case: valida + persiste patch |
| `apps/api/src/interface/http/schemas/admin_settings.py` | Pydantic schemas da API |
| `apps/api/src/interface/http/routers/admin/settings.py` | Router GET/PUT /admin/settings |
| `apps/api/tests/unit/adapters/test_account_config_repo.py` | Unit tests do repositório |
| `apps/api/tests/unit/application/admin/__init__.py` | Package marker |
| `apps/api/tests/unit/application/admin/test_account_config_use_cases.py` | Unit tests dos use cases |
| `apps/api/tests/unit/interface/admin/test_settings_router.py` | Unit tests do router |
| `apps/web/src/features/settings/types.ts` | Tipos TypeScript espelhando schemas da API |
| `apps/web/src/features/settings/components/IntegrationSection.tsx` | Formulário grupo A |
| `apps/web/src/features/settings/components/BehaviorSection.tsx` | Formulário grupo B |
| `apps/web/src/app/settings/page.tsx` | Página /settings |

### Modificar
| Arquivo | Mudança |
|---|---|
| `apps/api/src/interface/http/routers/admin/api_tokens.py` | Importar AdminAuth e _require_admin de admin_auth.py |
| `apps/api/src/main.py` | Registrar router de settings |
| `apps/api/src/shared/adapters/chatnexo/client.py` | Adicionar from_account_config() |
| `apps/api/src/shared/adapters/cademi/client.py` | Adicionar from_account_config() |
| `apps/api/src/interface/worker/handlers/message.py` | Carregar AccountConfig do DB |
| `apps/web/src/lib/api.ts` | Adicionar getAccountSettings, updateAccountSettings |
| `apps/web/src/shared/components/layout/Sidebar.tsx` | Adicionar item "Configurações" |

---

## Task 1: Entidade AccountConfig no domínio

**Files:**
- Create: `apps/api/src/shared/domain/entities/account_config.py`

- [ ] **Criar o arquivo de entidade**

```python
# apps/api/src/shared/domain/entities/account_config.py
from __future__ import annotations

from dataclasses import dataclass, field


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
    """Patch parcial — apenas campos não-None são atualizados."""
    chatnexo_base_url: str | None = field(default=None)
    chatnexo_api_key: str | None = field(default=None)
    hubla_webhook_secret: str | None = field(default=None)
    cademi_api_url: str | None = field(default=None)
    cademi_api_key: str | None = field(default=None)
    cademi_max_retries: int | None = field(default=None)
    cademi_retry_base_seconds: float | None = field(default=None)
    openai_api_key: str | None = field(default=None)
    meta_api_key: str | None = field(default=None)
    idle_ping_minutes: int | None = field(default=None)
    idle_close_minutes: int | None = field(default=None)
    intent_confidence_threshold: float | None = field(default=None)
    message_buffer_wait_seconds: int | None = field(default=None)
    refund_deadline_days: int | None = field(default=None)
    welcome_d1_delay_hours: int | None = field(default=None)
    loja_express_d1_delay_hours: int | None = field(default=None)
    loja_express_d3_delay_hours: int | None = field(default=None)
    loja_express_d5_delay_hours: int | None = field(default=None)
    loja_express_d7_delay_hours: int | None = field(default=None)
```

- [ ] **Commit**

```bash
git add apps/api/src/shared/domain/entities/account_config.py
git commit -m "feat(settings): entidade AccountConfig no domínio"
```

---

## Task 2: AccountConfigRepository

**Files:**
- Create: `apps/api/src/shared/adapters/db/repositories/account_config_repo.py`
- Create: `apps/api/tests/unit/adapters/test_account_config_repo.py`

> **Nota sobre account_id:** `AccountModel.id` é UUID mas o sistema usa integer `account_id` no JWT/webhook (ChatNexo account ID). Como o sistema é single-tenant, o repositório busca o primeiro (e único) `AccountModel` com `.limit(1)`. O parâmetro `account_id: int` é aceito para consistência de interface mas não é usado como chave de busca no AccountModel.

- [ ] **Escrever os testes primeiro**

```python
# apps/api/tests/unit/adapters/test_account_config_repo.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from shared.adapters.db.repositories.account_config_repo import (
    AccountConfigRepository,
    _mask,
)
from shared.domain.entities.account_config import AccountConfigPatch


def _make_fernet() -> Fernet:
    return Fernet(Fernet.generate_key())


def _make_repo(session: AsyncMock, fernet: Fernet) -> AccountConfigRepository:
    return AccountConfigRepository(session=session, fernet=fernet)


def _mock_account(settings_data: dict) -> MagicMock:
    m = MagicMock()
    m.settings = settings_data
    return m


def _mock_session_with_account(account_mock) -> AsyncMock:
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = account_mock
    session.execute = AsyncMock(return_value=result_mock)
    return session


@pytest.mark.asyncio
async def test_get_returns_env_defaults_when_jsonb_empty():
    """Quando AccountModel.settings está vazio, usa env vars como fallback."""
    session = _mock_session_with_account(_mock_account({}))
    fernet = _make_fernet()
    repo = _make_repo(session, fernet)

    with patch("shared.adapters.db.repositories.account_config_repo.get_settings") as mock_s:
        mock_s.return_value.chatnexo_base_url = "http://default"
        mock_s.return_value.chatnexo_api_key = "default_key"
        mock_s.return_value.hubla_webhook_secret = "default_secret"
        mock_s.return_value.cademi_api_url = ""
        mock_s.return_value.cademi_api_key = ""
        mock_s.return_value.cademi_max_retries = 3
        mock_s.return_value.cademi_retry_base_seconds = 1.0
        mock_s.return_value.openai_api_key = "sk-default"
        mock_s.return_value.meta_api_key = "meta_default"
        mock_s.return_value.idle_ping_minutes = 30
        mock_s.return_value.idle_close_minutes = 20
        mock_s.return_value.intent_confidence_threshold = 0.7
        mock_s.return_value.message_buffer_wait_seconds = 0
        mock_s.return_value.refund_deadline_days = 7
        mock_s.return_value.welcome_d1_delay_hours = 24
        mock_s.return_value.loja_express_d1_delay_hours = 24
        mock_s.return_value.loja_express_d3_delay_hours = 72
        mock_s.return_value.loja_express_d5_delay_hours = 120
        mock_s.return_value.loja_express_d7_delay_hours = 168

        config = await repo.get(account_id=1)

    assert config.integration.chatnexo_base_url == "http://default"
    assert config.integration.openai_api_key == "sk-default"
    assert config.behavior.idle_ping_minutes == 30
    assert config.behavior.refund_deadline_days == 7


@pytest.mark.asyncio
async def test_get_uses_db_values_over_env_defaults():
    """Valores no JSONB têm prioridade sobre env vars."""
    fernet = _make_fernet()
    encrypted_key = fernet.encrypt(b"sk-db-key").decode()
    account = _mock_account({
        "integration": {
            "chatnexo_base_url": "http://from-db",
            "openai_api_key": encrypted_key,
        },
        "behavior": {
            "idle_ping_minutes": 45,
        },
    })
    session = _mock_session_with_account(account)
    repo = _make_repo(session, fernet)

    with patch("shared.adapters.db.repositories.account_config_repo.get_settings") as mock_s:
        mock_s.return_value.chatnexo_base_url = "http://default"
        mock_s.return_value.chatnexo_api_key = "default_key"
        mock_s.return_value.hubla_webhook_secret = "default_secret"
        mock_s.return_value.cademi_api_url = ""
        mock_s.return_value.cademi_api_key = ""
        mock_s.return_value.cademi_max_retries = 3
        mock_s.return_value.cademi_retry_base_seconds = 1.0
        mock_s.return_value.openai_api_key = "sk-default"
        mock_s.return_value.meta_api_key = "meta_default"
        mock_s.return_value.idle_ping_minutes = 30
        mock_s.return_value.idle_close_minutes = 20
        mock_s.return_value.intent_confidence_threshold = 0.7
        mock_s.return_value.message_buffer_wait_seconds = 0
        mock_s.return_value.refund_deadline_days = 7
        mock_s.return_value.welcome_d1_delay_hours = 24
        mock_s.return_value.loja_express_d1_delay_hours = 24
        mock_s.return_value.loja_express_d3_delay_hours = 72
        mock_s.return_value.loja_express_d5_delay_hours = 120
        mock_s.return_value.loja_express_d7_delay_hours = 168

        config = await repo.get(account_id=1)

    assert config.integration.chatnexo_base_url == "http://from-db"
    assert config.integration.openai_api_key == "sk-db-key"
    assert config.behavior.idle_ping_minutes == 45
    assert config.behavior.refund_deadline_days == 7  # fallback para env


@pytest.mark.asyncio
async def test_update_encrypts_sensitive_fields():
    """Campos sensíveis são criptografados antes de salvar."""
    fernet = _make_fernet()
    account = _mock_account({})
    session = _mock_session_with_account(account)
    repo = _make_repo(session, fernet)

    patch_obj = AccountConfigPatch(openai_api_key="sk-new-key")

    with patch("shared.adapters.db.repositories.account_config_repo.get_settings") as mock_s:
        _setup_default_settings(mock_s)
        await repo.update(account_id=1, patch=patch_obj)

    saved = account.settings
    stored_key = saved["integration"]["openai_api_key"]
    # Valor armazenado deve ser criptografado (não é o valor original)
    assert stored_key != "sk-new-key"
    # Mas pode ser descriptografado de volta
    assert fernet.decrypt(stored_key.encode()).decode() == "sk-new-key"


@pytest.mark.asyncio
async def test_update_ignores_masked_values():
    """Se o valor contém '****', o campo não é sobrescrito."""
    fernet = _make_fernet()
    encrypted_orig = fernet.encrypt(b"sk-original").decode()
    account = _mock_account({
        "integration": {"openai_api_key": encrypted_orig}
    })
    session = _mock_session_with_account(account)
    repo = _make_repo(session, fernet)

    patch_obj = AccountConfigPatch(openai_api_key="sk-proj-****abcd")

    with patch("shared.adapters.db.repositories.account_config_repo.get_settings") as mock_s:
        _setup_default_settings(mock_s)
        await repo.update(account_id=1, patch=patch_obj)

    saved = account.settings
    # Valor original preservado
    assert saved["integration"]["openai_api_key"] == encrypted_orig


def test_mask_hides_sensitive_values():
    assert _mask("sk-proj-abc123") == "sk-proj-****"
    assert _mask("short") == "****"
    assert _mask("") == ""
    assert _mask("12345678") == "12345678****"


def _setup_default_settings(mock_s):
    s = mock_s.return_value
    s.chatnexo_base_url = "http://default"
    s.chatnexo_api_key = "default_key"
    s.hubla_webhook_secret = "default_secret"
    s.cademi_api_url = ""
    s.cademi_api_key = ""
    s.cademi_max_retries = 3
    s.cademi_retry_base_seconds = 1.0
    s.openai_api_key = "sk-default"
    s.meta_api_key = "meta_default"
    s.idle_ping_minutes = 30
    s.idle_close_minutes = 20
    s.intent_confidence_threshold = 0.7
    s.message_buffer_wait_seconds = 0
    s.refund_deadline_days = 7
    s.welcome_d1_delay_hours = 24
    s.loja_express_d1_delay_hours = 24
    s.loja_express_d3_delay_hours = 72
    s.loja_express_d5_delay_hours = 120
    s.loja_express_d7_delay_hours = 168
```

- [ ] **Rodar para confirmar que falham**

```bash
cd apps/api && uv run pytest tests/unit/adapters/test_account_config_repo.py -v
```

Esperado: erros de import (módulo não existe ainda).

- [ ] **Implementar o repositório**

```python
# apps/api/src/shared/adapters/db/repositories/account_config_repo.py
from __future__ import annotations

from dataclasses import dataclass

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import AccountModel
from shared.config.settings import get_settings
from shared.domain.entities.account_config import (
    AccountConfig,
    AccountConfigPatch,
    BehaviorConfig,
    IntegrationConfig,
)

_SENSITIVE = frozenset({
    "chatnexo_api_key",
    "hubla_webhook_secret",
    "cademi_api_key",
    "openai_api_key",
    "meta_api_key",
})


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return value[:8] + "****"


def _decrypt(fernet: Fernet, value: str) -> str:
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception:
        return ""


def _encrypt(fernet: Fernet, value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def _should_skip(value: str | None) -> bool:
    return value is None or "****" in value


@dataclass
class AccountConfigRepository:
    session: AsyncSession
    fernet: Fernet

    async def _load_model(self) -> AccountModel | None:
        result = await self.session.execute(select(AccountModel).limit(1))
        return result.scalar_one_or_none()

    async def get(self, *, account_id: int) -> AccountConfig:  # noqa: ARG002
        model = await self._load_model()
        raw: dict = dict(model.settings or {}) if model else {}

        s = get_settings()
        i = raw.get("integration", {})
        b = raw.get("behavior", {})

        def gs(key: str, default: str) -> str:
            val = i.get(key) or ""
            if not val:
                return default
            if key in _SENSITIVE:
                return _decrypt(self.fernet, val)
            return val

        def gi(key: str, default: int) -> int:
            v = b.get(key)
            return int(v) if v is not None else default

        def gf(key: str, default: float) -> float:
            v = b.get(key)
            return float(v) if v is not None else default

        return AccountConfig(
            integration=IntegrationConfig(
                chatnexo_base_url=gs("chatnexo_base_url", s.chatnexo_base_url),
                chatnexo_api_key=gs("chatnexo_api_key", s.chatnexo_api_key),
                hubla_webhook_secret=gs("hubla_webhook_secret", s.hubla_webhook_secret),
                cademi_api_url=gs("cademi_api_url", s.cademi_api_url),
                cademi_api_key=gs("cademi_api_key", s.cademi_api_key),
                cademi_max_retries=int(i.get("cademi_max_retries", s.cademi_max_retries)),
                cademi_retry_base_seconds=float(i.get("cademi_retry_base_seconds", s.cademi_retry_base_seconds)),
                openai_api_key=gs("openai_api_key", s.openai_api_key),
                meta_api_key=gs("meta_api_key", s.meta_api_key),
            ),
            behavior=BehaviorConfig(
                idle_ping_minutes=gi("idle_ping_minutes", s.idle_ping_minutes),
                idle_close_minutes=gi("idle_close_minutes", s.idle_close_minutes),
                intent_confidence_threshold=gf("intent_confidence_threshold", s.intent_confidence_threshold),
                message_buffer_wait_seconds=gi("message_buffer_wait_seconds", s.message_buffer_wait_seconds),
                refund_deadline_days=gi("refund_deadline_days", s.refund_deadline_days),
                welcome_d1_delay_hours=gi("welcome_d1_delay_hours", s.welcome_d1_delay_hours),
                loja_express_d1_delay_hours=gi("loja_express_d1_delay_hours", s.loja_express_d1_delay_hours),
                loja_express_d3_delay_hours=gi("loja_express_d3_delay_hours", s.loja_express_d3_delay_hours),
                loja_express_d5_delay_hours=gi("loja_express_d5_delay_hours", s.loja_express_d5_delay_hours),
                loja_express_d7_delay_hours=gi("loja_express_d7_delay_hours", s.loja_express_d7_delay_hours),
            ),
        )

    async def update(self, *, account_id: int, patch: AccountConfigPatch) -> AccountConfig:  # noqa: ARG002
        model = await self._load_model()
        if model is None:
            model = AccountModel(name="default", settings={})
            self.session.add(model)
            await self.session.flush()

        current = dict(model.settings or {})
        i = dict(current.get("integration", {}))
        b = dict(current.get("behavior", {}))

        # Integration string fields
        for key in ("chatnexo_base_url", "chatnexo_api_key", "hubla_webhook_secret",
                    "cademi_api_url", "cademi_api_key", "openai_api_key", "meta_api_key"):
            val: str | None = getattr(patch, key)
            if _should_skip(val):
                continue
            assert val is not None
            i[key] = _encrypt(self.fernet, val) if key in _SENSITIVE else val

        # Integration numeric fields
        if patch.cademi_max_retries is not None:
            i["cademi_max_retries"] = patch.cademi_max_retries
        if patch.cademi_retry_base_seconds is not None:
            i["cademi_retry_base_seconds"] = patch.cademi_retry_base_seconds

        # Behavior fields
        for key in ("idle_ping_minutes", "idle_close_minutes", "intent_confidence_threshold",
                    "message_buffer_wait_seconds", "refund_deadline_days", "welcome_d1_delay_hours",
                    "loja_express_d1_delay_hours", "loja_express_d3_delay_hours",
                    "loja_express_d5_delay_hours", "loja_express_d7_delay_hours"):
            val_any = getattr(patch, key)
            if val_any is not None:
                b[key] = val_any

        current["integration"] = i
        current["behavior"] = b
        model.settings = current
        await self.session.flush()

        return await self.get(account_id=1)
```

- [ ] **Rodar os testes**

```bash
cd apps/api && uv run pytest tests/unit/adapters/test_account_config_repo.py -v
```

Esperado: todos passam.

- [ ] **Criar `apps/api/tests/unit/adapters/__init__.py`** (se não existir)

```bash
touch apps/api/tests/unit/adapters/__init__.py
```

- [ ] **Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/account_config_repo.py \
        apps/api/tests/unit/adapters/test_account_config_repo.py \
        apps/api/tests/unit/adapters/__init__.py
git commit -m "feat(settings): AccountConfigRepository com criptografia Fernet e overlay de env vars"
```

---

## Task 3: Extrair _require_admin para admin_auth.py (DRY)

**Files:**
- Create: `apps/api/src/interface/http/deps/admin_auth.py`
- Modify: `apps/api/src/interface/http/routers/admin/api_tokens.py`

O `_require_admin` está duplicado entre `api_tokens.py` e `admin_deps.py`. Extrair para um local compartilhado.

- [ ] **Criar admin_auth.py**

```python
# apps/api/src/interface/http/deps/admin_auth.py
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Cookie, Header, HTTPException, status
from jose import JWTError

from shared.adapters.kb.jwt_handler import verify_token
from shared.config.settings import get_settings


@dataclass
class AdminAuth:
    account_id: int
    user_email: str
    user_role: str


async def require_admin(
    authorization: str | None = Header(default=None),
    nexoia_token: str | None = Cookie(default=None),
) -> AdminAuth:
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
    settings = get_settings()
    try:
        payload = verify_token(token, secret=settings.jwt_secret)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return AdminAuth(
        account_id=payload["account_id"],
        user_email=payload["sub"],
        user_role=payload.get("role", "viewer"),
    )
```

- [ ] **Verificar se `apps/api/src/interface/http/deps/__init__.py` existe**

```bash
ls apps/api/src/interface/http/deps/
```

Se não tiver `__init__.py`: `touch apps/api/src/interface/http/deps/__init__.py`

- [ ] **Atualizar api_tokens.py para importar de admin_auth.py**

Em `apps/api/src/interface/http/routers/admin/api_tokens.py`, substituir as definições locais de `AdminAuth` e `_require_admin` por imports:

```python
# Remover as definições locais de AdminAuth e _require_admin
# Adicionar no topo dos imports:
from interface.http.deps.admin_auth import AdminAuth, require_admin as _require_admin
```

O arquivo final dos imports deve ficar:

```python
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from interface.http.deps.admin_auth import AdminAuth, require_admin as _require_admin
from shared.adapters.db.repositories.api_token_repo import ApiTokenRepository
from shared.adapters.db.session import session_scope

router = APIRouter(tags=["admin-api-tokens"])
```

(Remover: `from fastapi import Cookie, Header` — não são mais necessários nesse arquivo. Remover imports `from jose`, `from shared.adapters.kb.jwt_handler`, `from shared.config.settings` que eram usados apenas pelo `_require_admin` local.)

- [ ] **Rodar os testes existentes para confirmar que não quebraram**

```bash
cd apps/api && uv run pytest tests/unit/interface/ -v
```

Esperado: todos passam (sem regressão).

- [ ] **Commit**

```bash
git add apps/api/src/interface/http/deps/admin_auth.py \
        apps/api/src/interface/http/deps/__init__.py \
        apps/api/src/interface/http/routers/admin/api_tokens.py
git commit -m "refactor(auth): extrair AdminAuth e require_admin para deps/admin_auth.py"
```

---

## Task 4: Use Cases GetAccountConfig e UpdateAccountConfig

**Files:**
- Create: `apps/api/src/shared/application/use_cases/admin/__init__.py`
- Create: `apps/api/src/shared/application/use_cases/admin/get_account_config.py`
- Create: `apps/api/src/shared/application/use_cases/admin/update_account_config.py`
- Create: `apps/api/tests/unit/application/admin/__init__.py`
- Create: `apps/api/tests/unit/application/admin/test_account_config_use_cases.py`

- [ ] **Escrever os testes primeiro**

```python
# apps/api/tests/unit/application/admin/test_account_config_use_cases.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.application.use_cases.admin.get_account_config import GetAccountConfig
from shared.application.use_cases.admin.update_account_config import UpdateAccountConfig
from shared.domain.entities.account_config import (
    AccountConfig,
    AccountConfigPatch,
    BehaviorConfig,
    IntegrationConfig,
)


def _make_config() -> AccountConfig:
    return AccountConfig(
        integration=IntegrationConfig(
            chatnexo_base_url="http://nexo",
            chatnexo_api_key="key",
            hubla_webhook_secret="secret",
            cademi_api_url="",
            cademi_api_key="",
            cademi_max_retries=3,
            cademi_retry_base_seconds=1.0,
            openai_api_key="sk-test",
            meta_api_key="meta",
        ),
        behavior=BehaviorConfig(
            idle_ping_minutes=30,
            idle_close_minutes=20,
            intent_confidence_threshold=0.7,
            message_buffer_wait_seconds=0,
            refund_deadline_days=7,
            welcome_d1_delay_hours=24,
            loja_express_d1_delay_hours=24,
            loja_express_d3_delay_hours=72,
            loja_express_d5_delay_hours=120,
            loja_express_d7_delay_hours=168,
        ),
    )


@pytest.mark.asyncio
async def test_get_account_config_returns_config():
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=_make_config())

    uc = GetAccountConfig(repo=repo)
    config = await uc.execute(account_id=1)

    assert config.integration.chatnexo_base_url == "http://nexo"
    repo.get.assert_called_once_with(account_id=1)


@pytest.mark.asyncio
async def test_update_account_config_delegates_to_repo():
    config = _make_config()
    repo = AsyncMock()
    repo.update = AsyncMock(return_value=config)

    uc = UpdateAccountConfig(repo=repo)
    patch = AccountConfigPatch(idle_ping_minutes=45)
    result = await uc.execute(account_id=1, patch=patch)

    assert result is config
    repo.update.assert_called_once_with(account_id=1, patch=patch)


@pytest.mark.asyncio
async def test_update_rejects_invalid_confidence_threshold():
    repo = AsyncMock()
    uc = UpdateAccountConfig(repo=repo)

    with pytest.raises(ValueError, match="intent_confidence_threshold"):
        await uc.execute(account_id=1, patch=AccountConfigPatch(intent_confidence_threshold=1.5))

    repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_update_rejects_negative_max_retries():
    repo = AsyncMock()
    uc = UpdateAccountConfig(repo=repo)

    with pytest.raises(ValueError, match="cademi_max_retries"):
        await uc.execute(account_id=1, patch=AccountConfigPatch(cademi_max_retries=-1))

    repo.update.assert_not_called()
```

- [ ] **Rodar para confirmar que falham**

```bash
cd apps/api && uv run pytest tests/unit/application/admin/ -v
```

- [ ] **Criar os package markers**

```bash
touch apps/api/src/shared/application/use_cases/admin/__init__.py
touch apps/api/tests/unit/application/admin/__init__.py
```

- [ ] **Implementar GetAccountConfig**

```python
# apps/api/src/shared/application/use_cases/admin/get_account_config.py
from __future__ import annotations

from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
from shared.domain.entities.account_config import AccountConfig


class GetAccountConfig:
    def __init__(self, repo: AccountConfigRepository) -> None:
        self._repo = repo

    async def execute(self, account_id: int) -> AccountConfig:
        return await self._repo.get(account_id=account_id)
```

- [ ] **Implementar UpdateAccountConfig**

```python
# apps/api/src/shared/application/use_cases/admin/update_account_config.py
from __future__ import annotations

from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
from shared.domain.entities.account_config import AccountConfig, AccountConfigPatch


class UpdateAccountConfig:
    def __init__(self, repo: AccountConfigRepository) -> None:
        self._repo = repo

    async def execute(self, account_id: int, patch: AccountConfigPatch) -> AccountConfig:
        self._validate(patch)
        return await self._repo.update(account_id=account_id, patch=patch)

    def _validate(self, patch: AccountConfigPatch) -> None:
        if patch.intent_confidence_threshold is not None:
            if not 0.0 <= patch.intent_confidence_threshold <= 1.0:
                raise ValueError(
                    "intent_confidence_threshold deve estar entre 0.0 e 1.0"
                )
        if patch.cademi_max_retries is not None and patch.cademi_max_retries < 0:
            raise ValueError("cademi_max_retries não pode ser negativo")
```

- [ ] **Rodar os testes**

```bash
cd apps/api && uv run pytest tests/unit/application/admin/ -v
```

Esperado: todos passam.

- [ ] **Commit**

```bash
git add apps/api/src/shared/application/use_cases/admin/ \
        apps/api/tests/unit/application/admin/
git commit -m "feat(settings): use cases GetAccountConfig e UpdateAccountConfig"
```

---

## Task 5: Schemas Pydantic e Router HTTP

**Files:**
- Create: `apps/api/src/interface/http/schemas/admin_settings.py`
- Create: `apps/api/src/interface/http/routers/admin/settings.py`
- Create: `apps/api/tests/unit/interface/admin/test_settings_router.py`

- [ ] **Verificar se `apps/api/src/interface/http/schemas/` existe**

```bash
ls apps/api/src/interface/http/schemas/ 2>/dev/null || mkdir -p apps/api/src/interface/http/schemas && touch apps/api/src/interface/http/schemas/__init__.py
```

- [ ] **Escrever os testes primeiro**

```python
# apps/api/tests/unit/interface/admin/test_settings_router.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.deps.admin_auth import AdminAuth, require_admin
from interface.http.routers.admin import settings as settings_router
from shared.domain.entities.account_config import (
    AccountConfig,
    BehaviorConfig,
    IntegrationConfig,
)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(settings_router.router, prefix="/admin")
    return app


def _auth_override() -> AdminAuth:
    return AdminAuth(account_id=1, user_email="admin@test.com", user_role="admin")


def _make_config() -> AccountConfig:
    return AccountConfig(
        integration=IntegrationConfig(
            chatnexo_base_url="http://chatnexo",
            chatnexo_api_key="sk-chatnexo-key",
            hubla_webhook_secret="hubla-secret",
            cademi_api_url="http://cademi",
            cademi_api_key="cademi-key",
            cademi_max_retries=3,
            cademi_retry_base_seconds=1.0,
            openai_api_key="sk-proj-openai-key",
            meta_api_key="meta-key",
        ),
        behavior=BehaviorConfig(
            idle_ping_minutes=30,
            idle_close_minutes=20,
            intent_confidence_threshold=0.7,
            message_buffer_wait_seconds=0,
            refund_deadline_days=7,
            welcome_d1_delay_hours=24,
            loja_express_d1_delay_hours=24,
            loja_express_d3_delay_hours=72,
            loja_express_d5_delay_hours=120,
            loja_express_d7_delay_hours=168,
        ),
    )


def test_get_settings_returns_masked_api_keys():
    app = _make_app()
    app.dependency_overrides[require_admin] = _auth_override
    client = TestClient(app)

    with (
        patch("interface.http.routers.admin.settings.session_scope") as mock_scope,
        patch("interface.http.routers.admin.settings.AccountConfigRepository") as MockRepo,
        patch("interface.http.routers.admin.settings.GetAccountConfig") as MockUC,
        patch("interface.http.routers.admin.settings.get_settings") as mock_settings,
    ):
        mock_settings.return_value.integration_credentials_key = "x" * 44
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        uc_instance = AsyncMock()
        uc_instance.execute = AsyncMock(return_value=_make_config())
        MockUC.return_value = uc_instance

        r = client.get("/admin/settings")

    assert r.status_code == 200
    data = r.json()
    # API keys devem estar mascaradas
    assert "****" in data["chatnexo_api_key"]
    assert "****" in data["openai_api_key"]
    # URLs não mascaradas
    assert data["chatnexo_base_url"] == "http://chatnexo"
    # Campos de comportamento presentes
    assert data["idle_ping_minutes"] == 30


def test_put_settings_accepts_partial_patch():
    app = _make_app()
    app.dependency_overrides[require_admin] = _auth_override
    client = TestClient(app)

    with (
        patch("interface.http.routers.admin.settings.session_scope") as mock_scope,
        patch("interface.http.routers.admin.settings.AccountConfigRepository"),
        patch("interface.http.routers.admin.settings.UpdateAccountConfig") as MockUC,
        patch("interface.http.routers.admin.settings.get_settings") as mock_settings,
    ):
        mock_settings.return_value.integration_credentials_key = "x" * 44
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        uc_instance = AsyncMock()
        uc_instance.execute = AsyncMock(return_value=_make_config())
        MockUC.return_value = uc_instance

        r = client.put("/admin/settings", json={"idle_ping_minutes": 45})

    assert r.status_code == 200
    # Confirmar que execute foi chamado com o patch
    call_args = uc_instance.execute.call_args
    assert call_args.kwargs["patch"].idle_ping_minutes == 45


def test_put_settings_returns_422_for_invalid_threshold():
    app = _make_app()
    app.dependency_overrides[require_admin] = _auth_override
    client = TestClient(app)

    with (
        patch("interface.http.routers.admin.settings.session_scope") as mock_scope,
        patch("interface.http.routers.admin.settings.AccountConfigRepository"),
        patch("interface.http.routers.admin.settings.UpdateAccountConfig") as MockUC,
        patch("interface.http.routers.admin.settings.get_settings") as mock_settings,
    ):
        mock_settings.return_value.integration_credentials_key = "x" * 44
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        uc_instance = AsyncMock()
        uc_instance.execute.side_effect = ValueError("intent_confidence_threshold deve estar entre 0.0 e 1.0")
        MockUC.return_value = uc_instance

        r = client.put("/admin/settings", json={"intent_confidence_threshold": 2.0})

    assert r.status_code == 422


def test_get_settings_returns_401_without_auth():
    app = _make_app()
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/admin/settings")
    assert r.status_code == 401
```

- [ ] **Rodar para confirmar que falham**

```bash
cd apps/api && uv run pytest tests/unit/interface/admin/test_settings_router.py -v
```

- [ ] **Criar schemas Pydantic**

```python
# apps/api/src/interface/http/schemas/admin_settings.py
from __future__ import annotations

from pydantic import BaseModel


class AccountSettingsResponse(BaseModel):
    # Integrações
    chatnexo_base_url: str
    chatnexo_api_key: str
    hubla_webhook_secret: str
    cademi_api_url: str
    cademi_api_key: str
    cademi_max_retries: int
    cademi_retry_base_seconds: float
    openai_api_key: str
    meta_api_key: str
    # Comportamento
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


class AccountSettingsUpdateRequest(BaseModel):
    # Integrações
    chatnexo_base_url: str | None = None
    chatnexo_api_key: str | None = None
    hubla_webhook_secret: str | None = None
    cademi_api_url: str | None = None
    cademi_api_key: str | None = None
    cademi_max_retries: int | None = None
    cademi_retry_base_seconds: float | None = None
    openai_api_key: str | None = None
    meta_api_key: str | None = None
    # Comportamento
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

- [ ] **Criar o router de settings**

```python
# apps/api/src/interface/http/routers/admin/settings.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from cryptography.fernet import Fernet

from interface.http.deps.admin_auth import AdminAuth, require_admin
from interface.http.schemas.admin_settings import (
    AccountSettingsResponse,
    AccountSettingsUpdateRequest,
)
from shared.adapters.db.repositories.account_config_repo import (
    AccountConfigRepository,
    _mask,
)
from shared.adapters.db.session import session_scope
from shared.application.use_cases.admin.get_account_config import GetAccountConfig
from shared.application.use_cases.admin.update_account_config import UpdateAccountConfig
from shared.config.settings import get_settings
from shared.domain.entities.account_config import AccountConfig, AccountConfigPatch

router = APIRouter(tags=["admin-settings"])


def _to_response(config: AccountConfig) -> AccountSettingsResponse:
    i = config.integration
    b = config.behavior
    return AccountSettingsResponse(
        chatnexo_base_url=i.chatnexo_base_url,
        chatnexo_api_key=_mask(i.chatnexo_api_key),
        hubla_webhook_secret=_mask(i.hubla_webhook_secret),
        cademi_api_url=i.cademi_api_url,
        cademi_api_key=_mask(i.cademi_api_key),
        cademi_max_retries=i.cademi_max_retries,
        cademi_retry_base_seconds=i.cademi_retry_base_seconds,
        openai_api_key=_mask(i.openai_api_key),
        meta_api_key=_mask(i.meta_api_key),
        idle_ping_minutes=b.idle_ping_minutes,
        idle_close_minutes=b.idle_close_minutes,
        intent_confidence_threshold=b.intent_confidence_threshold,
        message_buffer_wait_seconds=b.message_buffer_wait_seconds,
        refund_deadline_days=b.refund_deadline_days,
        welcome_d1_delay_hours=b.welcome_d1_delay_hours,
        loja_express_d1_delay_hours=b.loja_express_d1_delay_hours,
        loja_express_d3_delay_hours=b.loja_express_d3_delay_hours,
        loja_express_d5_delay_hours=b.loja_express_d5_delay_hours,
        loja_express_d7_delay_hours=b.loja_express_d7_delay_hours,
    )


@router.get("/settings", response_model=AccountSettingsResponse)
async def get_settings_endpoint(
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> AccountSettingsResponse:
    s = get_settings()
    fernet = Fernet(s.integration_credentials_key.encode())
    async with session_scope() as session:
        repo = AccountConfigRepository(session=session, fernet=fernet)
        uc = GetAccountConfig(repo=repo)
        config = await uc.execute(account_id=auth.account_id)
    return _to_response(config)


@router.put("/settings", response_model=AccountSettingsResponse)
async def update_settings_endpoint(
    body: AccountSettingsUpdateRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> AccountSettingsResponse:
    s = get_settings()
    fernet = Fernet(s.integration_credentials_key.encode())
    patch = AccountConfigPatch(
        chatnexo_base_url=body.chatnexo_base_url,
        chatnexo_api_key=body.chatnexo_api_key,
        hubla_webhook_secret=body.hubla_webhook_secret,
        cademi_api_url=body.cademi_api_url,
        cademi_api_key=body.cademi_api_key,
        cademi_max_retries=body.cademi_max_retries,
        cademi_retry_base_seconds=body.cademi_retry_base_seconds,
        openai_api_key=body.openai_api_key,
        meta_api_key=body.meta_api_key,
        idle_ping_minutes=body.idle_ping_minutes,
        idle_close_minutes=body.idle_close_minutes,
        intent_confidence_threshold=body.intent_confidence_threshold,
        message_buffer_wait_seconds=body.message_buffer_wait_seconds,
        refund_deadline_days=body.refund_deadline_days,
        welcome_d1_delay_hours=body.welcome_d1_delay_hours,
        loja_express_d1_delay_hours=body.loja_express_d1_delay_hours,
        loja_express_d3_delay_hours=body.loja_express_d3_delay_hours,
        loja_express_d5_delay_hours=body.loja_express_d5_delay_hours,
        loja_express_d7_delay_hours=body.loja_express_d7_delay_hours,
    )
    try:
        async with session_scope() as session:
            repo = AccountConfigRepository(session=session, fernet=fernet)
            uc = UpdateAccountConfig(repo=repo)
            config = await uc.execute(account_id=auth.account_id, patch=patch)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _to_response(config)
```

- [ ] **Rodar os testes**

```bash
cd apps/api && uv run pytest tests/unit/interface/admin/test_settings_router.py -v
```

Esperado: todos passam.

- [ ] **Commit**

```bash
git add apps/api/src/interface/http/schemas/ \
        apps/api/src/interface/http/routers/admin/settings.py \
        apps/api/tests/unit/interface/admin/test_settings_router.py
git commit -m "feat(settings): schemas Pydantic e router GET/PUT /admin/settings"
```

---

## Task 6: Registrar router em main.py

**Files:**
- Modify: `apps/api/src/main.py`

- [ ] **Adicionar import e registro**

Em `apps/api/src/main.py`, adicionar após os outros imports de admin:

```python
from interface.http.routers.admin import settings as admin_settings
```

E no `create_app()`, após a linha `app.include_router(admin_dlq.router, prefix="/admin")`:

```python
app.include_router(admin_settings.router, prefix="/admin")
```

- [ ] **Verificar que a app sobe sem erros**

```bash
cd apps/api && uv run uvicorn nexoia.main:app --port 8001 &
sleep 3 && curl -s http://localhost:8001/health | python3 -c "import sys,json; print(json.load(sys.stdin))"
kill %1
```

Esperado: resposta de health com status ok (sem erros de import).

- [ ] **Commit**

```bash
git add apps/api/src/main.py
git commit -m "feat(settings): registrar router /admin/settings no app"
```

---

## Task 7: from_account_config() nos adapters ChatNexo e Cademi

**Files:**
- Modify: `apps/api/src/shared/adapters/chatnexo/client.py`
- Modify: `apps/api/src/shared/adapters/cademi/client.py`

- [ ] **Adicionar from_account_config() no ChatNexoClient**

Em `apps/api/src/shared/adapters/chatnexo/client.py`, adicionar após `from_settings()`:

```python
    @classmethod
    def from_account_config(cls, config: "AccountConfig") -> ChatNexoClient:
        from shared.domain.entities.account_config import AccountConfig  # evitar import circular
        client = httpx.AsyncClient(
            base_url=config.integration.chatnexo_base_url,
            headers={"X-Api-Key": config.integration.chatnexo_api_key},
            timeout=httpx.Timeout(10.0, connect=3.0),
        )
        return cls(http=client)
```

O import `AccountConfig` deve ser feito no topo do arquivo (não inline), como:

```python
from __future__ import annotations
# outros imports existentes...
from shared.domain.entities.account_config import AccountConfig
```

Verificar se não há import circular. Se houver, usar TYPE_CHECKING:

```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from shared.domain.entities.account_config import AccountConfig
```

O método `from_account_config` com `from __future__ import annotations` funciona mesmo com TYPE_CHECKING.

- [ ] **Adicionar from_account_config() no CademiClient**

Em `apps/api/src/shared/adapters/cademi/client.py`, adicionar factory method:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from shared.domain.ports.cademi_port import CademiStudent

if TYPE_CHECKING:
    from shared.domain.entities.account_config import AccountConfig


class CademiClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url
        self._api_key = api_key

    @classmethod
    def from_account_config(cls, config: AccountConfig) -> CademiClient:
        return cls(
            base_url=config.integration.cademi_api_url,
            api_key=config.integration.cademi_api_key,
        )

    async def get_student_by_email(self, email: str) -> CademiStudent | None:
        raise NotImplementedError("CademiClient não implementado — ver OPEN_QUESTIONS.md#CQ-W01")

    async def get_student_by_cpf(self, cpf: str) -> CademiStudent | None:
        raise NotImplementedError("CademiClient não implementado — ver OPEN_QUESTIONS.md#CQ-W01")

    async def get_student_by_name_phone(self, name: str, phone: str) -> CademiStudent | None:
        raise NotImplementedError("CademiClient não implementado — ver OPEN_QUESTIONS.md#CQ-W01")

    async def get_access_link(self, student_id: str, product_id: str) -> str:
        raise NotImplementedError("CademiClient não implementado — ver OPEN_QUESTIONS.md#CQ-W01")
```

- [ ] **Rodar testes gerais para confirmar ausência de regressão**

```bash
cd apps/api && uv run pytest tests/unit/ -v --tb=short
```

Esperado: todos os testes existentes passam.

- [ ] **Commit**

```bash
git add apps/api/src/shared/adapters/chatnexo/client.py \
        apps/api/src/shared/adapters/cademi/client.py
git commit -m "feat(settings): from_account_config() em ChatNexoClient e CademiClient"
```

---

## Task 8: Worker carrega AccountConfig do DB

**Files:**
- Modify: `apps/api/src/interface/worker/handlers/message.py`

- [ ] **Atualizar _process_message para usar AccountConfig**

Substituir o conteúdo de `_process_message` em `apps/api/src/interface/worker/handlers/message.py`:

```python
async def _process_message(
    *,
    account_id: int,
    phone: str,
    conversation_id: int,
    text: str,
) -> None:
    settings = get_settings()
    redis = get_redis()

    fernet = Fernet(settings.integration_credentials_key.encode())

    async with session_scope() as session:
        # Carregar config da conta do DB (com fallback para env vars)
        config_repo = AccountConfigRepository(session=session, fernet=fernet)
        account_config = await config_repo.get(account_id=account_id)

        openai_client = AsyncOpenAI(api_key=account_config.integration.openai_api_key)
        chatnexo = ChatNexoClient.from_account_config(account_config)
        cademi = CademiClient.from_account_config(account_config)
        hubla = HublaClient()
        refund_mutex = RedisRefundMutex(redis, ttl_seconds=settings.refund_mutex_ttl_seconds)

        knowledge_repo = EmbeddingsKnowledgeAdapter(
            chunk_repo=ChunkRepository(session),
            openai_client=openai_client,
            embedding_model=settings.kb_embedding_model,
        )
        adapters = Adapters(
            access_repo=AccessCaseRepository(session),
            cademi=cademi,
            chatnexo=chatnexo,
            refund_repo=RefundCaseRepository(session),
            hubla=hubla,
            legal_history=_NullLegalHistory(),
            refund_mutex=refund_mutex,
            knowledge_repo=knowledge_repo,
            usage_log_repo=UsageLogRepository(session),
        )
        registry = build_registry(adapters)
        guard_service = GuardService([LegalMentionGuard(), LoopDetectorGuard()])

        ctx = AgentContext(
            account_id=str(account_id),
            phone=phone,
            conversation_id=str(conversation_id),
            thread_id=f"{account_id}:{phone}",
        )
        reply = await run_agent(
            ctx=ctx,
            user_message=text,
            registry=registry,
            session=session,
            client=openai_client,
            guard_service=guard_service,
        )

    await chatnexo.send_message(
        account_id=account_id,
        conversation_id=conversation_id,
        text=reply,
    )
    log.info("message_reply_sent", account_id=account_id, conversation_id=conversation_id)
```

Adicionar os imports necessários no topo do arquivo:

```python
from cryptography.fernet import Fernet

from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
```

- [ ] **Rodar testes de unit do worker (se existirem)**

```bash
cd apps/api && uv run pytest tests/ -k "message" -v --tb=short
```

- [ ] **Commit**

```bash
git add apps/api/src/interface/worker/handlers/message.py
git commit -m "feat(settings): worker carrega AccountConfig do DB via AccountConfigRepository"
```

---

## Task 9: Frontend — tipos TypeScript e funções de API

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/features/settings/types.ts`

- [ ] **Criar types.ts**

```typescript
// apps/web/src/features/settings/types.ts

export interface AccountSettings {
  // Integrações
  chatnexo_base_url: string;
  chatnexo_api_key: string;
  hubla_webhook_secret: string;
  cademi_api_url: string;
  cademi_api_key: string;
  cademi_max_retries: number;
  cademi_retry_base_seconds: number;
  openai_api_key: string;
  meta_api_key: string;
  // Comportamento
  idle_ping_minutes: number;
  idle_close_minutes: number;
  intent_confidence_threshold: number;
  message_buffer_wait_seconds: number;
  refund_deadline_days: number;
  welcome_d1_delay_hours: number;
  loja_express_d1_delay_hours: number;
  loja_express_d3_delay_hours: number;
  loja_express_d5_delay_hours: number;
  loja_express_d7_delay_hours: number;
}

export type AccountSettingsPatch = Partial<AccountSettings>;
```

- [ ] **Adicionar getAccountSettings e updateAccountSettings em api.ts**

Adicionar ao final de `apps/web/src/lib/api.ts`:

```typescript
// ─── Account Settings ─────────────────────────────────────────────────────────

import type { AccountSettings, AccountSettingsPatch } from "@/features/settings/types";

export async function getAccountSettings(): Promise<AccountSettings> {
  return apiFetch<AccountSettings>("/admin/settings");
}

export async function updateAccountSettings(
  patch: AccountSettingsPatch,
): Promise<AccountSettings> {
  return apiFetch<AccountSettings>("/admin/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}
```

- [ ] **Commit**

```bash
git add apps/web/src/features/settings/types.ts apps/web/src/lib/api.ts
git commit -m "feat(settings): tipos TypeScript e funções de API para configurações"
```

---

## Task 10: Frontend — IntegrationSection

**Files:**
- Create: `apps/web/src/features/settings/components/IntegrationSection.tsx`

- [ ] **Criar o componente**

```tsx
// apps/web/src/features/settings/components/IntegrationSection.tsx
"use client";

import { useState } from "react";
import { updateAccountSettings } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import type { AccountSettings, AccountSettingsPatch } from "@/features/settings/types";

interface FieldConfig {
  key: keyof AccountSettings;
  label: string;
  type: "text" | "secret" | "url" | "number";
  placeholder?: string;
}

const FIELDS: FieldConfig[] = [
  { key: "chatnexo_base_url", label: "ChatNexo URL", type: "url", placeholder: "http://..." },
  { key: "chatnexo_api_key", label: "ChatNexo API Key", type: "secret" },
  { key: "hubla_webhook_secret", label: "Hubla Webhook Secret", type: "secret" },
  { key: "cademi_api_url", label: "Cademi API URL", type: "url", placeholder: "http://..." },
  { key: "cademi_api_key", label: "Cademi API Key", type: "secret" },
  { key: "cademi_max_retries", label: "Cademi Max Retries", type: "number" },
  { key: "cademi_retry_base_seconds", label: "Cademi Retry Base (s)", type: "number" },
  { key: "openai_api_key", label: "OpenAI API Key", type: "secret" },
  { key: "meta_api_key", label: "Meta API Key", type: "secret" },
];

interface Props {
  initial: AccountSettings;
  onSaved: (updated: AccountSettings) => void;
}

export function IntegrationSection({ initial, onSaved }: Props) {
  const toast = useToast();
  const [editing, setEditing] = useState<Set<keyof AccountSettings>>(new Set());
  const [values, setValues] = useState<Partial<AccountSettings>>({});
  const [saving, setSaving] = useState(false);

  function startEdit(key: keyof AccountSettings) {
    setEditing((prev) => new Set([...prev, key]));
    setValues((prev) => ({ ...prev, [key]: "" }));
  }

  function cancelEdit(key: keyof AccountSettings) {
    setEditing((prev) => {
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
    setValues((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  function handleChange(key: keyof AccountSettings, value: string | number) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    if (Object.keys(values).length === 0) return;
    setSaving(true);
    try {
      const patch: AccountSettingsPatch = { ...values };
      const updated = await updateAccountSettings(patch);
      onSaved(updated);
      setEditing(new Set());
      setValues({});
      toast.success("Integrações salvas com sucesso.");
    } catch {
      toast.error("Erro ao salvar configurações.");
    } finally {
      setSaving(false);
    }
  }

  function displayValue(field: FieldConfig): string {
    const current = initial[field.key];
    if (field.type === "number") return String(current);
    return String(current);
  }

  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-low p-6">
      <h2 className="text-h2 font-sans font-semibold text-on-surface mb-1">Integrações</h2>
      <p className="text-body-sm text-on-surface-variant mb-6">
        Credenciais de acesso aos serviços externos. Campos de chave exibem valor mascarado.
      </p>

      <div className="space-y-4">
        {FIELDS.map((field) => {
          const isEditing = editing.has(field.key);
          const isSecret = field.type === "secret";

          return (
            <div key={field.key} className="flex flex-col gap-1">
              <label className="text-label-sm font-sans text-on-surface-variant">
                {field.label}
              </label>
              <div className="flex gap-2">
                {isEditing ? (
                  <>
                    <input
                      type={isSecret ? "password" : field.type === "number" ? "number" : "text"}
                      step={field.key === "cademi_retry_base_seconds" ? "0.1" : undefined}
                      value={String(values[field.key] ?? "")}
                      onChange={(e) =>
                        handleChange(
                          field.key,
                          field.type === "number" ? Number(e.target.value) : e.target.value,
                        )
                      }
                      placeholder={isSecret ? "Digite o novo valor" : field.placeholder}
                      className="flex-1 rounded-lg border border-outline bg-surface-container px-3 py-2 text-body-sm text-on-surface placeholder:text-on-surface-variant/50 focus:border-primary focus:outline-none"
                      autoFocus
                    />
                    <button
                      type="button"
                      onClick={() => cancelEdit(field.key)}
                      className="rounded-lg border border-outline-variant px-3 py-2 text-label-sm text-on-surface-variant hover:bg-surface-container transition-colors"
                    >
                      Cancelar
                    </button>
                  </>
                ) : (
                  <>
                    <div className="flex-1 rounded-lg border border-outline-variant bg-surface-container px-3 py-2 text-body-sm text-on-surface-variant font-mono">
                      {displayValue(field)}
                    </div>
                    <button
                      type="button"
                      onClick={() => startEdit(field.key)}
                      className="flex items-center gap-1.5 rounded-lg border border-outline-variant px-3 py-2 text-label-sm text-on-surface hover:bg-surface-container transition-colors"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                        edit
                      </span>
                      Editar
                    </button>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {editing.size > 0 && (
        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-label-sm font-sans font-semibold text-on-primary hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {saving ? (
              <>
                <span className="material-symbols-outlined animate-spin" style={{ fontSize: "16px" }}>
                  progress_activity
                </span>
                Salvando...
              </>
            ) : (
              <>
                <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                  save
                </span>
                Salvar Integrações
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Commit**

```bash
git add apps/web/src/features/settings/components/IntegrationSection.tsx
git commit -m "feat(settings): componente IntegrationSection com edição inline de API keys"
```

---

## Task 11: Frontend — BehaviorSection

**Files:**
- Create: `apps/web/src/features/settings/components/BehaviorSection.tsx`

- [ ] **Criar o componente**

```tsx
// apps/web/src/features/settings/components/BehaviorSection.tsx
"use client";

import { useState } from "react";
import { updateAccountSettings } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import type { AccountSettings, AccountSettingsPatch } from "@/features/settings/types";

interface FieldConfig {
  key: keyof AccountSettings;
  label: string;
  description: string;
  min?: number;
  max?: number;
  step?: number;
}

const FIELDS: FieldConfig[] = [
  { key: "idle_ping_minutes", label: "Ping de inatividade (min)", description: "Minutos sem atividade para enviar ping ao contato", min: 1 },
  { key: "idle_close_minutes", label: "Fechar conversa inativa (min)", description: "Minutos sem atividade para encerrar a conversa", min: 1 },
  { key: "intent_confidence_threshold", label: "Limiar de confiança do agente", description: "Valor entre 0 e 1. Abaixo disso, o agente escala para humano", min: 0, max: 1, step: 0.05 },
  { key: "message_buffer_wait_seconds", label: "Buffer de mensagens (s)", description: "Segundos para aguardar mais mensagens antes de processar", min: 0 },
  { key: "refund_deadline_days", label: "Prazo de reembolso (dias)", description: "Dias dentro do prazo CDC para oferecer reembolso", min: 1 },
  { key: "welcome_d1_delay_hours", label: "Follow-up D+1 de boas-vindas (h)", description: "Horas após a compra para enviar o lembrete de boas-vindas", min: 1 },
  { key: "loja_express_d1_delay_hours", label: "Loja Express D+1 (h)", description: "Horas após compra para o follow-up D+1", min: 1 },
  { key: "loja_express_d3_delay_hours", label: "Loja Express D+3 (h)", description: "Horas após compra para o follow-up D+3", min: 1 },
  { key: "loja_express_d5_delay_hours", label: "Loja Express D+5 (h)", description: "Horas após compra para o follow-up D+5", min: 1 },
  { key: "loja_express_d7_delay_hours", label: "Loja Express D+7 (h)", description: "Horas após compra para o follow-up D+7 (alerta crítico)", min: 1 },
];

interface Props {
  initial: AccountSettings;
  onSaved: (updated: AccountSettings) => void;
}

export function BehaviorSection({ initial, onSaved }: Props) {
  const toast = useToast();
  const [values, setValues] = useState<Partial<AccountSettings>>({});
  const [saving, setSaving] = useState(false);

  const hasChanges = Object.keys(values).length > 0;

  function handleChange(key: keyof AccountSettings, value: number) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    if (!hasChanges) return;
    setSaving(true);
    try {
      const patch: AccountSettingsPatch = { ...values };
      const updated = await updateAccountSettings(patch);
      onSaved(updated);
      setValues({});
      toast.success("Comportamento do agente salvo com sucesso.");
    } catch {
      toast.error("Erro ao salvar configurações.");
    } finally {
      setSaving(false);
    }
  }

  function currentValue(key: keyof AccountSettings): number {
    return (values[key] as number | undefined) ?? (initial[key] as number);
  }

  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-low p-6">
      <h2 className="text-h2 font-sans font-semibold text-on-surface mb-1">Comportamento do Agente</h2>
      <p className="text-body-sm text-on-surface-variant mb-6">
        Parâmetros que controlam timeouts, limiares e intervalos de follow-up.
      </p>

      <div className="space-y-5">
        {FIELDS.map((field) => (
          <div key={field.key} className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between">
              <label className="text-label-sm font-sans text-on-surface">
                {field.label}
              </label>
              <span className="text-mono-label font-mono text-primary">
                {currentValue(field.key)}
              </span>
            </div>
            <input
              type="number"
              min={field.min}
              max={field.max}
              step={field.step ?? 1}
              value={currentValue(field.key)}
              onChange={(e) => handleChange(field.key, Number(e.target.value))}
              className="w-full rounded-lg border border-outline bg-surface-container px-3 py-2 text-body-sm text-on-surface focus:border-primary focus:outline-none"
            />
            <p className="text-label-xs text-on-surface-variant">{field.description}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 flex justify-end">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !hasChanges}
          className="flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-label-sm font-sans font-semibold text-on-primary hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {saving ? (
            <>
              <span className="material-symbols-outlined animate-spin" style={{ fontSize: "16px" }}>
                progress_activity
              </span>
              Salvando...
            </>
          ) : (
            <>
              <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                save
              </span>
              Salvar Comportamento
            </>
          )}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Commit**

```bash
git add apps/web/src/features/settings/components/BehaviorSection.tsx
git commit -m "feat(settings): componente BehaviorSection com inputs numéricos"
```

---

## Task 12: Frontend — página /settings e Sidebar

**Files:**
- Create: `apps/web/src/app/settings/page.tsx`
- Modify: `apps/web/src/shared/components/layout/Sidebar.tsx`

- [ ] **Criar a página**

```tsx
// apps/web/src/app/settings/page.tsx
"use client";

import { useEffect, useState } from "react";
import { getAccountSettings } from "@/lib/api";
import { IntegrationSection } from "@/features/settings/components/IntegrationSection";
import { BehaviorSection } from "@/features/settings/components/BehaviorSection";
import type { AccountSettings } from "@/features/settings/types";

export default function SettingsPage() {
  const [settings, setSettings] = useState<AccountSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAccountSettings()
      .then(setSettings)
      .catch(() => setError("Não foi possível carregar as configurações."));
  }, []);

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center py-16">
        <div className="rounded-xl border border-error bg-error-container p-6 text-on-error-container">
          <span className="material-symbols-outlined text-error" style={{ fontSize: "24px" }}>
            error
          </span>
          <p className="mt-2 text-body-base">{error}</p>
        </div>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="flex flex-1 items-center justify-center py-16">
        <span
          className="material-symbols-outlined animate-spin text-on-surface-variant"
          style={{ fontSize: "32px" }}
        >
          progress_activity
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-h1 font-sans font-bold text-on-background">Configurações</h1>
        <p className="mt-1 text-body-base text-on-surface-variant">
          Credenciais de integração e parâmetros do agente. As alterações têm efeito imediato.
        </p>
      </div>

      <IntegrationSection initial={settings} onSaved={setSettings} />
      <BehaviorSection initial={settings} onSaved={setSettings} />
    </div>
  );
}
```

- [ ] **Adicionar item de Configurações na Sidebar**

Em `apps/web/src/shared/components/layout/Sidebar.tsx`, adicionar na `NAV_ITEMS`:

```typescript
const NAV_ITEMS = [
  { label: "Painel", href: "/dashboard", icon: "dashboard" },
  { label: "Base de Conhecimento", href: "/kb", icon: "database" },
  { label: "Contas", href: "/accounts", icon: "group" },
  { label: "Configurações", href: "/settings", icon: "settings" },
] as const;
```

- [ ] **Verificar se a rota /settings está acessível**

Subir o dev server e acessar `http://localhost:3000/settings`:

```bash
cd apps/web && npm run dev &
sleep 5
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/settings
```

Esperado: `200` (ou `307` redirect para login se autenticação interceptar).

- [ ] **Commit final**

```bash
git add apps/web/src/app/settings/page.tsx \
        apps/web/src/shared/components/layout/Sidebar.tsx
git commit -m "feat(settings): página /settings e item na Sidebar"
```

---

## Task 13: Atualizar docs

- [ ] **Atualizar INDEX.md**

Em `docs/superpowers/INDEX.md`, atualizar linha do subsistema ⑧:

```markdown
| ⑧ | **Account Settings** — página de configuração de credenciais e comportamento via UI | [spec](specs/2026-05-06-nexoia-account-settings-design.md) | [plano](plans/2026-05-06-nexoia-account-settings.md) | ✅ Concluído |
```

- [ ] **Commit**

```bash
git add docs/superpowers/INDEX.md
git commit -m "docs: marcar Account Settings como concluído no INDEX"
```

---

## Self-Review

**Cobertura do spec:**
- ✅ RF-S01: página /settings com dois grupos → Tasks 10, 11, 12
- ✅ RF-S02: Grupo A (integrações) → Task 10
- ✅ RF-S03: Grupo B (comportamento) → Task 11
- ✅ RF-S04: campos sensíveis mascarados, edição inline → Task 10
- ✅ RF-S05: ignorar valores com `****` → Task 2 (`_should_skip`)
- ✅ RF-S06: botão Salvar por seção, payload parcial → Tasks 10, 11
- ✅ RF-S07: toasts via useToast → Tasks 10, 11
- ✅ RF-S08: sidebar item → Task 12
- ✅ RF-S09: GET /admin/settings com mascaramento → Task 5
- ✅ RF-S10: fallback para env vars → Task 2

- ✅ RNF-S01: Fernet encryption → Task 2
- ✅ RNF-S02: sem migration → usa AccountModel.settings JSONB existente
- ✅ RNF-S03: JWT auth com require_admin → Tasks 3, 5
- ✅ RNF-S04: @dataclass com session: AsyncSession → Task 2
- ✅ RNF-S05: use cases injetados via __init__ → Task 4
- ✅ RNF-S06: from_account_config() ao lado de from_settings() → Task 7

**Consistência de tipos:**
- `AccountConfigPatch` definido em Task 1, usado em Tasks 2, 4, 5 — ✅
- `_mask()` definido em Task 2 (repositório), importado em Task 5 (router) — ✅
- `require_admin` definido em Task 3, importado em Tasks 5 e nos testes — ✅
- `AccountConfig` → `IntegrationConfig` + `BehaviorConfig` consistente em todos os tasks — ✅

**Placeholders:** nenhum encontrado — todo código é completo.
