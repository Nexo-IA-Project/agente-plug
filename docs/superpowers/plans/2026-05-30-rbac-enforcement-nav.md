# RBAC Enforcement + Navegação + Perfis em cards — Implementation Plan

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Trava real por permissão (front+back, encapsulada), navegação reorganizada (grupo Configurações recolhível, sem Contas), Perfis em cards.

**Architecture:** Admin bypassa (acesso total). Permissões resolvidas do banco por request; `/me` expõe lista; frontend lê do `/me` e guarda rotas via wrapper reutilizável; Sidebar filtra por permissão. Sobre `feat/settings-reorg-tenant` (já tem a reorg do #74).

**Tech:** FastAPI/SQLAlchemy/Pydantic; Next.js 15 + TS + Tailwind (NexoIA).

---

### Task 1: Backend — catálogo + resolução de permissões + require_permission
**Files:** modify `apps/api/src/shared/domain/permissions/catalog.py`; create `apps/api/src/interface/http/deps/permissions.py`; create `apps/api/tests/unit/interface/admin/test_require_permission.py`.

- catalog.py: adicionar `_p("profiles","view","Ver perfis")` e `_p("profiles","manage","Gerenciar perfis")`; adicionar `"profiles.view","profiles.manage"` a `ADMIN_ONLY_KEYS`.
- `permissions.py`:
```python
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from interface.http.deps.admin_auth import AdminAuth, require_admin
from shared.adapters.db.models import ProfilePermissionModel, UserModel
from shared.domain.permissions.catalog import all_permission_keys

async def resolve_user_permissions(session: AsyncSession, *, user_id: str, role: str) -> set[str]:
    if role == "admin":
        return set(all_permission_keys())
    u = (await session.execute(select(UserModel.profile_id).where(UserModel.id == user_id))).scalar_one_or_none()
    if u is None:
        return set()
    rows = (await session.execute(select(ProfilePermissionModel.permission_key).where(ProfilePermissionModel.profile_id == u))).scalars().all()
    return set(rows)

def require_permission(key: str):
    async def _dep(auth: AdminAuth = Depends(require_admin)) -> AdminAuth:
        if auth.user_role == "admin":
            return auth
        from shared.adapters.db.session import session_scope
        async with session_scope() as s:
            perms = await resolve_user_permissions(s, user_id=auth.user_id, role=auth.user_role)
        if key not in perms:
            raise HTTPException(status_code=403, detail="Permissão insuficiente")
        return auth
    return _dep
```
- Tests: admin→passa sem profile; operador com a key→passa; sem a key→403; resolve_user_permissions(admin)==all; sem profile==∅.

- [ ] testes → implementar → `uv run pytest tests/unit/interface/admin/test_require_permission.py -q` + ruff → commit

---

### Task 2: Backend — `/admin/me` retorna `permissions`
**Files:** modify `apps/api/src/interface/http/routers/admin/me.py`; modify `apps/api/tests/unit/interface/admin/test_me_router.py`.

- `MeResponse` + `permissions: list[str] = []`. Em `get_me`/`update_me`, resolver via `resolve_user_permissions(s, user_id=auth.user_id, role=auth.user_role)` e ordenar. (Reaproveita session já aberta.)
- Teste: admin → permissions == all_permission_keys(); operador → as do profile (mock).

- [ ] testes → implementar → pytest + ruff → commit

---

### Task 3: Backend — aplicar require_permission nos endpoints
**Files:** modify routers em `apps/api/src/interface/http/routers/admin/`: products, documents(kb), search, leads, followup(onboarding), meta_templates, users, profiles, settings, api_tokens, dlq. Ajustar testes unit afetados.

Regra: trocar `Depends(require_admin_role)`/`require_admin` por `Depends(require_permission("<key>"))` conforme o mapa. GET/list → `*.view`; create/edit/delete/manage conforme catálogo (ex.: products POST→`products.create`, PUT→`products.edit`, DELETE→`products.delete`; users mutações→`users.manage`, GET→`users.view`; profiles GET→`profiles.view`, POST/PUT/DELETE→`profiles.manage`; meta_templates DELETE→`templates.delete`, POST→`templates.create`, GET→`templates.view`; kb DELETE→`kb.delete`, upload→`kb.create`, GET→`kb.view`; settings GET→`settings.view`, PUT→`settings.edit_credentials`; api_tokens GET→`tokens.view`, POST/DELETE→`tokens.manage`; leads GET/export→`leads.view`/`leads.export`; onboarding GET→`onboarding.view`, mut→create/edit/delete, reorder→edit, resolve→`onboarding.resolve_unmapped`; dlq→`onboarding.view` ou `settings.view` (decidir: usar `settings.view`)). `/admin/me*`, `/admin/auth/*`, `/admin/smtp`(removido), platform-config (mantém require_admin_role) e change-password **não** mudam.
- Atualizar testes que assumiam require_admin_role (a maioria mocka auth via dependency_overrides; o override deve passar a sobrescrever `require_admin` base — manter funcionando). Garantir suite verde.

- [ ] implementar por router → `uv run pytest tests/unit -q` verde → ruff + mypy(baseline) → commit

---

### Task 4: Frontend — PermissionContext + usePermission + guard + mapa de rotas
**Files:** create `apps/web/src/features/auth/context/PermissionContext.tsx`; modify `apps/web/src/features/auth/hooks/usePermission.ts`; create `apps/web/src/features/auth/lib/routePermissions.ts`; create `apps/web/src/features/auth/components/RequirePermission.tsx`; wire provider no layout admin (`apps/web/src/app/(admin)/layout.tsx`). modify `MeResponse` type em `features/profile/types.ts` (+ permissions).

- `MeResponse` type + `permissions: string[]`.
- PermissionProvider: ao montar (se autenticado) chama `getMe()`, guarda `permissions: Set<string>` + `isAdmin` (role do /me) + `loading`. Expõe via context.
- `usePermission()` reescrito: `{ isAdmin, can(key:string):boolean, loading }` — `can` = isAdmin || permissions.has(key). (Manter compat: se algum lugar usa `can("manage_users")` antigo, migrar para keys reais — buscar usos e ajustar.)
- `routePermissions.ts`: `{ "/dashboard":"dashboard.view", "/kb":"kb.view", "/products":"products.view", "/leads":"leads.view", "/onboarding":"onboarding.view", "/onboarding/pendencias":"onboarding.view", "/templates":"templates.view", "/users":"users.view", "/profiles":"profiles.view", "/settings":"settings.view", "/settings/comportamento":"settings.view", "/settings/tokens":"tokens.view" }` + helper `permForPath(pathname)`.
- `<RequirePermission perm>`: usa usePermission; loading→spinner; !can→bloco "Acesso restrito a quem tem permissão"; senão children.
- Registrar `<PermissionProvider>` dentro do AuthProvider no layout (admin).

- [ ] implementar → `npx tsc --noEmit` → commit

---

### Task 5: Frontend — Sidebar (grupo recolhível + remover Contas + filtro por permissão + animação)
**Files:** modify `apps/web/src/shared/components/layout/Sidebar.tsx`.

- Remover item "Contas". Remover FOOTER "Tokens de API" (migra para o grupo).
- Itens top-level com `perm` (usar routePermissions): Painel, Base de Conhecimento, Produtos, Leads, Onboarding, Pendências, Templates, Usuários, Perfis. Filtrar por `can(item.perm)`.
- Grupo **Configurações** (recolhível): filhos Integrações(`/settings`, settings.view), Comportamento(`/settings/comportamento`, settings.view), API/Tokens(`/settings/tokens`, tokens.view). Mostrar o grupo se algum filho visível. Abre automaticamente quando `pathname` casa um filho; estado `open` controlado (useState, init = rota atual é filha). Clique no header só toggla. Conteúdo anima: container `overflow-hidden` com transição `max-height` (0 ↔ suficiente) + `opacity`, ~320ms ease-in-out; chevron rota 200ms. Filhos com indentação.
- Manter NavItem visual; sub-itens levemente menores/indentados.

- [ ] implementar → `npx tsc --noEmit` → commit

---

### Task 6: Frontend — página Comportamento separada
**Files:** create `apps/web/src/app/(admin)/settings/comportamento/page.tsx`; modify `apps/web/src/app/(admin)/settings/page.tsx` (remover BehaviorSection).
- Nova página renderiza `<RequirePermission perm="settings.view"><BehaviorSection .../></RequirePermission>` (carrega settings via getAccountSettings, igual a /settings). Header "Comportamento da IA".
- `/settings`: remover render+import de BehaviorSection (fica só ChatNexoSection + IntegrationSection "Outras integrações"). Envolver conteúdo admin com `<RequirePermission perm="settings.view">`.

- [ ] implementar → `npx tsc --noEmit` → commit

---

### Task 7: Frontend — Perfis em cards + guard
**Files:** create `apps/web/src/features/profiles/components/ProfileCards.tsx`; modify `apps/web/src/app/(admin)/profiles/page.tsx` (usar ProfileCards + RequirePermission); remover `ProfileListTable.tsx`.
- `ProfileCards`: props `{profiles: ProfileListItem[], onEdit, onDelete}`. Grade `grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4`. Card: header com ícone (badge) + nome + badge "Sistema" se is_system; corpo com 2 stats (ícone `lock`/`shield` "N permissões", ícone `group` "N usuários"); rodapé com ações Editar/Excluir (ocultas se is_system, com indicador "Perfil de sistema"). Hover sutil (`hover:border-primary/40`, leve elevação), tokens NexoIA, refinado. Sem hex.
- page: trocar `<ProfileListTable .../>` por `<ProfileCards .../>`; envolver tudo em `<RequirePermission perm="profiles.view">`. Remover import e arquivo ProfileListTable.

- [ ] implementar → `npx tsc --noEmit` → commit

---

### Task 8: Frontend — aplicar guard às demais páginas
**Files:** modify pages em `apps/web/src/app/(admin)/`: dashboard, kb, products, leads, onboarding (+pendencias), templates(+new), users, settings/tokens. Envolver o conteúdo com `<RequirePermission perm="<key do routePermissions>">`. Não quebrar layout/SSR ("use client" onde já é). Páginas de conta própria (/profile, /change-password) NÃO recebem guard.
- [ ] implementar → `npx tsc --noEmit` → commit

---

### Task 9: Verificação + review + PR
- [ ] `cd apps/api && uv run pytest tests/unit -q` verde; `uv run ruff check src tests`; `uv run ruff format --check src tests`; `uv run mypy src` (≤ baseline).
- [ ] `cd apps/web && npx tsc --noEmit` limpo.
- [ ] requesting-code-review sobre o branch (foco: enforcement correto, sem lockout de admin, guard cobrindo todas as rotas, animação).
- [ ] push; atualizar PR #74 (título/descrição para o escopo ampliado) ou abrir PR novo. NÃO mergear sem OK.

## Arquivos críticos
- `apps/api/src/interface/http/deps/permissions.py` (novo) + catalog.py + me.py + os 10 routers admin.
- `apps/web/src/features/auth/{context/PermissionContext,hooks/usePermission,lib/routePermissions,components/RequirePermission}` + Sidebar + páginas.
