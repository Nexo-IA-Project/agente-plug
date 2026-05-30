# Config de Plataforma (OpenAI/SMTP global) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Mover OpenAI (API key) e SMTP de config por-tenant para uma config GLOBAL de plataforma (`platform_config`, 1 linha), com backfill dos dados de produção, sem quebrar runtime, e tirá-los da tela de Settings do tenant.

**Architecture:** Nova tabela `platform_config` (singleton) guarda `openai_api_key` (Fernet) + SMTP (host/port/security/user/senha Fernet/from). `PlatformConfigRepository` lê/grava (reusa `integration_credentials_key`). OpenAI e o serviço de e-mail passam a ler do global (fallback `.env` p/ OpenAI). Migração faz backfill de `accounts.settings.integration.openai_api_key` + da linha de `smtp_config`, remove openai do `accounts.settings` e dropa `smtp_config`. Frontend tira OpenAI/SMTP do Settings do tenant e cria seção "Plataforma".

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Fernet (cryptography), aiosmtplib, pytest (testcontainers), Next.js 15.

**Spec:** `docs/superpowers/specs/2026-05-30-platform-config-core-design.md`
**Base:** branch `feat/platform-config-core` (já criada a partir da main com o #71).

**Não-objetivos:** painel super-admin (futuro — por ora a seção "Plataforma" fica visível ao admin atual); enforcement por permissão; mexer em config de tenant (ChatNexo/Meta/Hubla/Cademi/comportamento).

---

## Task 1: Model + migração `platform_config` (create + backfill + cleanup)

**Files:**
- Modify: `apps/api/src/shared/adapters/db/models.py` (novo `PlatformConfigModel`)
- Create: `apps/api/migrations/versions/<rev>_platform_config.py`
- Test: `apps/api/tests/integration/test_platform_config_migration.py`

- [ ] **Step 1: Model** em `models.py`:
```python
class PlatformConfigModel(Base):
    __tablename__ = "platform_config"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    singleton: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("TRUE"), unique=True)
    openai_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet
    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("TRUE"))
    smtp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_encrypted_password: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet
    smtp_from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_from_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("NOW()"), onupdate=sa_text("NOW()"), nullable=False)
```
(`singleton` unique garante 1 linha.)

- [ ] **Step 2: Migration** `<rev>_platform_config.py` (`down_revision` = `uv run alembic heads` → `a7b8c9d0e1f2`). `upgrade()`:
```python
def upgrade() -> None:
    import uuid as _uuid, json
    conn = op.get_bind()
    op.create_table(
        "platform_config",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("singleton", sa.Boolean(), nullable=False, server_default=sa.true(), unique=True),
        sa.Column("openai_api_key", sa.Text(), nullable=True),
        sa.Column("smtp_host", sa.String(255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=True),
        sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("smtp_username", sa.String(255), nullable=True),
        sa.Column("smtp_encrypted_password", sa.Text(), nullable=True),
        sa.Column("smtp_from_name", sa.String(255), nullable=True),
        sa.Column("smtp_from_email", sa.String(255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    # backfill OpenAI (de accounts.settings.integration.openai_api_key da 1ª conta) — blob Fernet copiado como está
    acc = conn.execute(sa.text("SELECT settings FROM accounts ORDER BY created_at LIMIT 1")).scalar()
    openai = None
    if acc:
        settings = acc if isinstance(acc, dict) else json.loads(acc)
        openai = (settings.get("integration") or {}).get("openai_api_key") or None
    # backfill SMTP (da única linha de smtp_config, se houver)
    smtp = conn.execute(sa.text(
        "SELECT host, port, use_tls, username, encrypted_password, from_name, from_email "
        "FROM smtp_config LIMIT 1")).mappings().first()
    pid = str(_uuid.uuid4())
    conn.execute(sa.text(
        "INSERT INTO platform_config (id, singleton, openai_api_key, smtp_host, smtp_port, smtp_use_tls, "
        "smtp_username, smtp_encrypted_password, smtp_from_name, smtp_from_email) "
        "VALUES (:id, TRUE, :ok, :h, :p, :tls, :u, :pw, :fn, :fe)"),
        {"id": pid, "ok": openai,
         "h": smtp["host"] if smtp else None, "p": smtp["port"] if smtp else None,
         "tls": smtp["use_tls"] if smtp else True, "u": smtp["username"] if smtp else None,
         "pw": smtp["encrypted_password"] if smtp else None,
         "fn": smtp["from_name"] if smtp else None, "fe": smtp["from_email"] if smtp else None})
    # remove openai_api_key do accounts.settings (todas as contas)
    conn.execute(sa.text(
        "UPDATE accounts SET settings = settings #- '{integration,openai_api_key}'"))
    # dropa smtp_config (dados já migrados; downgrade recria)
    op.drop_table("smtp_config")
```
`downgrade()`: recria `smtp_config` (copiar DDL de `b1c2d3e4f5a6` mas com `account_id UUID FK`), restaura a linha a partir de `platform_config` (account_id = primeira conta), e re-grava `openai_api_key` em `accounts.settings`; depois `op.drop_table("platform_config")`.

> NOTA executor: confirme o caminho JSONB real do openai em `accounts.settings` (provável `{integration: {openai_api_key}}` — ver `account_config_repo.get`). Ajuste o `#-` path. Em prod, `smtp_config` tem 1 linha e `accounts.settings.integration.openai_api_key` existe — valide o backfill com os dados reais (testcontainer não tem dados; validação real é no dev local/prod).

- [ ] **Step 3: Validar** `uv run alembic upgrade heads` (Postgres local) e o teste de integração (testcontainer cria tabela; backfill com dados=vazio não quebra). Confirmar `platform_config` existe e `smtp_config` foi dropada.
- [ ] **Step 4: Commit** `git commit -m "feat(platform): tabela platform_config + migração (backfill openai/smtp, dropa smtp_config)"`

---

## Task 2: PlatformConfig entity + PlatformConfigRepository

**Files:**
- Create: `apps/api/src/shared/domain/entities/platform_config.py`, `apps/api/src/shared/adapters/db/repositories/platform_config_repo.py`
- Test: `apps/api/tests/integration/test_platform_config_repo.py`

- [ ] **Step 1: Entity** `platform_config.py`:
```python
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class PlatformConfig:
    openai_api_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_use_tls: bool = True
    smtp_username: str | None = None
    smtp_encrypted_password: str | None = None
    smtp_from_name: str | None = None
    smtp_from_email: str | None = None
```

- [ ] **Step 2: Repo** `platform_config_repo.py` — reusa `integration_credentials_key` p/ Fernet (espelhe `smtp_config_repo.py`):
```python
from __future__ import annotations
import uuid
from dataclasses import dataclass
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.adapters.db.models import PlatformConfigModel
from shared.config.settings import get_settings
from shared.domain.entities.platform_config import PlatformConfig


@dataclass
class PlatformConfigRepository:
    session: AsyncSession

    def _fernet(self) -> Fernet:
        k = get_settings().integration_credentials_key
        return Fernet(k.encode() if isinstance(k, str) else k)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet().encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str | None) -> str | None:
        if not token:
            return None
        return self._fernet().decrypt(token.encode()).decode()

    async def get(self) -> PlatformConfig:
        m = (await self.session.execute(select(PlatformConfigModel).limit(1))).scalar_one_or_none()
        if m is None:
            return PlatformConfig()
        return PlatformConfig(
            openai_api_key=m.openai_api_key, smtp_host=m.smtp_host, smtp_port=m.smtp_port,
            smtp_use_tls=m.smtp_use_tls, smtp_username=m.smtp_username,
            smtp_encrypted_password=m.smtp_encrypted_password,
            smtp_from_name=m.smtp_from_name, smtp_from_email=m.smtp_from_email,
        )

    async def upsert(self, **fields) -> PlatformConfig:
        m = (await self.session.execute(select(PlatformConfigModel).limit(1))).scalar_one_or_none()
        if m is None:
            m = PlatformConfigModel(id=uuid.uuid4(), singleton=True)
            self.session.add(m)
        for k, v in fields.items():
            if v is not None:
                setattr(m, k, v)
        await self.session.flush()
        return await self.get()
```
(senha SMTP e openai key passados já cifrados pelos callers, ou cifrar aqui — manter consistente: o router cifra antes via `encrypt()`.)

- [ ] **Step 3: Teste integração** `test_platform_config_repo.py` (testcontainer + migrations): `upsert(openai_api_key=enc, smtp_host="x", ...)` → `get()` retorna; segundo `upsert` parcial só atualiza o passado; `decrypt(encrypt("s"))=="s"`.
- [ ] **Step 4: Commit** `git commit -m "feat(platform): PlatformConfig entity + repository"`

---

## Task 3: OpenAI lê do platform_config (remove do tenant)

**Files:**
- Modify: `apps/api/src/shared/adapters/llm/openai_client.py:19-20`, `interface/http/deps/admin_deps.py:77-78`, `interface/worker/handlers/message.py:75,85`
- Modify: `shared/domain/entities/account_config.py` (remove `openai_api_key` de `IntegrationConfig` e `AccountConfigPatch`), `account_config_repo.py` (remove das linhas _SENSITIVE/get/update), `interface/http/schemas/admin_settings.py` (remove openai), `interface/http/routers/admin/settings.py` (remove openai do GET/PUT).

- [ ] **Step 1:** Adicionar um helper `async def resolve_openai_key(session) -> str`: lê `PlatformConfigRepository(session).get().openai_api_key` (decriptado); **fallback** `get_settings().openai_api_key` (env). Usar nos 3 call-sites:
  - `message.py`: trocar `account_config.integration.openai_api_key` por `await resolve_openai_key(session)`.
  - `openai_client.from_settings()` e `admin_deps.py`: já usam env — passar a aceitar a chave resolvida do platform_config quando houver sessão; onde não há sessão fácil, manter env fallback (a chave migrada está no platform_config, mas env continua válido). Mínimo: garantir que message.py (per-tenant hoje) use o global.
- [ ] **Step 2:** Remover `openai_api_key` de `IntegrationConfig`/`AccountConfigPatch`/`account_config_repo` (_SENSITIVE, get, update), do schema `admin_settings.py` e do router `settings.py`. Ajustar testes de settings/account_config que referenciam openai.
- [ ] **Step 3:** `uv run pytest tests/unit -q` + `uv run python -c "import main"` + `import worker`. Corrigir regressões.
- [ ] **Step 4: Commit** `git commit -m "feat(platform): OpenAI lê do platform_config; remove do tenant settings"`

---

## Task 4: SMTP lê do platform_config (global)

**Files:**
- Modify: `shared/adapters/email/smtp_email_service.py` (`send_email` sem `account_id`, lê do `PlatformConfigRepository`), seus callers (`use_cases/admin/create_user.py`, `reset_user_password.py`, `interface/http/routers/admin/users.py:95-96,175-176`), e aposenta `smtp_config_repo.py`/`SmtpConfig` (ou mantém só p/ downgrade — preferir remover usos).

- [ ] **Step 1:** `SmtpEmailService.send_email(*, to, subject, body_html)` (sem account_id) → carrega `PlatformConfigRepository(session).get()`; decripta `smtp_encrypted_password`; envia via aiosmtplib. Lança `SmtpNotConfiguredError` se `smtp_host` ausente.
- [ ] **Step 2:** Callers (`create_user`, `reset_user_password`, `users.py`) param de passar `account_id` ao `send_email`. Instanciam `SmtpEmailService` com a session/PlatformConfigRepository.
- [ ] **Step 3:** Testes (`test_smtp_config_repo` vira `test_platform_smtp`, ou ajusta) — envio lê do global.
- [ ] **Step 4:** `uv run pytest tests/unit -q`. Commit `git commit -m "feat(platform): SMTP global via platform_config"`

---

## Task 5: Router platform-config + remove openai do /admin/settings

**Files:**
- Create: `apps/api/src/interface/http/routers/admin/platform_config.py` (GET/PUT/test) + schema; registrar em `main.py`.
- Modify: aposentar `interface/http/routers/admin/smtp_config.py` (ou redirecionar pros novos endpoints).

- [ ] **Step 1:** `GET /admin/platform-config` → `{openai_api_key: masked, smtp: {host,port,use_tls,username,has_password,from_name,from_email}}`. `PUT /admin/platform-config` → upsert (cifra openai/senha via repo.encrypt; senha vazia mantém atual). `POST /admin/platform-config/test` → envia e-mail de teste via `SmtpEmailService`. Auth: `require_admin_role` (por ora; futura camada super-admin).
- [ ] **Step 2:** Registrar router em `main.py`. Remover bloco openai do `/admin/settings`.
- [ ] **Step 3:** Teste integração do router (GET/PUT/test). `uv run pytest`. Commit.

---

## Task 6: Frontend — tira OpenAI/SMTP do tenant, cria seção "Plataforma"

**Files:**
- Modify: `apps/web/src/features/settings/components/IntegrationSection.tsx` (remove bloco OpenAI), `features/settings/types.ts` (remove `openai_api_key` de `AccountSettings`), `lib/api.ts`.
- Create: `apps/web/src/features/settings/components/PlatformSection.tsx` (OpenAI + SMTP) consumindo os novos endpoints (`getPlatformConfig`/`savePlatformConfig`/`testPlatformConfig`). Mover o `SmtpConfigForm` pra essa seção. Página/aba "Plataforma" (ou seção no topo de Settings, marcada como "núcleo").

- [ ] **Step 1:** `lib/api.ts`: `getPlatformConfig/savePlatformConfig/testPlatformConfig` (substitui os de smtp). Remove `openai_api_key` de `AccountSettings`.
- [ ] **Step 2:** Remove o campo OpenAI do `IntegrationSection`. Cria `PlatformSection` com OpenAI (secret) + SMTP (reusa o form). Coloca numa seção "Plataforma / Núcleo" claramente separada.
- [ ] **Step 3:** `cd apps/web && npx tsc --noEmit`. Commit.

---

## Task 7: Verificação integrada
- [ ] `cd apps/api && uv run pytest tests/unit -q` (gate CI) + integração nova (migração/repo/router).
- [ ] `uvx ruff@0.15.12 check src tests && format --check`; `uv run mypy src` (sem novos).
- [ ] `cd apps/web && npx tsc --noEmit`.
- [ ] `uv run python -c "import main"` e `import worker`.
- [ ] **Validação local com dados reais** (banco `agente-g2-educacao`): `alembic upgrade heads`; conferir `platform_config` populado (openai + smtp vindos do backfill), `accounts.settings` sem openai, envio de e-mail de teste OK, agent (OpenAI) responde.

## Notas de execução
- `down_revision` = `alembic heads` antes de criar (head atual `a7b8c9d0e1f2`).
- Reusar `integration_credentials_key` (Fernet) — blobs migrados não precisam re-encriptar.
- Confirmar o path JSONB do openai em `accounts.settings` antes do `#-`.
- Após merge: deploy roda `alembic upgrade heads`; **backup do banco antes** (como no #71).
