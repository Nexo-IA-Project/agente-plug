# Base multi-tenant + modelo de Perfis/Permissões — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deixar a base multi-tenant pronta (account_id unificado p/ UUID+FF, conta #1 = dados atuais) e o modelo de dados de perfis/permissões (tabelas + catálogo + seed), sem mudar o comportamento atual nem perder dados.

**Architecture:** Migração aditiva-then-swap converte `account_id` Integer→UUID+FK nas 8 tabelas que faltam (backfill com a única conta existente). JWT/auth passam a carregar `account_id` UUID (tolerando tokens antigos). Catálogo de permissões em código + tabelas `profiles`/`profile_permissions` + `users.profile_id`; seed dos perfis Admin/Operador na conta #1. SEM UI nova, SEM trocar guards (`role` mantido).

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, asyncpg, python-jose (HS256), pytest (asyncio_mode=auto, testcontainers).

**Spec:** `docs/superpowers/specs/2026-05-30-multitenant-base-e-perfis-design.md`

**Não-objetivos:** UI de perfis, enforcement por permissão, painel da plataforma, resolução de tenant por usuário em runtime.

---

## File Structure
- `apps/api/src/shared/domain/permissions/catalog.py` — **novo**: catálogo de permissões (chaves `modulo.acao`).
- `apps/api/src/shared/adapters/db/models.py` — `ProfileModel`, `ProfilePermissionModel`, `users.profile_id`; e troca de `account_id` Integer→UUID em 7 tabelas.
- `apps/api/src/shared/domain/entities/profile.py` — **novo**: entidade `Profile`.
- `apps/api/src/shared/adapters/db/repositories/profile_repo.py` — **novo**: `ProfileRepository`.
- `apps/api/src/shared/adapters/db/repositories/user_repo.py` — ler/gravar `profile_id`.
- `apps/api/src/interface/http/routers/admin/auth.py` + `interface/http/deps/admin_auth.py` — JWT/AdminAuth com `account_id` UUID (tolerante).
- `apps/api/src/shared/adapters/db/repositories/account_config_repo.py` — `get(account_id: UUID)`.
- `apps/api/migrations/versions/` — 3 revisões encadeadas (profiles; account_id unification; seed).
- Testes em `tests/unit/` e `tests/integration/`.

---

## Task 1: Catálogo de permissões (código)

**Files:**
- Create: `apps/api/src/shared/domain/permissions/__init__.py` (vazio) e `catalog.py`
- Test: `apps/api/tests/unit/test_permission_catalog.py`

- [ ] **Step 1: Teste falhando** (`tests/unit/test_permission_catalog.py`)

```python
import re
from shared.domain.permissions.catalog import PERMISSION_CATALOG, all_permission_keys


def test_keys_are_unique_and_well_formed():
    keys = [p.key for p in PERMISSION_CATALOG]
    assert len(keys) == len(set(keys)), "chaves duplicadas no catálogo"
    for k in keys:
        assert re.fullmatch(r"[a-z_]+(\.[a-z_]+)+", k), f"chave mal formada: {k}"


def test_all_permission_keys_helper_matches_catalog():
    assert set(all_permission_keys()) == {p.key for p in PERMISSION_CATALOG}


def test_has_core_modules():
    modules = {p.module for p in PERMISSION_CATALOG}
    for m in ["dashboard", "products", "leads", "onboarding", "users", "settings"]:
        assert m in modules
```

- [ ] **Step 2: Rodar — falha.** `cd apps/api && uv run pytest tests/unit/test_permission_catalog.py -q` → FAIL (módulo inexistente).

