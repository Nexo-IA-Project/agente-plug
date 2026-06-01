# Controle de Acesso Multi-Tenant — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separar Identidade (credencial única global) de Membership (vínculo pessoa↔conta↔papel), entregando login único com escolha de conta, troca de conta, owner protegido, vínculo silencioso de funcionários e enforcement por conta — sem perder dados do tenant de produção.

**Architecture:** Padrão expand/contract. Criamos `identities` + `memberships` ao lado de `users`, fazemos backfill verificado, e cortamos o código para ler/escrever nas tabelas novas. `users` permanece como backup vivo (drop só em PR futuro). Clean Architecture já existente: domain entities → repositories → use cases → routers (FastAPI). Frontend Next.js consome via `apiFetch`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async, Alembic, asyncpg, pytest (unit com mocks + integration com testcontainers Postgres), Next.js 15, TypeScript.

**Spec de referência:** `docs/superpowers/specs/2026-05-30-multitenant-access-control-design.md`

**Comandos (rodar de `apps/api/`):**
- Teste unit: `uv run pytest tests/unit -q`
- Teste integration (precisa Docker): `uv run pytest tests/integration -q`
- Lint/format: `uv run ruff check src tests && uv run ruff format src tests`
- Types: `uv run mypy src`
- Migrations: `uv run alembic upgrade heads`

---

## File Structure

**Backend — criar:**
- `apps/api/src/shared/domain/entities/identity.py` — entidade `Identity`
- `apps/api/src/shared/domain/entities/membership.py` — entidade `Membership`
- `apps/api/src/shared/adapters/db/repositories/identity_repo.py` — `IdentityRepository`
- `apps/api/src/shared/adapters/db/repositories/membership_repo.py` — `MembershipRepository`
- `apps/api/src/shared/application/use_cases/admin/add_member.py` — `AddMemberUseCase` (vínculo silencioso)
- `apps/api/migrations/versions/aa01_multitenant_identities_memberships.py` — migração expand + backfill
- `apps/api/src/shared/db/seed_multitenant.py` — script de seed idempotente
- Testes: `tests/unit/domain/test_identity_entity.py`, `tests/unit/domain/test_membership_entity.py`, `tests/integration/test_identity_repo.py`, `tests/integration/test_membership_repo.py`, `tests/integration/test_multitenant_migration.py`, `tests/unit/admin/test_add_member.py`, `tests/unit/interface/admin/test_auth_login_multi.py`, `tests/unit/interface/admin/test_select_switch_account.py`, `tests/unit/interface/admin/test_users_router_membership.py`

**Backend — modificar:**
- `apps/api/src/shared/adapters/db/models.py` — adicionar `IdentityModel`, `MembershipModel`, campos novos em `AccountModel`
- `apps/api/src/interface/http/routers/admin/auth.py` — login multi-conta + `select-account` + `switch-account`
- `apps/api/src/interface/http/deps/admin_auth.py` — `AdminAuth` ganha `identity_id`, `membership_id`
- `apps/api/src/interface/http/deps/permissions.py` — resolve permissões via membership
- `apps/api/src/interface/http/routers/admin/users.py` — opera sobre memberships
- `apps/api/src/interface/http/routers/admin/me.py` — opera sobre identity (avatar/senha/perfil)
- `apps/api/src/shared/application/use_cases/admin/reset_user_password.py` — opera sobre identity

**Frontend — modificar:**
- `apps/web/src/features/auth/lib/jwt.ts` — payload com `account_id: string`, `identity_id`, `membership_id`
- `apps/web/src/lib/auth.ts` — `loginRequest` retorna desfecho (token | pre-auth + contas); `selectAccount`, `switchAccount`
- `apps/web/src/features/auth/context/AuthContext.tsx` — estado de conta atual + lista de contas
- `apps/web/src/app/(auth)/login/page.tsx` — modal de escolha de conta
- `apps/web/src/shared/components/layout/TopBar.tsx` — seletor de empresa
- `apps/web/src/features/users/*` — gestão de memberships (ids agora são membership_id)

---

## Convenções de teste (ler antes de começar)

- **Unit de router** (`tests/unit/interface/admin/`): cria `FastAPI()`, inclui o router com `prefix="/admin"`, e mocka `get_db`/`get_settings` via `unittest.mock.patch` no namespace do módulo do router. Ver `tests/unit/interface/admin/test_auth_router.py` como modelo exato.
- **Integration de repo** (`tests/integration/`): usa `db_session` (fixture do `tests/integration/conftest.py`) sobre testcontainer Postgres; aplica `alembic upgrade heads` uma vez por sessão; insere contas reais via SQL `ON CONFLICT DO NOTHING`. Ver `tests/integration/test_user_repo.py`.
- Todo teste async usa `@pytest.mark.asyncio`.

---

# FASE 1 — Fundação de dados (entidades, models, repos, migração, seed)

Produz software testável: a migração roda e o backfill é verificado por testes de integração.

## Task 1: Entidade `Identity`

**Files:**
- Create: `apps/api/src/shared/domain/entities/identity.py`
- Test: `apps/api/tests/unit/domain/test_identity_entity.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/domain/test_identity_entity.py
from __future__ import annotations

from shared.domain.entities.identity import Identity


def test_identity_defaults():
    ident = Identity(email="a@x.com", password_hash="h", name="Alice")
    assert ident.must_change_password is True
    assert ident.is_active is True
    assert ident.avatar is None
    assert isinstance(ident.id, str) and len(ident.id) == 36
    assert ident.last_login_at is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/domain/test_identity_entity.py -v`
Expected: FAIL com `ModuleNotFoundError: shared.domain.entities.identity`

- [ ] **Step 3: Implementar a entidade**

```python
# src/shared/domain/entities/identity.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass
class Identity:
    email: str
    password_hash: str
    name: str
    id: str = field(default_factory=lambda: str(uuid4()))
    avatar: bytes | None = None
    must_change_password: bool = True
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_login_at: datetime | None = None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/domain/test_identity_entity.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/shared/domain/entities/identity.py tests/unit/domain/test_identity_entity.py
git commit -m "feat(domain): entidade Identity"
```

## Task 2: Entidade `Membership`

**Files:**
- Create: `apps/api/src/shared/domain/entities/membership.py`
- Test: `apps/api/tests/unit/domain/test_membership_entity.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/domain/test_membership_entity.py
from __future__ import annotations

from uuid import UUID, uuid4

from shared.domain.entities.membership import Membership
from shared.domain.entities.user import UserRole


def test_membership_defaults():
    acc = uuid4()
    ident_id = str(uuid4())
    m = Membership(identity_id=ident_id, account_id=acc, role=UserRole.OPERATOR)
    assert m.is_owner is False
    assert m.is_active is True
    assert m.profile_id is None
    assert isinstance(UUID(m.id), UUID)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/domain/test_membership_entity.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar a entidade**

```python
# src/shared/domain/entities/membership.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from shared.domain.entities.user import UserRole


@dataclass
class Membership:
    identity_id: str
    account_id: UUID
    role: UserRole
    id: str = field(default_factory=lambda: str(uuid4()))
    profile_id: UUID | None = None
    is_owner: bool = False
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/domain/test_membership_entity.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/shared/domain/entities/membership.py tests/unit/domain/test_membership_entity.py
git commit -m "feat(domain): entidade Membership"
```

## Task 3: Models SQLAlchemy `IdentityModel`, `MembershipModel` + campos em `accounts`

**Files:**
- Modify: `apps/api/src/shared/adapters/db/models.py` (adicionar ao final, junto aos demais models; e adicionar colunas em `AccountModel`)

> Consultar no arquivo a classe base usada (`Base`) e o estilo de `UserModel`/`ProfileModel` (linhas ~451-514) e `AccountModel` (linhas ~36-43) para casar o padrão exato (`mapped_column`, tipos, `server_default`).

- [ ] **Step 1: Adicionar colunas de cadastro em `AccountModel`**

Localizar `class AccountModel` e adicionar após `settings`:

```python
    legal_name: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
```

> Se o arquivo usar `Column(...)` no estilo clássico em vez de `Mapped[...] = mapped_column(...)`, copiar o estilo do arquivo. Verificar como `UserModel.avatar` é declarado e seguir igual.

- [ ] **Step 2: Adicionar `IdentityModel` e `MembershipModel`**

```python
class IdentityModel(Base):
    __tablename__ = "identities"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    avatar: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)
    must_change_password: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("TRUE")
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("TRUE")
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    __table_args__ = (sa.UniqueConstraint("email", name="uq_identities_email"),)


class MembershipModel(Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    identity_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("identities.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("accounts.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    profile_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("profiles.id"), nullable=True
    )
    is_owner: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("FALSE")
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("TRUE")
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )

    __table_args__ = (
        sa.UniqueConstraint("identity_id", "account_id", name="uq_membership_identity_account"),
        sa.Index("ix_memberships_account_id", "account_id"),
        sa.Index("ix_memberships_identity_id", "identity_id"),
    )
