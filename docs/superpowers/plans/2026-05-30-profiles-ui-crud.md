# Perfis: CRUD + UI (sem enforcement) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Tenant-admin gerencia perfis (CRUD) com seletor de permissões por módulo e atribui perfil aos usuários — sem enforcement (guards seguem por role).

**Architecture:** Reusa base RBAC do #71 (entity/repo/models/catálogo). Adiciona métodos ao `ProfileRepository`, router `/admin/profiles` + catálogo, `profile_id` nos schemas de usuário, e feature `profiles/` no frontend espelhando `users/`.

**Tech Stack:** FastAPI async + SQLAlchemy + Pydantic; Next.js 15 + TS + Tailwind (design system NexoIA).

---

### Task 1: ProfileRepository — get_by_id, update, delete, list_with_counts

**Files:**
- Modify: `apps/api/src/shared/adapters/db/repositories/profile_repo.py`
- Test: `apps/api/tests/integration/test_profile_repo.py` (estende o existente)

Adicionar métodos (manter os existentes create/get_by_name/list_by_account):
- `get_by_id(self, account_id: UUID, profile_id: UUID) -> Profile | None` — busca scoped por account; popula permissions via `_perms`.
- `update(self, account_id: UUID, profile_id: UUID, name: str, permissions: list[str]) -> Profile | None` — atualiza name, substitui o conjunto de permissions (delete-all + re-insert dedup preservando ordem), atualiza updated_at, flush. Retorna None se não achar.
- `delete(self, account_id: UUID, profile_id: UUID) -> bool` — apaga (cascade nas permissions); retorna False se não achar.
- `list_with_counts(self, account_id: UUID) -> list[dict]` — retorna por perfil: `{id, name, is_system, permission_count, user_count}`. `user_count` = COUNT de users com aquele profile_id. Uma query com subselects ou LEFT JOINs agregados.

TDD: estender o teste de integração existente cobrindo update (troca de permissions), delete, get_by_id (scoped/None) e list_with_counts (contagens corretas após criar perfil + atribuir a um user).

- [ ] Escrever testes (integration, testcontainers — NÃO tocar o DB local de dev)
- [ ] Implementar métodos
- [ ] `uv run pytest tests/integration/test_profile_repo.py -q` (ou via testcontainer) verde
- [ ] `uv run ruff check src tests` + commit

---

### Task 2: Router `/admin/profiles` + catálogo de permissões

**Files:**
- Create: `apps/api/src/interface/http/routers/admin/profiles.py`
- Modify: `apps/api/src/main.py` (registrar router)
- Test: `apps/api/tests/unit/interface/admin/test_profiles_router.py`

Endpoints (todos `Depends(require_admin_role)`; account via `get_default_account_uuid(session)`):
- `GET /admin/profiles` → `list[ProfileListItem]` (id, name, is_system, permission_count, user_count) usando `list_with_counts`.
- `GET /admin/profiles/{id}` → `ProfileDetail` (id, name, is_system, permissions[]) | 404.
- `POST /admin/profiles` → 201 `ProfileDetail`. Body `{name, permissions[]}`. Valida cada key ∈ `all_permission_keys()` (senão 422). is_system sempre False. 409 se `get_by_name` já existe.
- `PUT /admin/profiles/{id}` → `ProfileDetail`. 404 se não existe; **403 se is_system**; 409 se renomear p/ nome existente; 422 key inválida.
- `DELETE /admin/profiles/{id}` → 204. 404; **403 se is_system**.
- `GET /admin/permissions/catalog` → lista agrupada por módulo: `[{module, permissions:[{key, action, label}]}]`, derivada de `PERMISSION_CATALOG` (preservar ordem do catálogo).

Schemas Pydantic no próprio router (ProfileListItem, ProfileDetail, CreateProfileRequest, UpdateProfileRequest, PermissionItem, PermissionGroup).

Padrão: seguir um router admin existente (ex.: `products.py`) para estilo (router = APIRouter, `configure(...)` se houver injeção, session_scope).

TDD (unit, mockando repo/session como nos outros test_*_router): list, create (201 + 409 dup + 422 key inválida), update (200 + 403 system + 404), delete (204 + 403 system), catalog (agrupado e completo).

- [ ] Testes unit
- [ ] Implementar router + registrar em main.py
- [ ] `uv run pytest tests/unit/interface/admin/test_profiles_router.py -q` verde
- [ ] ruff + commit

---

### Task 3: `profile_id` nos schemas e use cases de usuário

**Files:**
- Modify: `apps/api/src/interface/http/routers/admin/users.py` (schemas CreateUserRequest/UpdateUserRequest/UserResponse + handlers)
- Modify: use cases em `apps/api/src/shared/application/use_cases/admin/` (`create_user.py`, `reset_user_password.py` se necessário, e o update)
- Modify: `apps/api/src/interface/http/routers/admin/me.py` (incluir profile no /admin/me se fizer sentido — opcional, manter mínimo)
- Test: `apps/api/tests/unit/interface/admin/test_users_router.py` (estender)