- [ ] **Step 3: Implementar** `catalog.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Permission:
    key: str       # "<module>.<action>"
    module: str    # agrupador p/ UI futura
    label: str     # rótulo PT-BR
    action: str    # view|create|edit|delete|manage|...


def _p(module: str, action: str, label: str) -> Permission:
    return Permission(key=f"{module}.{action}", module=module, label=label, action=action)


PERMISSION_CATALOG: list[Permission] = [
    _p("dashboard", "view", "Ver painel"),
    _p("kb", "view", "Ver base de conhecimento"),
    _p("kb", "create", "Enviar documento"),
    _p("kb", "delete", "Excluir documento"),
    _p("accounts", "view", "Ver contas"),
    _p("products", "view", "Ver produtos"),
    _p("products", "create", "Criar produto"),
    _p("products", "edit", "Editar produto"),
    _p("products", "delete", "Excluir produto"),
    _p("leads", "view", "Ver leads"),
    _p("leads", "export", "Exportar leads"),
    _p("onboarding", "view", "Ver onboarding"),
    _p("onboarding", "create", "Criar flow"),
    _p("onboarding", "edit", "Editar flow"),
    _p("onboarding", "delete", "Excluir flow"),
    _p("onboarding", "resolve_unmapped", "Resolver pendências"),
    _p("templates", "view", "Ver templates"),
    _p("templates", "create", "Criar template"),
    _p("templates", "delete", "Excluir template"),
    _p("users", "view", "Ver usuários"),
    _p("users", "manage", "Gerenciar usuários"),
    _p("settings", "view", "Ver configurações"),
    _p("settings", "edit_credentials", "Editar credenciais/integração"),
    _p("settings", "edit_smtp", "Editar SMTP"),
    _p("tokens", "view", "Ver tokens de API"),
    _p("tokens", "manage", "Gerenciar tokens de API"),
]


def all_permission_keys() -> list[str]:
    return [p.key for p in PERMISSION_CATALOG]


# Permissões que hoje são "admin-only" (operador NÃO tem). Base p/ o seed do perfil Operador.
ADMIN_ONLY_KEYS: frozenset[str] = frozenset(
    {
        "users.manage",
        "templates.delete",
        "kb.delete",
        "tokens.manage",
        "settings.edit_credentials",
        "settings.edit_smtp",
    }
)
```

- [ ] **Step 4: Rodar — passa.** `uv run pytest tests/unit/test_permission_catalog.py -q` → 3 passed.
- [ ] **Step 5: Commit.** `git add ... && git commit -m "feat(rbac): catálogo de permissões (módulo.ação)"`

---

## Task 2: Models + migração das tabelas de perfis

**Files:**
- Modify: `apps/api/src/shared/adapters/db/models.py`
- Create: `apps/api/migrations/versions/<rev1>_profiles_tables.py`

- [ ] **Step 1: Models** em `models.py` (após `UserModel`). `account_id` é UUID FK (accounts é UUID):

```python
class ProfileModel(Base):
    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("account_id", "name", name="uq_profiles_account_name"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("FALSE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("NOW()"), onupdate=sa_text("NOW()"), nullable=False)


class ProfilePermissionModel(Base):
    __tablename__ = "profile_permissions"
    __table_args__ = (UniqueConstraint("profile_id", "permission_key", name="uq_profile_perm"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission_key: Mapped[str] = mapped_column(String(100), nullable=False)
```

E adicionar a coluna em `UserModel` (nullable; FK p/ profiles):
```python
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
```

- [ ] **Step 2: Migration** `<rev1>_profiles_tables.py` — `down_revision` = saída de `uv run alembic heads`. `upgrade()`: cria `profiles`, `profile_permissions`, e `op.add_column("users", sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True))`. `downgrade()`: drop coluna + 2 tabelas. (Use o mesmo estilo de migrations existentes, ex. a de `product_hubla_aliases`.)

- [ ] **Step 3: Validar.** `uv run alembic upgrade heads` (Postgres local) OU `uv run pytest tests/integration/test_leads_pubsub.py -q` (aplica migrations via testcontainer). Confirmar tabelas/coluna criadas.
- [ ] **Step 4: Smoke import.** `uv run python -c "import shared.adapters.db.models"`.
- [ ] **Step 5: Commit.** `git commit -m "feat(rbac): tabelas profiles/profile_permissions + users.profile_id"`

---

## Task 3: Entidade Profile + ProfileRepository

**Files:**
- Create: `apps/api/src/shared/domain/entities/profile.py`, `apps/api/src/shared/adapters/db/repositories/profile_repo.py`
- Test: `apps/api/tests/integration/test_profile_repo.py`

- [ ] **Step 1: Entidade** `profile.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class Profile:
    id: UUID
    account_id: UUID
    name: str
    is_system: bool
    permissions: list[str] = field(default_factory=list)
```