```

> Ajustar imports no topo se necessário: `from datetime import datetime`, `from uuid import UUID`. Conferir se o arquivo usa `sa.Uuid` ou `postgresql.UUID(as_uuid=True)` para `account_id` em `UserModel` e copiar exatamente o mesmo tipo.

- [ ] **Step 3: Verificar import sem erro**

Run: `uv run python -c "from shared.adapters.db.models import IdentityModel, MembershipModel, AccountModel"`
Expected: sem saída (sucesso)

- [ ] **Step 4: Lint/type**

Run: `uv run ruff check src/shared/adapters/db/models.py && uv run mypy src/shared/adapters/db/models.py`
Expected: sem erros

- [ ] **Step 5: Commit**

```bash
git add src/shared/adapters/db/models.py
git commit -m "feat(db): models IdentityModel, MembershipModel e campos de cadastro em accounts"
```

## Task 4: Migração expand + backfill + verificação

**Files:**
- Create: `apps/api/migrations/versions/aa01_multitenant_identities_memberships.py`

> `down_revision` = head atual = `"a9b0c1d2e3f4"` (confirmar com `uv run alembic heads`; se houver mais de um head, usar a tupla de todos).

- [ ] **Step 1: Escrever a migração**

```python
"""multitenant: identities + memberships + backfill

Revision ID: aa01mt
Revises: a9b0c1d2e3f4
Create Date: 2026-05-31

Padrão expand/contract: cria identities/memberships AO LADO de users e faz
backfill verificado. NÃO dropa users (drop fica para PR de contract).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision = "aa01mt"
down_revision: Union[str, Sequence[str]] = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Campos de cadastro em accounts (nullable)
    op.add_column("accounts", sa.Column("legal_name", sa.String(200), nullable=True))
    op.add_column("accounts", sa.Column("tax_id", sa.String(40), nullable=True))
    op.add_column("accounts", sa.Column("contact_email", sa.String(200), nullable=True))
    op.add_column("accounts", sa.Column("contact_phone", sa.String(40), nullable=True))

    # 2) Tabelas novas
    op.create_table(
        "identities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("avatar", sa.LargeBinary, nullable=True),
        sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_identities_email"),
    )
    op.create_table(
        "memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("identity_id", sa.String(36), sa.ForeignKey("identities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Uuid, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("profile_id", sa.Uuid, sa.ForeignKey("profiles.id"), nullable=True),
        sa.Column("is_owner", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("identity_id", "account_id", name="uq_membership_identity_account"),
    )
    op.create_index("ix_memberships_account_id", "memberships", ["account_id"])
    op.create_index("ix_memberships_identity_id", "memberships", ["identity_id"])
    # No máximo 1 owner por conta
    op.create_index(
        "uq_membership_owner_per_account",
        "memberships",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("is_owner"),
    )

    conn = op.get_bind()

    # 3) Pré-condição: sem e-mails duplicados entre contas (falha cedo, sem escrita destrutiva)
    dup = conn.execute(
        sa.text(
            "SELECT lower(email) FROM users GROUP BY lower(email) HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if dup is not None:
        raise RuntimeError(
            f"Backfill abortado: e-mail duplicado entre contas em users: {dup[0]!r}"
        )

    # 4) Backfill identities (1 por e-mail; reusa users.id da linha mais antiga p/ continuidade de auditoria)
    conn.execute(
        sa.text(
            """
            INSERT INTO identities
                (id, email, password_hash, name, avatar, must_change_password, is_active, created_at, last_login_at)
            SELECT DISTINCT ON (lower(u.email))
                   u.id, u.email, u.password_hash, u.name, u.avatar,
                   u.must_change_password, u.is_active, u.created_at, u.last_login_at
            FROM users u
            ORDER BY lower(u.email), u.created_at ASC
            """
        )
    )

    # 5) Backfill memberships (1 por linha de users)
    conn.execute(
        sa.text(
            """
            INSERT INTO memberships
                (id, identity_id, account_id, role, profile_id, is_owner, is_active, created_at)
            SELECT gen_random_uuid()::text, i.id, u.account_id, u.role, u.profile_id, FALSE, u.is_active, u.created_at
            FROM users u
            JOIN identities i ON lower(i.email) = lower(u.email)
            """
        )
    )

    # 6) Owner = admin mais antigo de cada conta
    conn.execute(
        sa.text(
            """
            UPDATE memberships SET is_owner = TRUE
            WHERE id IN (
                SELECT DISTINCT ON (account_id) id
                FROM memberships
                WHERE role = 'admin'
                ORDER BY account_id, created_at ASC
            )
            """
        )
    )
    # 6b) Fallback: conta sem admin → promove o membership mais antigo a admin+owner
    conn.execute(
        sa.text(
            """
            UPDATE memberships SET is_owner = TRUE, role = 'admin'
            WHERE id IN (
                SELECT DISTINCT ON (account_id) id
                FROM memberships
                WHERE account_id NOT IN (SELECT account_id FROM memberships WHERE is_owner)
                ORDER BY account_id, created_at ASC
            )
            """
        )
    )

    # 7) Cadastro fake onde vazio
    conn.execute(
        sa.text("UPDATE accounts SET legal_name = '(pendente)' WHERE legal_name IS NULL")
    )

    # 8) Verificações — qualquer falha aborta a transação inteira (rollback)
    n_users = conn.execute(sa.text("SELECT count(*) FROM users")).scalar()
    n_emails = conn.execute(sa.text("SELECT count(DISTINCT lower(email)) FROM users")).scalar()
    n_ident = conn.execute(sa.text("SELECT count(*) FROM identities")).scalar()
    n_memb = conn.execute(sa.text("SELECT count(*) FROM memberships")).scalar()
    assert n_ident == n_emails, f"identities={n_ident} != distinct emails={n_emails}"
    assert n_memb == n_users, f"memberships={n_memb} != users={n_users}"

    orphans = conn.execute(
        sa.text(
            """
            SELECT count(*) FROM users u
            LEFT JOIN memberships m
              ON m.account_id = u.account_id
             AND m.identity_id = (SELECT id FROM identities i WHERE lower(i.email) = lower(u.email))
            WHERE m.id IS NULL
            """
        )
    ).scalar()
    assert orphans == 0, f"{orphans} linhas de users sem membership"

    bad_owner = conn.execute(
        sa.text(
            """
            SELECT count(*) FROM (
                SELECT account_id FROM memberships
                GROUP BY account_id
                HAVING count(*) FILTER (WHERE is_owner) <> 1
            ) x
            """
        )
    ).scalar()
    assert bad_owner == 0, f"{bad_owner} contas sem exatamente 1 owner"

    null_pw = conn.execute(
        sa.text("SELECT count(*) FROM identities WHERE password_hash IS NULL OR password_hash = ''")
    ).scalar()
    assert null_pw == 0, f"{null_pw} identities com password_hash vazio"


def downgrade() -> None:
    op.drop_index("uq_membership_owner_per_account", table_name="memberships")
    op.drop_index("ix_memberships_identity_id", table_name="memberships")
    op.drop_index("ix_memberships_account_id", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("identities")
    op.drop_column("accounts", "contact_phone")
    op.drop_column("accounts", "contact_email")
    op.drop_column("accounts", "tax_id")
    op.drop_column("accounts", "legal_name")
```

- [ ] **Step 2: Aplicar a migração no banco local de dev**

Run: `uv run alembic upgrade heads`
Expected: sem erro; `aa01mt` aplicada. Conferir: `uv run alembic current` mostra `aa01mt`.

- [ ] **Step 3: Verificar reversibilidade**

Run: `uv run alembic downgrade -1 && uv run alembic upgrade heads`
Expected: downgrade remove tabelas, upgrade recria — ambos sem erro.

- [ ] **Step 4: Commit**

```bash
git add migrations/versions/aa01_multitenant_identities_memberships.py
git commit -m "feat(db): migracao expand identities+memberships com backfill verificado"
```

## Task 5: Teste de integração do backfill

**Files:**
- Create: `apps/api/tests/integration/test_multitenant_migration.py`

- [ ] **Step 1: Escrever o teste**

```python
# tests/integration/test_multitenant_migration.py
from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ACC = UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture(autouse=True)
async def _seed_users(db_session: AsyncSession) -> None:
    await db_session.execute(text("DELETE FROM memberships"))
    await db_session.execute(text("DELETE FROM identities"))
    await db_session.execute(text("DELETE FROM users"))
    await db_session.execute(
        text(
            "INSERT INTO accounts (id, name, settings, created_at) "
            "VALUES (:id, 'BackfillCo', '{}'::jsonb, NOW()) ON CONFLICT (id) DO NOTHING"
        ),
        {"id": str(ACC)},
    )
    # 1 admin (mais antigo) + 1 operator
    await db_session.execute(
        text(
            "INSERT INTO users (id, account_id, name, email, password_hash, role, "
            "must_change_password, is_active, created_at) VALUES "
            "('11111111-0000-0000-0000-000000000001', :acc, 'Boss', 'boss@x.com', 'h1', 'admin', false, true, NOW() - interval '2 day'),"
            "('11111111-0000-0000-0000-000000000002', :acc, 'Emp', 'emp@x.com', 'h2', 'operator', false, true, NOW())"
        ),
        {"acc": str(ACC)},
    )
    await db_session.commit()


async def _run_backfill(session: AsyncSession) -> None:
    # Reproduz os passos 4-7 da migração (idempotentes para o teste)
    await session.execute(
        text(
            "INSERT INTO identities (id, email, password_hash, name, avatar, must_change_password, is_active, created_at, last_login_at) "
            "SELECT DISTINCT ON (lower(u.email)) u.id, u.email, u.password_hash, u.name, u.avatar, u.must_change_password, u.is_active, u.created_at, u.last_login_at "
            "FROM users u ORDER BY lower(u.email), u.created_at ASC"
        )
    )
    await session.execute(
        text(
            "INSERT INTO memberships (id, identity_id, account_id, role, profile_id, is_owner, is_active, created_at) "
            "SELECT gen_random_uuid()::text, i.id, u.account_id, u.role, u.profile_id, FALSE, u.is_active, u.created_at "
            "FROM users u JOIN identities i ON lower(i.email)=lower(u.email)"
        )
    )
    await session.execute(
        text(
            "UPDATE memberships SET is_owner=TRUE WHERE id IN ("
            "SELECT DISTINCT ON (account_id) id FROM memberships WHERE role='admin' "
            "ORDER BY account_id, created_at ASC)"
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_backfill_creates_identities_and_memberships(db_session: AsyncSession) -> None:
    await _run_backfill(db_session)

    n_ident = (await db_session.execute(text("SELECT count(*) FROM identities"))).scalar()
    n_memb = (await db_session.execute(text("SELECT count(*) FROM memberships"))).scalar()
    assert n_ident == 2
    assert n_memb == 2

    owner_email = (
        await db_session.execute(
            text(
                "SELECT i.email FROM memberships m JOIN identities i ON i.id=m.identity_id "
                "WHERE m.is_owner AND m.account_id=:acc"
            ),
            {"acc": str(ACC)},
        )
    ).scalar()
    assert owner_email == "boss@x.com"  # admin mais antigo

    n_owners = (
        await db_session.execute(
            text("SELECT count(*) FROM memberships WHERE is_owner AND account_id=:acc"),
            {"acc": str(ACC)},
        )
    ).scalar()
    assert n_owners == 1
```

- [ ] **Step 2: Rodar**

Run: `uv run pytest tests/integration/test_multitenant_migration.py -v`
Expected: PASS (precisa Docker para o testcontainer Postgres)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_multitenant_migration.py
git commit -m "test(db): valida backfill multi-tenant (owner=admin mais antigo)"
```

## Task 6: `IdentityRepository`

**Files:**
- Create: `apps/api/src/shared/adapters/db/repositories/identity_repo.py`
- Test: `apps/api/tests/integration/test_identity_repo.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/integration/test_identity_repo.py
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.repositories.identity_repo import IdentityRepository
from shared.domain.entities.identity import Identity


@pytest.fixture(autouse=True)
async def _clean(db_session: AsyncSession) -> None:
    await db_session.execute(text("DELETE FROM memberships"))
    await db_session.execute(text("DELETE FROM identities"))
    await db_session.commit()


@pytest.mark.asyncio
async def test_save_and_get_by_email_global(db_session: AsyncSession) -> None:
    repo = IdentityRepository(db_session)
    await repo.save(Identity(email="z@x.com", password_hash="h", name="Zoe"))
    await db_session.commit()

    loaded = await repo.get_by_email("z@x.com")
    assert loaded is not None and loaded.name == "Zoe"
    assert await repo.get_by_email("Z@X.COM") is not None  # case-insensitive


@pytest.mark.asyncio
async def test_update_password_sets_flag(db_session: AsyncSession) -> None:
    repo = IdentityRepository(db_session)
    ident = Identity(email="p@x.com", password_hash="old", name="P", must_change_password=False)
    await repo.save(ident)
    await db_session.commit()

    await repo.update_password(ident.id, "new", must_change_password=True)
    await db_session.commit()

    reloaded = await repo.get_by_id(ident.id)
    assert reloaded is not None
    assert reloaded.password_hash == "new"
    assert reloaded.must_change_password is True
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/integration/test_identity_repo.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar o repo**

```python
# src/shared/adapters/db/repositories/identity_repo.py
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import IdentityModel
from shared.domain.entities.identity import Identity


def _to_entity(m: IdentityModel) -> Identity:
    return Identity(
        id=m.id,
        email=m.email,
        password_hash=m.password_hash,
        name=m.name,
        avatar=m.avatar,
        must_change_password=m.must_change_password,
        is_active=m.is_active,
        created_at=m.created_at,
        last_login_at=m.last_login_at,
    )


class IdentityRepository:
    """Session lifecycle managed by caller. Uses flush(), not commit()."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, ident: Identity) -> None:
        self._session.add(
            IdentityModel(
                id=ident.id,
                email=ident.email,
                password_hash=ident.password_hash,
                name=ident.name,
                avatar=ident.avatar,
                must_change_password=ident.must_change_password,
                is_active=ident.is_active,
            )
        )
        await self._session.flush()

    async def get_by_id(self, identity_id: str) -> Identity | None:
        row = (
            await self._session.execute(
                select(IdentityModel).where(IdentityModel.id == identity_id)
            )
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_email(self, email: str) -> Identity | None:
        row = (
            await self._session.execute(
                select(IdentityModel).where(
                    func.lower(IdentityModel.email) == email.lower()
                )
            )
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def update_password(
        self, identity_id: str, new_hash: str, must_change_password: bool
    ) -> None:
        m = (
            await self._session.execute(
                select(IdentityModel).where(IdentityModel.id == identity_id)
            )
        ).scalar_one()
        m.password_hash = new_hash
        m.must_change_password = must_change_password
        await self._session.flush()

    async def update_profile(self, identity_id: str, name: str) -> None:
        m = (
            await self._session.execute(
                select(IdentityModel).where(IdentityModel.id == identity_id)
            )
        ).scalar_one()
        m.name = name
        await self._session.flush()

    async def update_avatar(self, identity_id: str, avatar: bytes) -> None:
        m = (
            await self._session.execute(
                select(IdentityModel).where(IdentityModel.id == identity_id)
            )
        ).scalar_one()
        m.avatar = avatar
        await self._session.flush()

    async def touch_last_login(self, identity_id: str) -> None:
        m = (
            await self._session.execute(
                select(IdentityModel).where(IdentityModel.id == identity_id)
            )
        ).scalar_one()
        m.last_login_at = datetime.now(UTC)
        await self._session.flush()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/integration/test_identity_repo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/shared/adapters/db/repositories/identity_repo.py tests/integration/test_identity_repo.py
git commit -m "feat(db): IdentityRepository"
```

## Task 7: `MembershipRepository`

**Files:**
- Create: `apps/api/src/shared/adapters/db/repositories/membership_repo.py`
- Test: `apps/api/tests/integration/test_membership_repo.py`

> Tipo de retorno para listagens com dados da pessoa: usamos um dataclass leve `MemberView` (membership + email/name da identidade) para a tela de usuários e para o chooser do login.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/integration/test_membership_repo.py
from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.repositories.identity_repo import IdentityRepository
from shared.adapters.db.repositories.membership_repo import MembershipRepository
from shared.domain.entities.identity import Identity
from shared.domain.entities.membership import Membership
from shared.domain.entities.user import UserRole

ACC1 = UUID("44444444-4444-4444-4444-444444444444")
ACC2 = UUID("55555555-5555-5555-5555-555555555555")


@pytest.fixture(autouse=True)
async def _setup(db_session: AsyncSession) -> None:
    await db_session.execute(text("DELETE FROM memberships"))
    await db_session.execute(text("DELETE FROM identities"))
    for acc, name in ((ACC1, "C1"), (ACC2, "C2")):
        await db_session.execute(
            text(
                "INSERT INTO accounts (id, name, settings, created_at) "
                "VALUES (:id, :n, '{}'::jsonb, NOW()) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": str(acc), "n": name},
        )
    await db_session.commit()


@pytest.mark.asyncio
async def test_list_active_by_identity_spans_accounts(db_session: AsyncSession) -> None:
    ident = Identity(email="multi@x.com", password_hash="h", name="Multi")
    await IdentityRepository(db_session).save(ident)
    repo = MembershipRepository(db_session)
    await repo.save(Membership(identity_id=ident.id, account_id=ACC1, role=UserRole.OPERATOR))
    await repo.save(Membership(identity_id=ident.id, account_id=ACC2, role=UserRole.ADMIN, is_owner=True))
    await db_session.commit()

    views = await repo.list_active_by_identity(ident.id)
    assert {v.account_id for v in views} == {ACC1, ACC2}
    owner_view = next(v for v in views if v.account_id == ACC2)
    assert owner_view.is_owner is True
    assert owner_view.account_name == "C2"


@pytest.mark.asyncio
async def test_get_by_identity_and_account(db_session: AsyncSession) -> None:
    ident = Identity(email="x@x.com", password_hash="h", name="X")
    await IdentityRepository(db_session).save(ident)
    repo = MembershipRepository(db_session)
    await repo.save(Membership(identity_id=ident.id, account_id=ACC1, role=UserRole.OPERATOR))
    await db_session.commit()

    m = await repo.get_by_identity_and_account(ident.id, ACC1)
    assert m is not None and m.role == UserRole.OPERATOR
    assert await repo.get_by_identity_and_account(ident.id, ACC2) is None


@pytest.mark.asyncio
async def test_count_active_admins(db_session: AsyncSession) -> None:
    ir = IdentityRepository(db_session)
    repo = MembershipRepository(db_session)
    for i, role in enumerate([UserRole.ADMIN, UserRole.ADMIN, UserRole.OPERATOR]):
        ident = Identity(email=f"a{i}@x.com", password_hash="h", name=f"A{i}")
        await ir.save(ident)
        await repo.save(Membership(identity_id=ident.id, account_id=ACC1, role=role))
    await db_session.commit()
    assert await repo.count_active_admins(ACC1) == 2
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/integration/test_membership_repo.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar o repo**

```python
# src/shared/adapters/db/repositories/membership_repo.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import AccountModel, IdentityModel, MembershipModel
from shared.domain.entities.membership import Membership
from shared.domain.entities.user import UserRole


@dataclass
class MemberView:
    """Membership + dados da identidade e da conta, para telas e chooser."""

    membership_id: str
    identity_id: str
    account_id: UUID
    account_name: str
    email: str
    name: str
    role: UserRole
    profile_id: UUID | None
    is_owner: bool
    is_active: bool
    must_change_password: bool
    has_avatar: bool
    created_at: datetime
    last_login_at: datetime | None


def _to_entity(m: MembershipModel) -> Membership:
    return Membership(
        id=m.id,
        identity_id=m.identity_id,
        account_id=m.account_id,
        role=UserRole(m.role),
        profile_id=m.profile_id,
        is_owner=m.is_owner,
        is_active=m.is_active,
        created_at=m.created_at,
    )


class MembershipRepository:
    """Session lifecycle managed by caller. Uses flush(), not commit()."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, m: Membership) -> None:
        self._session.add(
            MembershipModel(
                id=m.id,
                identity_id=m.identity_id,
                account_id=m.account_id,
                role=m.role.value,
                profile_id=m.profile_id,
                is_owner=m.is_owner,
                is_active=m.is_active,
            )
        )
        await self._session.flush()

    async def get_by_id(self, membership_id: str) -> Membership | None:
        row = (
            await self._session.execute(
                select(MembershipModel).where(MembershipModel.id == membership_id)
            )
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_identity_and_account(
        self, identity_id: str, account_id: UUID
    ) -> Membership | None:
        row = (
            await self._session.execute(
                select(MembershipModel)
                .where(MembershipModel.identity_id == identity_id)
                .where(MembershipModel.account_id == account_id)
            )
        ).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list_active_by_identity(self, identity_id: str) -> list[MemberView]:
        rows = (
            await self._session.execute(
                select(MembershipModel, AccountModel, IdentityModel)
                .join(AccountModel, AccountModel.id == MembershipModel.account_id)
                .join(IdentityModel, IdentityModel.id == MembershipModel.identity_id)
                .where(MembershipModel.identity_id == identity_id)
                .where(MembershipModel.is_active.is_(True))
                .order_by(AccountModel.name.asc())
            )
        ).all()
        return [self._view(m, acc, ident) for m, acc, ident in rows]

    async def list_by_account(
        self, account_id: UUID, page: int, page_size: int
    ) -> tuple[list[MemberView], int]:
        total = (
            await self._session.execute(
                select(func.count())
                .select_from(MembershipModel)
                .where(MembershipModel.account_id == account_id)
            )
        ).scalar_one()
        rows = (
            await self._session.execute(
                select(MembershipModel, AccountModel, IdentityModel)
                .join(AccountModel, AccountModel.id == MembershipModel.account_id)
                .join(IdentityModel, IdentityModel.id == MembershipModel.identity_id)
                .where(MembershipModel.account_id == account_id)
                .order_by(MembershipModel.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [self._view(m, acc, ident) for m, acc, ident in rows], total

    async def update_fields(
        self,
        membership_id: str,
        role: UserRole,
        is_active: bool,
        profile_id: UUID | None,
    ) -> None:
        m = (
            await self._session.execute(
                select(MembershipModel).where(MembershipModel.id == membership_id)
            )
        ).scalar_one()
        m.role = role.value
        m.is_active = is_active
        m.profile_id = profile_id
        await self._session.flush()

    async def delete(self, membership_id: str) -> None:
        m = (
            await self._session.execute(
                select(MembershipModel).where(MembershipModel.id == membership_id)
            )
        ).scalar_one()
        await self._session.delete(m)
        await self._session.flush()

    async def count_active_admins(self, account_id: UUID) -> int:
        return (
            await self._session.execute(
                select(func.count())
                .select_from(MembershipModel)
                .where(MembershipModel.account_id == account_id)
                .where(MembershipModel.role == UserRole.ADMIN.value)
                .where(MembershipModel.is_active.is_(True))
            )
        ).scalar_one()

    @staticmethod
    def _view(
        m: MembershipModel, acc: AccountModel, ident: IdentityModel
    ) -> MemberView:
        return MemberView(
            membership_id=m.id,
            identity_id=m.identity_id,
            account_id=m.account_id,
            account_name=acc.name,
            email=ident.email,
            name=ident.name,
            role=UserRole(m.role),
            profile_id=m.profile_id,
            is_owner=m.is_owner,
            is_active=m.is_active,
            must_change_password=ident.must_change_password,
            has_avatar=ident.avatar is not None,
            created_at=m.created_at,
            last_login_at=ident.last_login_at,
        )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/integration/test_membership_repo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/shared/adapters/db/repositories/membership_repo.py tests/integration/test_membership_repo.py
git commit -m "feat(db): MembershipRepository + MemberView"
```

## Task 8: Script de seed multi-tenant

**Files:**
- Create: `apps/api/src/shared/db/seed_multitenant.py`

> Objetivo: destravar dev/CI sem depender de produção. Idempotente. Cria 1 conta + 1 identity owner com credenciais conhecidas.

- [ ] **Step 1: Implementar o seed**

```python
# src/shared/db/seed_multitenant.py
from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import text

from shared.adapters.db.session import session_scope
from shared.adapters.kb.jwt_handler import hash_password

SEED_ACCOUNT_ID = UUID("00000000-0000-0000-0000-0000000000aa")
SEED_OWNER_EMAIL = "owner@seed.local"
SEED_OWNER_PASSWORD = "seed-owner-pass"
SEED_IDENTITY_ID = "00000000-0000-0000-0000-0000000000bb"
SEED_MEMBERSHIP_ID = "00000000-0000-0000-0000-0000000000cc"


async def run() -> None:
    pw_hash = hash_password(SEED_OWNER_PASSWORD)
    async with session_scope() as s:
        await s.execute(
            text(
                "INSERT INTO accounts (id, name, settings, created_at, legal_name) "
                "VALUES (:id, 'Seed Co', '{}'::jsonb, NOW(), 'Seed Co LTDA') "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": str(SEED_ACCOUNT_ID)},
        )
        await s.execute(
            text(
                "INSERT INTO identities (id, email, password_hash, name, must_change_password, is_active, created_at) "
                "VALUES (:id, :email, :pw, 'Seed Owner', FALSE, TRUE, NOW()) "
                "ON CONFLICT (email) DO NOTHING"
            ),
            {"id": SEED_IDENTITY_ID, "email": SEED_OWNER_EMAIL, "pw": pw_hash},
        )
        await s.execute(
            text(
                "INSERT INTO memberships (id, identity_id, account_id, role, is_owner, is_active, created_at) "
                "VALUES (:id, :iid, :acc, 'admin', TRUE, TRUE, NOW()) "
                "ON CONFLICT (identity_id, account_id) DO NOTHING"
            ),
            {"id": SEED_MEMBERSHIP_ID, "iid": SEED_IDENTITY_ID, "acc": str(SEED_ACCOUNT_ID)},
        )
        await s.commit()
    print(f"Seed OK: {SEED_OWNER_EMAIL} / {SEED_OWNER_PASSWORD} (account {SEED_ACCOUNT_ID})")


if __name__ == "__main__":
    asyncio.run(run())
```

- [ ] **Step 2: Rodar o seed contra o dev (com a migração aplicada)**

Run: `uv run python -m shared.db.seed_multitenant`
Expected: imprime `Seed OK: owner@seed.local / seed-owner-pass ...`

- [ ] **Step 3: Commit**

```bash
git add src/shared/db/seed_multitenant.py
git commit -m "feat(db): seed multi-tenant idempotente para dev/CI"
```

---

# FASE 2 — Autenticação multi-conta

## Task 9: JWT handler — claims do token completo

> O `create_access_token`/`verify_token` em `shared/adapters/kb/jwt_handler.py` já aceitam um dict arbitrário de claims (ver `auth.py`). Nenhuma mudança no handler é necessária; os novos claims (`identity_id`, `membership_id`) entram via o dict passado em `auth.py`. Esta task só confirma isso por teste.

**Files:**
- Test: `apps/api/tests/unit/test_jwt_claims.py`

- [ ] **Step 1: Escrever o teste**

```python
# tests/unit/test_jwt_claims.py
from __future__ import annotations

from shared.adapters.kb.jwt_handler import create_access_token, verify_token


def test_token_roundtrips_membership_claims():
    token = create_access_token(
        data={
            "sub": "a@x.com",
            "identity_id": "id-1",
            "account_id": "acc-uuid",
            "membership_id": "m-1",
            "role": "admin",
        },
        secret="s",
        expire_minutes=10,
    )
    payload = verify_token(token, secret="s")
    assert payload["identity_id"] == "id-1"
    assert payload["membership_id"] == "m-1"
    assert payload["account_id"] == "acc-uuid"
```

- [ ] **Step 2: Rodar e ver passar (ou ajustar handler se quebrar)**

Run: `uv run pytest tests/unit/test_jwt_claims.py -v`
Expected: PASS (sem mudança de código)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_jwt_claims.py
git commit -m "test(auth): claims identity_id/membership_id no JWT"
```

## Task 10: `AdminAuth` ganha `identity_id` e `membership_id`

**Files:**
- Modify: `apps/api/src/interface/http/deps/admin_auth.py`

- [ ] **Step 1: Atualizar o dataclass e o `_decode`**

Substituir o dataclass `AdminAuth` e o final do `_decode`:

```python
@dataclass
class AdminAuth:
    account_id: UUID | None
    user_email: str
    user_role: str
    user_id: str            # = identity_id (compat: continua sendo o id da pessoa)
    identity_id: str
    membership_id: str | None
    user_name: str
    must_change_password: bool
```

No `_decode`, ajustar o `return`:

```python
    email = payload["sub"]
    identity_id = payload.get("identity_id") or payload.get("user_id", "")
    return AdminAuth(
        account_id=account_id,
        user_email=email,
        user_role=payload.get("role", "operator"),
        user_id=identity_id,
        identity_id=identity_id,
        membership_id=payload.get("membership_id"),
        user_name=payload.get("user_name") or email,
        must_change_password=payload.get("must_change_password", False),
    )
```

> `user_id` continua existindo (= identity_id) para não quebrar consumidores como `delete_user` e `_check_permission`.

- [ ] **Step 2: Rodar a suíte de auth/permissions existente**

Run: `uv run pytest tests/unit/interface/admin -v`
Expected: PASS (testes existentes não passam `identity_id`; o fallback para `user_id` mantém compat)

- [ ] **Step 3: Type check**

Run: `uv run mypy src/interface/http/deps/admin_auth.py`
Expected: sem erros

- [ ] **Step 4: Commit**

```bash
git add src/interface/http/deps/admin_auth.py
git commit -m "feat(auth): AdminAuth com identity_id e membership_id"
```

## Task 11: Login multi-conta (rewrite do `login`) + endpoints `select-account` / `switch-account`

**Files:**
- Modify: `apps/api/src/interface/http/routers/admin/auth.py`
- Test: `apps/api/tests/unit/interface/admin/test_auth_login_multi.py`, `tests/unit/interface/admin/test_select_switch_account.py`

> Estratégia de teste: como o login agora usa repositórios, mockamos `IdentityRepository` e `MembershipRepository` via patch no namespace do router. Mantemos `get_db`/`get_settings` mockados como nos testes existentes.

- [ ] **Step 1: Escrever os testes que falham (login)**

```python
# tests/unit/interface/admin/test_auth_login_multi.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.adapters.kb import jwt_handler
from shared.domain.entities.identity import Identity
from shared.domain.entities.user import UserRole


def _app():
    from interface.http.routers.admin.auth import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    return app


def _view(account_id, role, is_owner=False, name="Co"):
    v = MagicMock()
    v.membership_id = str(uuid4())
    v.account_id = account_id
    v.account_name = name
    v.role = role
    v.is_owner = is_owner
    return v


def _patches(identity, member_views):
    sess = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    sess.commit = AsyncMock()

    ident_repo = MagicMock()
    ident_repo.get_by_email = AsyncMock(return_value=identity)
    ident_repo.touch_last_login = AsyncMock()

    memb_repo = MagicMock()
    memb_repo.list_active_by_identity = AsyncMock(return_value=member_views)

    return sess, ident_repo, memb_repo


@pytest.mark.asyncio
async def test_login_single_membership_returns_full_token():
    ident = Identity(email="a@x.com", password_hash=jwt_handler.hash_password("pw"), name="A", must_change_password=False)
    acc = uuid4()
    views = [_view(acc, UserRole.ADMIN, is_owner=True)]
    sess, ir, mr = _patches(ident, views)

    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        r = TestClient(_app()).post("/admin/auth/login", json={"email": "a@x.com", "password": "pw"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "authenticated"
        assert "access_token" in body
        payload = jwt_handler.verify_token(body["access_token"], secret="s")
        assert payload["account_id"] == str(acc)
        assert payload["membership_id"] == views[0].membership_id


@pytest.mark.asyncio
async def test_login_multi_membership_returns_chooser():
    ident = Identity(email="a@x.com", password_hash=jwt_handler.hash_password("pw"), name="A", must_change_password=False)
    views = [_view(uuid4(), UserRole.OPERATOR, name="C1"), _view(uuid4(), UserRole.ADMIN, name="C2")]
    sess, ir, mr = _patches(ident, views)

    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        r = TestClient(_app()).post("/admin/auth/login", json={"email": "a@x.com", "password": "pw"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "choose_account"
        assert "pre_auth_token" in body
        assert len(body["accounts"]) == 2
        assert {a["account_name"] for a in body["accounts"]} == {"C1", "C2"}


@pytest.mark.asyncio
async def test_login_no_membership_403():
    ident = Identity(email="a@x.com", password_hash=jwt_handler.hash_password("pw"), name="A", must_change_password=False)
    sess, ir, mr = _patches(ident, [])
    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        r = TestClient(_app()).post("/admin/auth/login", json={"email": "a@x.com", "password": "pw"})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_login_must_change_password_returns_change_status():
    ident = Identity(email="a@x.com", password_hash=jwt_handler.hash_password("pw"), name="A", must_change_password=True)
    views = [_view(uuid4(), UserRole.ADMIN)]
    sess, ir, mr = _patches(ident, views)
    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        r = TestClient(_app()).post("/admin/auth/login", json={"email": "a@x.com", "password": "pw"})
        assert r.status_code == 200
        assert r.json()["status"] == "must_change_password"
        assert "pre_auth_token" in r.json()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/interface/admin/test_auth_login_multi.py -v`
Expected: FAIL (resposta atual não tem `status`; repos não importados no router)

- [ ] **Step 3: Reescrever `auth.py` (login + select + switch)**

Substituir o conteúdo a partir dos imports e do `login`. Manter `_extract_login_ip`, `_save_auth_audit` e `logout` como estão. Imports a adicionar no topo:

```python
from shared.adapters.db.repositories.identity_repo import IdentityRepository
from shared.adapters.db.repositories.membership_repo import MembershipRepository
```

Novos modelos de resposta e helper de emissão de token:

```python
class AccountOption(BaseModel):
    membership_id: str
    account_id: str
    account_name: str
    role: str
    is_owner: bool


class LoginResultResponse(BaseModel):
    status: str  # "authenticated" | "choose_account" | "must_change_password"
    access_token: str | None = None
    pre_auth_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    accounts: list[AccountOption] | None = None
    must_change_password: bool = False


def _full_token(identity, view, settings) -> str:
    return create_access_token(
        data={
            "sub": identity.email,
            "identity_id": identity.id,
            "user_id": identity.id,
            "user_name": identity.name,
            "account_id": str(view.account_id),
            "membership_id": view.membership_id,
            "role": view.role.value,
            "must_change_password": identity.must_change_password,
        },
        secret=settings.jwt_secret,
        expire_minutes=settings.jwt_expire_minutes,
    )


def _pre_auth_token(identity, settings) -> str:
    return create_access_token(
        data={
            "sub": identity.email,
            "identity_id": identity.id,
            "user_id": identity.id,
            "user_name": identity.name,
            "scope": "pre_auth",
            "must_change_password": identity.must_change_password,
        },
        secret=settings.jwt_secret,
        expire_minutes=10,
    )
```

Novo `login`:

```python
@router.post("/auth/login", response_model=LoginResultResponse)
async def login(body: LoginRequest, request: Request, response: Response) -> LoginResultResponse:
    settings = get_settings()
    async with get_db() as session:
        identity = await IdentityRepository(session).get_by_email(body.email)
        if identity is None or not verify_password(body.password, identity.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"})
        if not identity.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

        views = await MembershipRepository(session).list_active_by_identity(identity.id)
        await IdentityRepository(session).touch_last_login(identity.id)
        await session.commit()

    if identity.must_change_password:
        return LoginResultResponse(
            status="must_change_password",
            pre_auth_token=_pre_auth_token(identity, settings),
            must_change_password=True,
        )
    if not views:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a nenhuma empresa")
    if len(views) == 1:
        token = _full_token(identity, views[0], settings)
        max_age = settings.jwt_expire_minutes * 60
        response.set_cookie(key=_COOKIE_NAME, value=token, httponly=True, samesite="lax", max_age=max_age, path="/")
        asyncio.create_task(_save_auth_audit(  # noqa: RUF006
            account_id=str(views[0].account_id), user_id=identity.id, user_email=identity.email,
            ip=_extract_login_ip(request), action="Login", user_agent=request.headers.get("user-agent", "")))
        return LoginResultResponse(status="authenticated", access_token=token, expires_in=max_age)
    return LoginResultResponse(
        status="choose_account",
        pre_auth_token=_pre_auth_token(identity, settings),
        accounts=[
            AccountOption(membership_id=v.membership_id, account_id=str(v.account_id), account_name=v.account_name, role=v.role.value, is_owner=v.is_owner)
            for v in views
        ],
    )
```

`select-account` e `switch-account` (ambos recebem o token via header/cookie e re-emitem o token completo após revalidar o vínculo):

```python
class SelectAccountRequest(BaseModel):
    account_id: str


async def _emit_for_account(identity_id: str, account_id_raw: str, request: Request, response: Response) -> LoginResultResponse:
    from uuid import UUID as _UUID

    settings = get_settings()
    try:
        account_uuid = _UUID(account_id_raw)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail="Invalid account_id") from e

    async with get_db() as session:
        identity = await IdentityRepository(session).get_by_id(identity_id)
        if identity is None or not identity.is_active:
            raise HTTPException(status_code=401, detail="Invalid identity")
        views = await MembershipRepository(session).list_active_by_identity(identity_id)
    match = next((v for v in views if str(v.account_id) == str(account_uuid)), None)
    if match is None:
        raise HTTPException(status_code=403, detail="Sem vínculo ativo com esta empresa")
    token = _full_token(identity, match, settings)
    max_age = settings.jwt_expire_minutes * 60
    response.set_cookie(key=_COOKIE_NAME, value=token, httponly=True, samesite="lax", max_age=max_age, path="/")
    return LoginResultResponse(status="authenticated", access_token=token, expires_in=max_age)


@router.post("/auth/select-account", response_model=LoginResultResponse)
async def select_account(
    body: SelectAccountRequest,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    nexoia_token: str | None = Cookie(default=None),
) -> LoginResultResponse:
    token = authorization.removeprefix("Bearer ").strip() if authorization and authorization.startswith("Bearer ") else nexoia_token
    if not token:
        raise HTTPException(status_code=401, detail="Missing credentials")
    payload = verify_token(token, secret=get_settings().jwt_secret)
    identity_id = payload.get("identity_id") or payload.get("user_id", "")
    return await _emit_for_account(identity_id, body.account_id, request, response)


@router.post("/auth/switch-account", response_model=LoginResultResponse)
async def switch_account(
    body: SelectAccountRequest,
    request: Request,
    response: Response,
    auth: AdminAuth = Depends(require_admin),
) -> LoginResultResponse:
    return await _emit_for_account(auth.identity_id, body.account_id, request, response)
```

Imports adicionais no topo do arquivo: `from fastapi import Depends` (já tem `Header`, `Cookie`) e `from interface.http.deps.admin_auth import AdminAuth, require_admin`.

> Atenção: `verify_token` pode lançar `JWTError` para token expirado/ inválido — embrulhe em try/except e levante 401 no `select_account` (replicar o tratamento de `_decode`).

- [ ] **Step 4: Rodar os testes de login**

Run: `uv run pytest tests/unit/interface/admin/test_auth_login_multi.py -v`
Expected: PASS

- [ ] **Step 5: Escrever e rodar os testes de select/switch**

```python
# tests/unit/interface/admin/test_select_switch_account.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.adapters.kb import jwt_handler
from shared.domain.entities.identity import Identity
from shared.domain.entities.user import UserRole


def _app():
    from interface.http.routers.admin.auth import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    return app


@pytest.mark.asyncio
async def test_select_account_emits_full_token():
    acc = uuid4()
    ident = Identity(email="a@x.com", password_hash="h", name="A", must_change_password=False)
    view = MagicMock(membership_id=str(uuid4()), account_id=acc, account_name="C", role=UserRole.ADMIN, is_owner=True)

    sess = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    ir = MagicMock(get_by_id=AsyncMock(return_value=ident))
    mr = MagicMock(list_active_by_identity=AsyncMock(return_value=[view]))

    pre = jwt_handler.create_access_token(
        data={"sub": "a@x.com", "identity_id": ident.id, "scope": "pre_auth"}, secret="s", expire_minutes=10
    )
    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        r = TestClient(_app()).post(
            "/admin/auth/select-account",
            json={"account_id": str(acc)},
            headers={"Authorization": f"Bearer {pre}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "authenticated"


@pytest.mark.asyncio
async def test_select_account_rejects_unlinked_account():
    ident = Identity(email="a@x.com", password_hash="h", name="A", must_change_password=False)
    sess = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    ir = MagicMock(get_by_id=AsyncMock(return_value=ident))
    mr = MagicMock(list_active_by_identity=AsyncMock(return_value=[]))
    pre = jwt_handler.create_access_token(
        data={"sub": "a@x.com", "identity_id": ident.id, "scope": "pre_auth"}, secret="s", expire_minutes=10
    )
    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        r = TestClient(_app()).post(
            "/admin/auth/select-account",
            json={"account_id": str(uuid4())},
            headers={"Authorization": f"Bearer {pre}"},
        )
        assert r.status_code == 403
```

Run: `uv run pytest tests/unit/interface/admin/test_select_switch_account.py -v`
Expected: PASS

- [ ] **Step 6: Rodar a suíte antiga de auth (deve ser substituída/ajustada)**

Run: `uv run pytest tests/unit/interface/admin/test_auth_router.py -v`
Expected: alguns testes antigos quebram (login agora retorna `status`). **Atualizar** `test_auth_router.py`: os testes de login devem passar a mockar `IdentityRepository`/`MembershipRepository` (copiar o padrão de `test_auth_login_multi.py`) e checar `status == "authenticated"`. Manter os testes de `logout`. Remover asserts obsoletos sobre `account_id: int`.

- [ ] **Step 7: Lint/type + commit**

Run: `uv run ruff check src/interface/http/routers/admin/auth.py && uv run mypy src/interface/http/routers/admin/auth.py`

```bash
git add src/interface/http/routers/admin/auth.py tests/unit/interface/admin/test_auth_login_multi.py tests/unit/interface/admin/test_select_switch_account.py tests/unit/interface/admin/test_auth_router.py
git commit -m "feat(auth): login multi-conta + select-account + switch-account"
```

## Task 12: Enforcement — `permissions.py` resolve via membership

**Files:**
- Modify: `apps/api/src/interface/http/deps/permissions.py`

> Hoje `resolve_user_permissions` lê `UserModel.profile_id` por `user_id`. Agora a permissão é do **membership**: usar `auth.membership_id` para achar o `profile_id`. Como a função só recebe `user_id`+`role`, vamos resolver via membership quando houver `membership_id`.

- [ ] **Step 1: Escrever teste unit (resolve por membership)**

```python
# tests/unit/interface/admin/test_permissions_membership.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interface.http.deps.admin_auth import AdminAuth
from interface.http.deps.permissions import _check_permission


def _auth(role, membership_id="m-1"):
    return AdminAuth(
        account_id=None, user_email="a@x.com", user_role=role, user_id="id-1",
        identity_id="id-1", membership_id=membership_id, user_name="A", must_change_password=False,
    )


@pytest.mark.asyncio
async def test_admin_bypasses_permission_check():
    out = await _check_permission(_auth("admin"), "users.manage")
    assert out.user_role == "admin"


@pytest.mark.asyncio
async def test_operator_denied_when_missing_permission():
    sess = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    with (
        patch("interface.http.deps.permissions.session_scope", return_value=sess),
        patch("interface.http.deps.permissions.resolve_membership_permissions", new=AsyncMock(return_value=set())),
    ):
        with pytest.raises(Exception) as exc:
            await _check_permission(_auth("operator"), "users.manage")
        assert "403" in str(exc.value) or "Permiss" in str(exc.value)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/interface/admin/test_permissions_membership.py -v`
Expected: FAIL (`resolve_membership_permissions` não existe)

- [ ] **Step 3: Implementar resolução por membership**

Adicionar função nova e ajustar `_check_permission`:

```python
from shared.adapters.db.models import MembershipModel, ProfilePermissionModel


async def resolve_membership_permissions(
    session: AsyncSession, *, membership_id: str | None, role: str
) -> set[str]:
    if role == "admin":
        return set(all_permission_keys())
    if membership_id is None:
        return set()
    profile_id = (
        await session.execute(
            select(MembershipModel.profile_id).where(MembershipModel.id == membership_id)
        )
    ).scalar_one_or_none()
    if profile_id is None:
        return set()
    rows = (
        await session.execute(
            select(ProfilePermissionModel.permission_key).where(
                ProfilePermissionModel.profile_id == profile_id
            )
        )
    ).scalars().all()
    return set(rows)
```

Atualizar `_check_permission` para usar a nova função:

```python
async def _check_permission(auth: AdminAuth, key: str) -> AdminAuth:
    if auth.user_role == "admin":
        return auth
    async with session_scope() as session:
        perms = await resolve_membership_permissions(
            session, membership_id=auth.membership_id, role=auth.user_role
        )
    if key not in perms:
        raise HTTPException(status_code=403, detail="Permissão insuficiente")
    return auth
```

> Manter `resolve_user_permissions` (legado) se algum outro módulo a importa; senão remover. Verificar com `grep -rn resolve_user_permissions src`.

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/interface/admin/test_permissions_membership.py -v`
Expected: PASS

- [ ] **Step 5: Lint/type + commit**

Run: `uv run ruff check src/interface/http/deps/permissions.py && uv run mypy src/interface/http/deps/permissions.py`

```bash
git add src/interface/http/deps/permissions.py tests/unit/interface/admin/test_permissions_membership.py
git commit -m "feat(auth): enforcement de permissoes via membership"
```

---

# FASE 3 — Gestão de funcionários (memberships)

## Task 13: `AddMemberUseCase` (vínculo silencioso)

**Files:**
- Create: `apps/api/src/shared/application/use_cases/admin/add_member.py`
- Test: `apps/api/tests/unit/admin/test_add_member.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/unit/admin/test_add_member.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.application.use_cases.admin.add_member import AddMemberUseCase
from shared.domain.entities.identity import Identity
from shared.domain.entities.user import UserRole


@pytest.mark.asyncio
async def test_new_email_creates_identity_and_sends_email():
    acc = uuid4()
    ident_repo = MagicMock(get_by_email=AsyncMock(return_value=None), save=AsyncMock())
    memb_repo = MagicMock(
        get_by_identity_and_account=AsyncMock(return_value=None), save=AsyncMock()
    )
    email_svc = MagicMock(send_email=AsyncMock())
    uc = AddMemberUseCase(identity_repo=ident_repo, membership_repo=memb_repo, email_service=email_svc)

    result = await uc.execute(account_id=acc, name="New", email="new@x.com", role=UserRole.OPERATOR, profile_id=None)

    assert result.created_identity is True
    ident_repo.save.assert_awaited_once()
    memb_repo.save.assert_awaited_once()
    email_svc.send_email.assert_awaited_once()  # senha enviada para e-mail novo


@pytest.mark.asyncio
async def test_existing_email_links_silently_no_new_password():
    acc = uuid4()
    existing = Identity(email="old@x.com", password_hash="keep", name="Old", must_change_password=False)
    ident_repo = MagicMock(get_by_email=AsyncMock(return_value=existing), save=AsyncMock())
    memb_repo = MagicMock(
        get_by_identity_and_account=AsyncMock(return_value=None), save=AsyncMock()
    )
    email_svc = MagicMock(send_email=AsyncMock())
    uc = AddMemberUseCase(identity_repo=ident_repo, membership_repo=memb_repo, email_service=email_svc)

    result = await uc.execute(account_id=acc, name="ignored", email="old@x.com", role=UserRole.ADMIN, profile_id=None)

    assert result.created_identity is False
    ident_repo.save.assert_not_awaited()  # NÃO cria identidade nova
    memb_repo.save.assert_awaited_once()  # só o vínculo
    email_svc.send_email.assert_not_awaited()  # sem senha nova


@pytest.mark.asyncio
async def test_duplicate_membership_raises():
    acc = uuid4()
    existing = Identity(email="dup@x.com", password_hash="h", name="Dup")
    ident_repo = MagicMock(get_by_email=AsyncMock(return_value=existing))
    memb_repo = MagicMock(get_by_identity_and_account=AsyncMock(return_value=MagicMock()))
    uc = AddMemberUseCase(identity_repo=ident_repo, membership_repo=memb_repo, email_service=MagicMock())

    with pytest.raises(ValueError):
        await uc.execute(account_id=acc, name="x", email="dup@x.com", role=UserRole.OPERATOR, profile_id=None)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/admin/test_add_member.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar o use case**

```python
# src/shared/application/use_cases/admin/add_member.py
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from shared.adapters.db.repositories.identity_repo import IdentityRepository
from shared.adapters.db.repositories.membership_repo import MembershipRepository
from shared.adapters.email.smtp_email_service import SmtpEmailService
from shared.adapters.email.templates import welcome_email
from shared.adapters.kb.jwt_handler import hash_password
from shared.domain.entities.identity import Identity
from shared.domain.entities.membership import Membership
from shared.domain.entities.user import UserRole
from shared.utils.password_generator import generate_temp_password


@dataclass
class AddMemberResult:
    membership: Membership
    identity: Identity
    created_identity: bool


@dataclass
class AddMemberUseCase:
    identity_repo: IdentityRepository
    membership_repo: MembershipRepository
    email_service: SmtpEmailService

    async def execute(
        self,
        account_id: UUID,
        name: str,
        email: str,
        role: UserRole,
        profile_id: UUID | None,
    ) -> AddMemberResult:
        identity = await self.identity_repo.get_by_email(email)
        created = False
        if identity is None:
            temp_password = generate_temp_password()
            identity = Identity(
                email=email,
                password_hash=hash_password(temp_password),
                name=name,
                must_change_password=True,
                is_active=True,
            )
            await self.identity_repo.save(identity)
            created = True

        existing = await self.membership_repo.get_by_identity_and_account(identity.id, account_id)
        if existing is not None:
            raise ValueError("Esta pessoa já faz parte desta empresa")

        membership = Membership(
            identity_id=identity.id,
            account_id=account_id,
            role=role,
            profile_id=profile_id,
            is_owner=False,
            is_active=True,
        )
        await self.membership_repo.save(membership)

        if created:
            subject, body = welcome_email(name=name, email=email, temp_password=temp_password)
            await self.email_service.send_email(to=email, subject=subject, body_html=body)

        return AddMemberResult(membership=membership, identity=identity, created_identity=created)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/admin/test_add_member.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/shared/application/use_cases/admin/add_member.py tests/unit/admin/test_add_member.py
git commit -m "feat(admin): AddMemberUseCase com vinculo silencioso"
```

## Task 14: Router `users.py` opera sobre memberships (CRUD + owner protegido)

**Files:**
- Modify: `apps/api/src/interface/http/routers/admin/users.py`
- Test: `apps/api/tests/unit/interface/admin/test_users_router_membership.py`

> O `{user_id}` nas rotas passa a ser `{membership_id}`. As respostas trazem `id = membership_id`. Owner (`is_owner`) é bloqueado em PUT/DELETE/reset.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/unit/interface/admin/test_users_router_membership.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.deps.admin_auth import AdminAuth
from interface.http.deps.permissions import require_permission
from shared.domain.entities.membership import Membership
from shared.domain.entities.user import UserRole


def _app():
    from interface.http.routers.admin.users import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    # bypass de permissão: injeta um auth admin fixo
    auth = AdminAuth(
        account_id=uuid4(), user_email="admin@x.com", user_role="admin", user_id="id-admin",
        identity_id="id-admin", membership_id="m-admin", user_name="Admin", must_change_password=False,
    )
    app.dependency_overrides[require_permission("users.manage")] = lambda: auth
    app.dependency_overrides[require_permission("users.view")] = lambda: auth
    return app, auth


@pytest.mark.asyncio
async def test_cannot_edit_owner_membership():
    app, auth = _app()
    owner = Membership(identity_id="id-owner", account_id=auth.account_id, role=UserRole.ADMIN, is_owner=True)
    sess = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    mr = MagicMock(get_by_id=AsyncMock(return_value=owner))
    with (
        patch("interface.http.routers.admin.users.session_scope", return_value=sess),
        patch("interface.http.routers.admin.users.MembershipRepository", return_value=mr),
    ):
        r = TestClient(app).put(
            f"/admin/users/{owner.id}",
            json={"name": "x", "role": "operator", "is_active": True, "profile_id": None},
        )
        assert r.status_code == 403
```

> Nota: como o nome interno do app override usa a fábrica `require_permission(...)` que cria uma função nova a cada chamada, o override por chave acima pode não casar. Estratégia robusta: no router, extrair as dependências para variáveis de módulo (`_perm_manage = require_permission("users.manage")`) e usar `Depends(_perm_manage)`; então o teste sobrescreve `_perm_manage`. Aplicar esse ajuste no router neste passo.

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/interface/admin/test_users_router_membership.py -v`
Expected: FAIL

- [ ] **Step 3: Reescrever `users.py`**

Pontos da reescrita (manter os schemas `UserResponse`/`CreateUserRequest`/`UpdateUserRequest`, ajustando `id` para representar membership):

1. Variáveis de módulo para as dependências (permite override em teste):
```python
_perm_view = require_permission("users.view")
_perm_manage = require_permission("users.manage")
```
2. `list_users`: usa `MembershipRepository(s).list_by_account(account_id, page, page_size)` → mapeia `MemberView` para `UserResponse` (`id = v.membership_id`, `profile_name` via `ProfileRepository.name_map`).
3. `create_user`: usa `AddMemberUseCase(identity_repo, membership_repo, email_svc)`; em `ValueError` → 409. Resposta com `id = result.membership.id`.
4. `update_user(membership_id)`: carrega membership; 404 se conta diferente; **403 se `is_owner`**; guard de último admin via `MembershipRepository.count_active_admins`; `update_fields` (role/is_active/profile). Para o nome da pessoa, atualizar a identidade via `IdentityRepository.update_profile(membership.identity_id, name)`.
5. `delete_user(membership_id)`: 404 se conta diferente; **403 se `is_owner`**; guard de último admin; `membership_repo.delete`. (Manter a proteção "não deletar o próprio membership": comparar `membership.identity_id == auth.identity_id`.)
6. `reset_password(membership_id)`: carrega membership; 404 se conta diferente; **403 se `is_owner`**; chama `ResetUserPasswordUseCase` operando na identidade (ver Task 15).

Mapeamento `MemberView → UserResponse`:
```python
def _view_to_response(v, profile_name=None) -> UserResponse:
    return UserResponse(
        id=v.membership_id, name=v.name, email=v.email, role=v.role.value,
        is_active=v.is_active, must_change_password=v.must_change_password,
        has_avatar=v.has_avatar, created_at=v.created_at, last_login_at=v.last_login_at,
        profile_id=str(v.profile_id) if v.profile_id else None, profile_name=profile_name,
    )
```

Bloco de proteção do owner (reutilizar em PUT/DELETE/reset):
```python
membership = await MembershipRepository(s).get_by_id(membership_id)
if membership is None or membership.account_id != account_id:
    raise HTTPException(status_code=404, detail="Membership not found")
if membership.is_owner:
    raise HTTPException(status_code=403, detail="Owner protegido: somente a plataforma pode alterá-lo")
```

- [ ] **Step 4: Rodar testes (novo + suíte existente do router de users)**

Run: `uv run pytest tests/unit/interface/admin/test_users_router_membership.py tests/unit/interface/admin/test_users_router.py -v`
Expected: novo PASS; **atualizar** `test_users_router.py` para o novo formato (membership_id, mocks de `MembershipRepository`/`AddMemberUseCase`). Ajustar até verde.

- [ ] **Step 5: Lint/type + commit**

```bash
uv run ruff check src/interface/http/routers/admin/users.py && uv run mypy src/interface/http/routers/admin/users.py
git add src/interface/http/routers/admin/users.py tests/unit/interface/admin/test_users_router_membership.py tests/unit/interface/admin/test_users_router.py
git commit -m "feat(admin): gestao de membership no router de users + owner protegido"
```

## Task 15: `/admin/me/*` e reset de senha operam na identidade

**Files:**
- Modify: `apps/api/src/interface/http/routers/admin/me.py`
- Modify: `apps/api/src/shared/application/use_cases/admin/reset_user_password.py`

> Ler o `me.py` atual primeiro (`apps/api/src/interface/http/routers/admin/me.py`) para casar assinaturas. Todos os handlers usam `auth.identity_id` em vez de `auth.user_id` sobre `IdentityRepository` (avatar, senha, perfil/nome). Como `auth.user_id == auth.identity_id`, a mudança principal é trocar `UserRepository` por `IdentityRepository`.

- [ ] **Step 1: Escrever/atualizar teste de troca de senha (me)**

Localizar o teste existente de `me`/password (se houver em `tests/unit/interface/admin/`) e adaptá-lo; senão criar `tests/unit/interface/admin/test_me_password.py` que mocka `IdentityRepository.update_password` e valida 204 com senha atual correta e 400/401 com senha atual errada. (Replicar padrão de mocks dos outros testes de router.)

```python
# tests/unit/interface/admin/test_me_password.py  (esqueleto a completar conforme me.py atual)
# - patch IdentityRepository no namespace de me.py
# - get_by_id retorna Identity com password_hash conhecido
# - PUT /admin/me/password com current correto -> 204 e update_password chamado com must_change_password=False
```

- [ ] **Step 2: Trocar `UserRepository` → `IdentityRepository` em `me.py`**

Em cada handler: `IdentityRepository(s)`; `get_by_id(auth.identity_id)`; `update_avatar`/`update_password`/`update_profile` com `auth.identity_id`. Manter a verificação de senha atual via `verify_password`.

- [ ] **Step 3: Atualizar `ResetUserPasswordUseCase`**

Trocar a dependência de `user_repo: UserRepository` por `identity_repo: IdentityRepository`; método `execute(account_id, identity_id)` agora: carrega identity por id, gera senha, `identity_repo.update_password(identity_id, hash, must_change_password=True)`, envia e-mail. Ajustar o `reset_password` do router de users (Task 14) para passar `identity_id=membership.identity_id`.

- [ ] **Step 4: Rodar testes**

Run: `uv run pytest tests/unit/admin/test_reset_user_password.py tests/unit/interface/admin/test_me_password.py -v`
Expected: PASS (atualizar `test_reset_user_password.py` para a nova assinatura)

- [ ] **Step 5: Lint/type + commit**

```bash
uv run ruff check src tests && uv run mypy src
git add src/interface/http/routers/admin/me.py src/shared/application/use_cases/admin/reset_user_password.py tests/unit/admin/test_reset_user_password.py tests/unit/interface/admin/test_me_password.py
git commit -m "feat(admin): me endpoints e reset de senha operam na identidade"
```

## Task 16: Suíte completa do backend verde

**Files:** nenhum novo — gate de qualidade.

- [ ] **Step 1: Rodar a suíte unit inteira**

Run: `uv run pytest tests/unit -q`
Expected: PASS. Corrigir qualquer teste legado que ainda assuma o modelo antigo de `users`.

- [ ] **Step 2: Rodar integration (com Docker)**

Run: `uv run pytest tests/integration -q`
Expected: PASS.

- [ ] **Step 3: Lint/format/type geral**

Run: `uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src`
Expected: sem erros.

- [ ] **Step 4: Commit (se houver ajustes)**

```bash
git add -A
git commit -m "test: suite backend verde apos cutover multi-tenant"
```

---

# FASE 4 — Frontend

## Task 17: Tipo do JWT + funções de auth

**Files:**
- Modify: `apps/web/src/features/auth/lib/jwt.ts`
- Modify: `apps/web/src/lib/auth.ts`

- [ ] **Step 1: Atualizar `jwt.ts`**

```typescript
export interface AuthTokenPayload {
  sub: string; // email
  user_id: string;
  identity_id: string;
  account_id: string; // UUID (corrige number)
  membership_id: string;
  role: "admin" | "operator";
  must_change_password: boolean;
  exp: number;
}
```
(Manter `decodeJwt` como está.)

- [ ] **Step 2: Atualizar `auth.ts` — login retorna desfecho + select/switch**

```typescript
export type AccountOption = {
  membership_id: string;
  account_id: string;
  account_name: string;
  role: "admin" | "operator";
  is_owner: boolean;
};

export type LoginResult =
  | { status: "authenticated"; access_token: string }
  | { status: "choose_account"; pre_auth_token: string; accounts: AccountOption[] }
  | { status: "must_change_password"; pre_auth_token: string };

export async function loginRequest(email: string, password: string): Promise<LoginResult> {
  const res = await fetch(`${API_URL}/admin/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "Credenciais inválidas");
  }
  return (await res.json()) as LoginResult;
}

export async function selectAccount(preAuthToken: string, accountId: string): Promise<string> {
  const res = await fetch(`${API_URL}/admin/auth/select-account`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${preAuthToken}` },
    body: JSON.stringify({ account_id: accountId }),
  });
  if (!res.ok) throw new Error("Falha ao selecionar empresa");
  const data = (await res.json()) as { access_token: string };
  return data.access_token;
}

export async function switchAccount(accountId: string): Promise<string> {
  const token = getToken();
  const res = await fetch(`${API_URL}/admin/auth/switch-account`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token ?? ""}` },
    body: JSON.stringify({ account_id: accountId }),
  });
  if (!res.ok) throw new Error("Falha ao trocar de empresa");
  const data = (await res.json()) as { access_token: string };
  return data.access_token;
}
```

- [ ] **Step 3: Type check**

Run: `cd apps/web && npx tsc --noEmit`
Expected: erros apenas nos consumidores que ainda usam o retorno antigo de `loginRequest` (corrigidos na Task 18).

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/auth/lib/jwt.ts apps/web/src/lib/auth.ts
git commit -m "feat(web): tipos e funcoes de auth multi-conta (select/switch)"
```

## Task 18: Tela de login com modal de escolha de conta

**Files:**
- Modify: `apps/web/src/app/(auth)/login/page.tsx`

> Ler o `page.tsx` atual primeiro para casar o estilo (design system NexoIA, `useToast`). Lógica: ao submeter, trata os 3 desfechos de `LoginResult`.

- [ ] **Step 1: Implementar o tratamento dos 3 desfechos**

Pseudocódigo a integrar no handler de submit (manter UI/estilo existentes):
```typescript
const result = await loginRequest(email, password);
if (result.status === "authenticated") {
  setToken(result.access_token);
  window.location.href = "/dashboard";
} else if (result.status === "must_change_password") {
  setToken(result.pre_auth_token); // pré-auth para a tela de troca
  window.location.href = "/change-password";
} else {
  // choose_account: guarda pre_auth_token + abre modal com result.accounts
  setPreAuthToken(result.pre_auth_token);
  setAccountOptions(result.accounts);
  setChooserOpen(true);
}
```
Modal de escolha (lista `accountOptions`, cada item mostra `account_name` + papel; `is_owner` ganha selo 🛡️). Ao clicar:
```typescript
const token = await selectAccount(preAuthToken, opt.account_id);
setToken(token);
window.location.href = "/dashboard";
```

- [ ] **Step 2: Type check + build**

Run: `cd apps/web && npx tsc --noEmit && npm run lint`
Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/(auth)/login/page.tsx
git commit -m "feat(web): modal de escolha de conta no login"
```

## Task 19: AuthContext com conta atual + seletor de empresa na TopBar

**Files:**
- Modify: `apps/web/src/features/auth/context/AuthContext.tsx`
- Modify: `apps/web/src/shared/components/layout/TopBar.tsx`

> Ler ambos os arquivos primeiro. O `AuthContext` decodifica o JWT — adicionar `accountId`, `membershipId` ao `AuthUser`. O seletor de empresa precisa da lista de contas da pessoa; obter via novo endpoint leve OU decodificar do estado. Decisão: adicionar `GET /admin/me/memberships` (lista as contas da identidade logada) para popular o seletor.

- [ ] **Step 1: Backend — endpoint `GET /admin/me/memberships`**

Em `me.py`, adicionar handler que usa `MembershipRepository.list_active_by_identity(auth.identity_id)` e retorna `[{account_id, account_name, role, is_owner, is_current}]` (marcando `is_current` = `auth.account_id`). Adicionar teste unit simples. Commit junto.

- [ ] **Step 2: AuthContext — expor `accountId`, `memberships`, `switchTo`**

Adicionar ao contexto: `accountId` (do JWT), `memberships` (fetch de `/admin/me/memberships`), e `switchTo(accountId)` que chama `switchAccount`, `setToken`, e recarrega (`window.location.reload()`).

- [ ] **Step 3: TopBar — dropdown de empresa**

Renderiza o nome da empresa atual; se `memberships.length > 1`, vira dropdown listando as outras; selecionar chama `switchTo`. Usar tokens do design system (`bg-surface-container`, etc.) e Material Symbols.

- [ ] **Step 4: Type check + lint + build**

Run: `cd apps/web && npx tsc --noEmit && npm run lint && npm run build`
Expected: build OK.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/auth/context/AuthContext.tsx apps/web/src/shared/components/layout/TopBar.tsx apps/api/src/interface/http/routers/admin/me.py
git commit -m "feat(web): seletor de empresa na TopBar + endpoint me/memberships"
```

## Task 20: Página de usuários usa membership_id

**Files:**
- Modify: `apps/web/src/features/users/*` (componentes, types, hooks)

> Ler os arquivos da feature `users` primeiro. As respostas do backend já usam `id = membership_id`; portanto o front em geral só precisa: (a) garantir que os ids tratados são membership_ids (sem mudança de shape, pois `UserResponse` manteve `id`), (b) exibir selo de owner (`is_owner`) — **adicionar `is_owner` ao `UserResponse`** do backend e ao type do front, (c) desabilitar editar/excluir quando `is_owner`, (d) aviso no reset de senha ("redefine o acesso em todo o sistema").

- [ ] **Step 1: Backend — incluir `is_owner` no `UserResponse`**

Adicionar `is_owner: bool = False` ao schema `UserResponse` (users.py) e preencher a partir de `MemberView.is_owner` no `_view_to_response`. Atualizar testes do router. Commit.

- [ ] **Step 2: Front — type + UI**

Adicionar `is_owner: boolean` ao type de usuário do front. Na tabela/cards: selo 🛡️ "Owner" quando `is_owner`; botões de editar/excluir `disabled` quando `is_owner`. No diálogo de reset de senha, texto de aviso.

- [ ] **Step 3: Type check + lint + build**

Run: `cd apps/web && npx tsc --noEmit && npm run lint && npm run build`
Expected: OK.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/users apps/api/src/interface/http/routers/admin/users.py apps/api/tests/unit/interface/admin/test_users_router_membership.py
git commit -m "feat(web): owner protegido na UI de usuarios + aviso de reset global"
```

---

# FASE 5 — Rollout

## Task 21: Validação em DEV

**Files:** nenhum.

- [ ] **Step 1: Subir infra + aplicar migração**

Run (de `apps/api/`): `docker compose up -d postgres redis && uv run alembic upgrade heads`
Expected: `aa01mt` aplicada; verificar contagens com um `SELECT count(*) FROM identities/memberships`.

- [ ] **Step 2: Suíte completa verde**

Run: `uv run pytest -q && cd ../web && npx tsc --noEmit && npm run build`
Expected: tudo verde.

- [ ] **Step 3: Smoke manual (dev)**

Subir `uv run uvicorn main:app --reload` + `npm run dev`. Testar: login 1-conta entra direto; criar funcionário com e-mail novo (recebe senha) e com e-mail existente (vínculo silencioso); criar 2ª conta via seed e logar o mesmo e-mail → modal aparece; trocar de empresa na TopBar; tentar editar owner → bloqueado.

- [ ] **Step 4: Checkpoint — só seguir se tudo OK em dev.**

## Task 22: Deploy em produção (com backup e rollback)

**Files:** nenhum (deploy via merge → CI).

- [ ] **Step 1: Backup do banco de produção (antes do deploy)**

> Via acesso de produção (ver memória `project_prod_access`). Executar `pg_dump` do banco `nexoia` para arquivo datado **antes** do merge.

- [ ] **Step 2: Abrir PR da branch de implementação → review → merge**

O merge em `main` dispara o CI (`alembic upgrade heads` roda a `aa01mt` com as 5 asserts; se qualquer assert falhar, a transação reverte e o deploy falha sem corromper dados).

- [ ] **Step 3: Pós-deploy — smoke em produção**

Verificar `https://api-flow.ianexo.com.br/health` OK; login do `suporte@ianexo.com.br` com a senha atual funciona; os 2 operators logam; G2 Educação intacta (leads/conversas visíveis).

- [ ] **Step 4: Em caso de falha — rollback**

`alembic downgrade -1` + redeploy da imagem anterior. Como `users` permanece intacta, o estado anterior é restaurado.

- [ ] **Step 5: PR de contract (FUTURO, separado)**

Só após produção validada por alguns dias: novo PR que dropa `users` (e limpa `admin_users`). **Não** faz parte desta entrega.

---

## Notas de verificação do plano (self-review)

- **Cobertura do spec:** modelo (Tasks 1-4), login multi-conta + select/switch (Task 11), enforcement por membership (Task 12), gestão de funcionários + vínculo silencioso + owner protegido (Tasks 13-14), reset global + me (Task 15), backfill+verificação (Tasks 4-5), seed (Task 8), rollout dev→prod (Tasks 21-22), frontend chooser/switcher/users (Tasks 17-20). Garantias de produção cobertas pela migração não-destrutiva (Task 4) e backup/rollback (Task 22).
- **Consistência de nomes:** `IdentityRepository`, `MembershipRepository`, `MemberView`, `AddMemberUseCase`, `_full_token`, `_pre_auth_token`, `resolve_membership_permissions`, claims `identity_id`/`membership_id` — usados de forma idêntica entre tasks.
- **Pendência conhecida (resolver na execução):** `me.py` e a feature `users` do front precisam ser lidos antes de editar (assinaturas exatas) — sinalizado nas Tasks 15, 19, 20.