- `UserResponse`: + `profile_id: str | None`, `profile_name: str | None`.
- `CreateUserRequest` / `UpdateUserRequest`: + `profile_id: str | None = None`.
- create/update: setar profile_id no UserModel; validar que o profile pertence à account (senão 400/422). list_users + get: join leve para `profile_name`.

TDD: create com profile_id válido → response traz profile_id/name; profile_id inexistente → 400/422; update troca profile.

- [ ] Testes unit
- [ ] Implementar
- [ ] pytest unit users verde + ruff + commit

---

### Task 4: Frontend — api.ts + types

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/features/profiles/types.ts`
- Modify: `apps/web/src/features/users/types.ts`

- `lib/api.ts`: `listProfiles()`, `getProfile(id)`, `createProfile(input)`, `updateProfile(id,input)`, `deleteProfile(id)`, `getPermissionCatalog()`.
- `features/profiles/types.ts`: `Profile {id,name,is_system,permissions:string[]}`, `ProfileListItem {id,name,is_system,permission_count,user_count}`, `PermissionItem {key,action,label}`, `PermissionGroup {module,permissions:PermissionItem[]}`, `CreateProfileInput {name,permissions:string[]}`.
- `features/users/types.ts`: `User` + `profile_id:string|null`, `profile_name:string|null`; `CreateUserInput`/`UpdateUserInput` + `profile_id:string|null`.

- [ ] Implementar; `npx tsc --noEmit` limpo; commit

---

### Task 5: Frontend — feature profiles (tabela + drawer) + página + sidebar

**Files:**
- Create: `apps/web/src/features/profiles/components/ProfileListTable.tsx`
- Create: `apps/web/src/features/profiles/components/ProfileDrawer.tsx`
- Create: `apps/web/src/app/(admin)/profiles/page.tsx`
- Modify: `apps/web/src/shared/components/layout/Sidebar.tsx` (item "Perfis", adminOnly, icon "badge")

- `ProfileListTable`: colunas Nome (+ badge "Sistema" se is_system), Permissões (count), Usuários (count), Ações (Editar/Excluir — ocultas/disabled em system). Usar tokens NexoIA + Material Symbols.
- `ProfileDrawer`: `Drawer` compartilhado. Campo Nome. Seletor de permissões agrupado por módulo: para cada `PermissionGroup`, uma seção com checkbox-mestre (estado checked/indeterminate/unchecked conforme seleção das filhas; clicar marca/desmarca o módulo todo) + checkboxes das ações (label PT-BR). Estado controlado por `Set<string>` de keys. Carrega catálogo via `getPermissionCatalog()`. Perfil system → read-only (campos disabled, sem submit). onSubmit chama create/update.
- `page.tsx`: espelha `users/page.tsx` (load listProfiles, abrir drawer p/ criar/editar, deletar com confirmação via toast/dialog).
- Sidebar: adicionar item.

- [ ] Implementar; `npx tsc --noEmit` limpo; commit

---

### Task 6: Frontend — atribuição de perfil no usuário

**Files:**
- Modify: `apps/web/src/features/users/components/UserDrawer.tsx` (select de Perfil)
- Modify: `apps/web/src/features/users/components/UserListTable.tsx` (coluna Perfil)
- Modify: `apps/web/src/app/(admin)/users/page.tsx` (carregar perfis p/ o select; passar profile_id no submit)

- UserDrawer: `<select>`/combobox de Perfil populado por `listProfiles()` (opção "Sem perfil" = null). Inclui profile_id no input.
- UserListTable: coluna "Perfil" mostrando `profile_name` ou "—".

- [ ] Implementar; `npx tsc --noEmit` limpo; commit

---

### Task 7: Verificação final + PR

- [ ] `cd apps/api && uv run pytest tests/unit -q` (todos) verde
- [ ] `uv run ruff check src tests` + `uv run mypy src` (sem erros novos além do baseline 112)
- [ ] `cd apps/web && npx tsc --noEmit` limpo
- [ ] (Integration relevante: test_profile_repo via testcontainer) verde
- [ ] Revisão final (requesting-code-review) sobre o branch
- [ ] push + abrir PR (base main). NÃO mergear sem OK do usuário.

## Arquivos críticos
- `apps/api/src/shared/adapters/db/repositories/profile_repo.py`
- `apps/api/src/interface/http/routers/admin/profiles.py` + `main.py`
- `apps/api/src/interface/http/routers/admin/users.py`
- `apps/api/src/shared/domain/permissions/catalog.py` (fonte das permissions; não alterar)
- `apps/web/src/features/profiles/*`, `apps/web/src/app/(admin)/profiles/page.tsx`, `Sidebar.tsx`, `lib/api.ts`, `features/users/*`