- [ ] **Step 2: Repo** `profile_repo.py`:
```python
from __future__ import annotations
import uuid
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import ProfileModel, ProfilePermissionModel
from shared.domain.entities.profile import Profile


@dataclass
class ProfileRepository:
    session: AsyncSession

    async def create(self, *, account_id: UUID, name: str, is_system: bool, permissions: list[str]) -> Profile:
        model = ProfileModel(id=uuid.uuid4(), account_id=account_id, name=name, is_system=is_system)
        self.session.add(model)
        await self.session.flush()
        for key in dict.fromkeys(permissions):  # dedup preservando ordem
            self.session.add(ProfilePermissionModel(id=uuid.uuid4(), profile_id=model.id, permission_key=key))
        await self.session.flush()
        return Profile(id=model.id, account_id=account_id, name=name, is_system=is_system, permissions=list(dict.fromkeys(permissions)))

    async def get_by_name(self, account_id: UUID, name: str) -> Profile | None:
        m = (
            await self.session.execute(
                select(ProfileModel).where(ProfileModel.account_id == account_id, ProfileModel.name == name)
            )
        ).scalar_one_or_none()
        if m is None:
            return None
        perms = (
            await self.session.execute(
                select(ProfilePermissionModel.permission_key).where(ProfilePermissionModel.profile_id == m.id)
            )
        ).scalars().all()
        return Profile(id=m.id, account_id=m.account_id, name=m.name, is_system=m.is_system, permissions=list(perms))

    async def list_by_account(self, account_id: UUID) -> list[Profile]:
        rows = (
            await self.session.execute(
                select(ProfileModel).where(ProfileModel.account_id == account_id).order_by(ProfileModel.name)
            )
        ).scalars().all()
        out: list[Profile] = []
        for m in rows:
            perms = (
                await self.session.execute(
                    select(ProfilePermissionModel.permission_key).where(ProfilePermissionModel.profile_id == m.id)
                )
            ).scalars().all()
            out.append(Profile(id=m.id, account_id=m.account_id, name=m.name, is_system=m.is_system, permissions=list(perms)))
        return out
```

- [ ] **Step 3: Teste integração** `test_profile_repo.py` (padrão `_apply_migrations` + `engine` de `test_scheduler_runner_commit.py`): seed account; `create` perfil com 3 permissões; `get_by_name` retorna com as 3; `list_by_account` retorna 1. Use `async_sessionmaker(engine)`.
- [ ] **Step 4: Rodar.** `uv run pytest tests/integration/test_profile_repo.py -q` → passa.
- [ ] **Step 5: Commit.** `git commit -m "feat(rbac): Profile entity + ProfileRepository"`

---

## Task 4: Migração de fundação — account_id Integer→UUID+FK (data-safe)

**Files:**
- Modify: `apps/api/src/shared/adapters/db/models.py` (7 models: `UserModel`, `SmtpConfigModel`, `KnowledgeDocumentModel`, `KnowledgeChunkModel`, `KbUsageLogModel`, `AccessCaseModel`, `RefundCaseModel`) — trocar `account_id: Mapped[int] = mapped_column(Integer, ...)` por `Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True)`. Manter `unique` onde havia (smtp_config) e recriar `uq_users_account_email`.
- Create: `apps/api/migrations/versions/<rev2>_account_id_to_uuid.py` (`down_revision` = `<rev1>`)

- [ ] **Step 1: Migration** com helper de conversão por tabela. `upgrade()`:
```python
def upgrade() -> None:
    conn = op.get_bind()
    # garante conta #1 (idempotente)
    acc = conn.execute(sa.text("SELECT id FROM accounts ORDER BY created_at LIMIT 1")).scalar()
    if acc is None:
        acc = conn.execute(
            sa.text("INSERT INTO accounts (id, name, settings) VALUES (gen_random_uuid(), 'Conta Principal', '{}'::jsonb) RETURNING id")
        ).scalar()

    def convert(table: str, *, unique_with_email: bool = False, unique_account: bool = False):
        op.add_column(table, sa.Column("account_uuid", UUID(as_uuid=True), nullable=True))
        conn.execute(sa.text(f"UPDATE {table} SET account_uuid = :acc"), {"acc": acc})
        # drop constraints antigas que dependiam do account_id integer
        if unique_with_email:
            op.drop_constraint("uq_users_account_email", "users", type_="unique")
        if unique_account:
            # smtp_config.account_id era unique
            op.drop_constraint("smtp_config_account_id_key", "smtp_config", type_="unique")
        op.drop_column(table, "account_id")
        op.alter_column(table, "account_uuid", new_column_name="account_id", nullable=False)
        op.create_foreign_key(f"fk_{table}_account", table, "accounts", ["account_id"], ["id"])
        op.create_index(f"ix_{table}_account_id", table, ["account_id"])
        if unique_with_email:
            op.create_unique_constraint("uq_users_account_email", "users", ["account_id", "email"])
        if unique_account:
            op.create_unique_constraint("uq_smtp_config_account", "smtp_config", ["account_id"])

    convert("users", unique_with_email=True)
    convert("smtp_config", unique_account=True)
    convert("knowledge_documents")
    convert("knowledge_chunks")
    convert("kb_usage_logs")
    convert("access_cases")
    convert("refund_cases")
```
`downgrade()`: para cada tabela, recriar `account_id INTEGER NOT NULL DEFAULT 1`, dropar FK/coluna UUID (reverso). (Detalhar o reverso por tabela.)

> NOTA executor: confira os NOMES REAIS das constraints unique antes (ex: `\d smtp_config` / `\d users` num Postgres com as migrations aplicadas, ou `SELECT conname FROM pg_constraint`). Ajuste `smtp_config_account_id_key`/`uq_users_account_email` aos nomes reais. `gen_random_uuid()` requer extensão pgcrypto (a tabela accounts usa UUID; confirme que `gen_random_uuid` existe — senão use `uuid_generate_v4()` ou gere no Python e passe via param).

- [ ] **Step 2: Atualizar os 7 models** conforme acima.
- [ ] **Step 3: Validar a migração com preservação de dados (integração).** Crie `tests/integration/test_account_id_migration.py`: aplica migrations (`alembic upgrade heads`), insere 1 account + 2 users (via SQL bruto antes? — não dá, a coluna já é UUID após upgrade). Em vez disso: o teste sobe o testcontainer (que aplica heads), e verifica que `users.account_id`/`smtp_config.account_id` etc. são `uuid` (consulta `information_schema.columns`) e têm FK p/ accounts (consulta `information_schema.table_constraints`). Para preservação de dados real, valide manualmente em staging/prod (ver verificação manual no spec).
- [ ] **Step 4: Rodar.** `uv run pytest tests/integration/test_account_id_migration.py -q`. + `uv run python -c "import shared.adapters.db.models"`.
- [ ] **Step 5: Commit.** `git commit -m "feat(db): account_id Integer→UUID+FK nas 8 tabelas (data-safe)"`

---

## Task 5: Auth/JWT com account_id UUID (tolerante a tokens antigos)

**Files:**
- Modify: `apps/api/src/interface/http/routers/admin/auth.py`, `interface/http/deps/admin_auth.py`, `shared/adapters/db/repositories/account_config_repo.py` + call-sites `get(account_id=1)`.
- Modify: `apps/api/src/shared/adapters/db/repositories/user_repo.py` (account_id agora UUID) + entidade User.
- Test: `apps/api/tests/unit/interface/http/test_admin_auth.py` (ou onde já houver)

- [ ] **Step 1: Entidade/Repo User com account_id UUID.** Em `shared/domain/entities/user.py` trocar `account_id: int` → `UUID`. Em `user_repo.py`, ajustar `save`/mapeamentos para UUID e adicionar leitura/escrita de `profile_id` (campo novo na entidade `User`: `profile_id: UUID | None = None`).
- [ ] **Step 2: AdminAuth tolerante.** Em `admin_auth.py`: `AdminAuth.account_id: UUID | None`. No `_decode`, ler `account_id` do payload e converter pra UUID **com tolerância**:
```python
raw_acc = payload.get("account_id")
try:
    account_id = UUID(str(raw_acc)) if raw_acc is not None else None
except (ValueError, TypeError):
    account_id = None  # token legado (account_id inteiro) — não derruba o login
```
- [ ] **Step 3: Login emite UUID.** Em `auth.py`, o snapshot já tem `user.account_id` (agora UUID); colocar `str(account_id)` no token (`create_access_token` serializa via jose; UUID→str).
- [ ] **Step 4: AccountConfigRepository.get(account_id: UUID).** Trocar assinatura `account_id: int` → `UUID`; **manter** a resolução interna via `get_default_account_uuid` (comportamento inalterado). Atualizar call-sites `config_repo.get(account_id=1)` para passar o UUID resolvido (ex: `await get_default_account_uuid(session)`), nos arquivos: `hubla_event.py`, `scheduled.py`, `lead_repo.py`(se houver), `onboarding_enrollments.py`, `account_config_repo.update`.
- [ ] **Step 5: Testes.** Unit do `_decode`: token com `account_id` UUID → `AdminAuth.account_id` UUID; token legado com `account_id=1` → `account_id=None`, sem exceção. Ajustar testes de auth/login existentes ao novo tipo.
- [ ] **Step 6: Rodar.** `uv run pytest tests/unit -q` (zero regressões) + `uv run python -c "import main"`.
- [ ] **Step 7: Commit.** `git commit -m "feat(auth): account_id UUID no JWT/AdminAuth (tolerante a tokens legados)"`

---

## Task 6: Seed dos perfis padrão + atribuição aos usuários (migração de dados)

**Files:**
- Create: `apps/api/migrations/versions/<rev3>_seed_default_profiles.py` (`down_revision` = `<rev2>`)
- Reuse: catálogo da Task 1 (importar `all_permission_keys`, `ADMIN_ONLY_KEYS`) — em migration, importar do pacote é aceitável (já há migrations que importam settings).

- [ ] **Step 1: Migration de seed** `upgrade()`:
```python
def upgrade() -> None:
    from shared.domain.permissions.catalog import all_permission_keys, ADMIN_ONLY_KEYS
    import uuid as _uuid
    conn = op.get_bind()
    acc = conn.execute(sa.text("SELECT id FROM accounts ORDER BY created_at LIMIT 1")).scalar()
    if acc is None:
        return  # ambiente sem conta; nada a semear

    def ensure_profile(name: str, is_system: bool, keys: list[str]) -> str:
        existing = conn.execute(
            sa.text("SELECT id FROM profiles WHERE account_id=:a AND name=:n"), {"a": acc, "n": name}
        ).scalar()
        if existing:
            return existing
        pid = str(_uuid.uuid4())
        conn.execute(
            sa.text("INSERT INTO profiles (id, account_id, name, is_system) VALUES (:i,:a,:n,:s)"),
            {"i": pid, "a": acc, "n": name, "s": is_system},
        )
        for k in keys:
            conn.execute(
                sa.text("INSERT INTO profile_permissions (id, profile_id, permission_key) VALUES (:i,:p,:k)"),
                {"i": str(_uuid.uuid4()), "p": pid, "k": k},
            )
        return pid

    all_keys = list(all_permission_keys())
    operator_keys = [k for k in all_keys if k not in ADMIN_ONLY_KEYS]
    admin_pid = ensure_profile("Admin", True, all_keys)
    operator_pid = ensure_profile("Operador", False, operator_keys)

    # atribui profile_id aos usuários existentes conforme role
    conn.execute(sa.text("UPDATE users SET profile_id=:p WHERE role='admin' AND profile_id IS NULL"), {"p": admin_pid})
    conn.execute(sa.text("UPDATE users SET profile_id=:p WHERE role='operator' AND profile_id IS NULL"), {"p": operator_pid})
```
`downgrade()`: `UPDATE users SET profile_id=NULL`; `DELETE FROM profiles WHERE account_id=<acc> AND name IN ('Admin','Operador')` (cascade limpa profile_permissions).

- [ ] **Step 2: Validar (integração)** `tests/integration/test_seed_profiles.py`: após `upgrade heads`, conta #1 tem perfis "Admin" (com `len(permissions)==len(catalog)`) e "Operador" (sem as ADMIN_ONLY_KEYS); se houver usuários seedados (o admin inicial), confere `profile_id` setado conforme role. Use `ProfileRepository` p/ ler.
- [ ] **Step 3: Rodar.** `uv run pytest tests/integration/test_seed_profiles.py -q`.
- [ ] **Step 4: Commit.** `git commit -m "feat(rbac): seed perfis Admin/Operador na conta #1 + atribui aos usuários"`

---

## Task 7: Verificação integrada + regressão

- [ ] **Step 1:** `cd apps/api && uv run pytest tests/unit -q` (gate do CI) → zero regressões.
- [ ] **Step 2:** `uv run pytest tests/integration/test_profile_repo.py tests/integration/test_account_id_migration.py tests/integration/test_seed_profiles.py -q`.
- [ ] **Step 3:** `uvx ruff@0.15.12 check src tests && uvx ruff@0.15.12 format --check src tests` + `uv run mypy src` (sem erros NOVOS vs main).
- [ ] **Step 4:** `uv run python -c "import main"` e `uv run python -c "import worker"` (app + worker importam).
- [ ] **Step 5: Commit** (se houver ajustes de regressão).

## Verificação manual (pós-deploy, staging/prod)
- Login funciona; telas atuais idênticas; JWT novo carrega `account_id` UUID.
- `SELECT count(*)` antes/depois nas 7 tabelas convertidas = igual (nenhum dado perdido).
- `users.account_id` é uuid e = `accounts.id`; `profiles` tem Admin+Operador; cada user com `profile_id`.

## Notas de execução
- `down_revision` de cada migration = head anterior (`alembic heads` antes de criar).
- Confirmar nomes reais das unique constraints (`uq_users_account_email`, unique de `smtp_config.account_id`) antes de dropar — `SELECT conname FROM pg_constraint WHERE conrelid='users'::regclass`.
- Confirmar `gen_random_uuid()` disponível; senão gerar UUID no Python e passar por param.
- Ordem das migrations: profiles (rev1) → account_id UUID (rev2) → seed (rev3).
