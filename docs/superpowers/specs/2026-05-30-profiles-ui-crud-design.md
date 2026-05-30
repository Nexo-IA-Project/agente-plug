# Perfis: CRUD + UI (sem enforcement) — design

**Data:** 2026-05-30
**Status:** Aprovado (design). Implementar em PR própria, sobre a base RBAC do #71.

## Context

A base de RBAC já existe (#71): tabelas `profiles` + `profile_permissions`, `users.profile_id` (FK SET NULL), entity `Profile`, `ProfileRepository` (create/get_by_name/list_by_account), catálogo de 26 permissões em código (`shared/domain/permissions/catalog.py`, com `module` + `label` PT-BR + 6 `ADMIN_ONLY_KEYS`), e seed dos perfis **Admin** (system, 26 perms) e **Operador** (20 perms). Em produção: 1 admin→Admin, 2 operators→Operador.

Falta a camada visível: o tenant-admin não tem como criar/editar perfis nem atribuí-los a usuários.

**Resultado pretendido:** admin gerencia perfis (CRUD) com um seletor de permissões agrupado por módulo, e atribui um perfil a cada usuário. Tudo funcional e visível no painel.

## Não-objetivos (decisão explícita 2026-05-30)

- **Enforcement fica para uma PR separada.** Os guards continuam `require_admin_role`/`require_admin` (por role). Esta PR NÃO troca guards nem coloca permissions no JWT. As permissões definidas aqui ainda não bloqueiam ações — só são geridas e atribuídas. Isso reduz o risco em produção (a PR de enforcement mexe em todos os routers + login e será focada/testada à parte).
- Painel super-admin da plataforma (fase futura).

## Modelo de dados

Sem migration. Usa o schema do #71 como está.

## Backend (`apps/api`)

### ProfileRepository — novos métodos
- `get_by_id(account_id, profile_id) -> Profile | None`
- `update(account_id, profile_id, name, permissions) -> Profile | None` (dedup de permissions; substitui o conjunto; flush)
- `delete(account_id, profile_id) -> bool`
- `list_with_counts(account_id) -> list[ProfileSummary]` — cada item com `permission_count` e `user_count` (usuários com aquele `profile_id`). Pode ser uma estrutura/dict de retorno dedicada para a listagem.

### Router `/admin/profiles` (`require_admin_role`)
```
GET    /admin/profiles                 → [ProfileListItem] (id, name, is_system, permission_count, user_count)
GET    /admin/profiles/{id}            → ProfileDetail (id, name, is_system, permissions[])
POST   /admin/profiles                 → ProfileDetail (201) | 409 nome duplicado
PUT    /admin/profiles/{id}            → ProfileDetail | 404 | 409 nome | 403 se is_system
DELETE /admin/profiles/{id}            → 204 | 404 | 403 se is_system
GET    /admin/permissions/catalog      → [{module, label_module?, permissions:[{key, action, label}]}] agrupado por módulo
```
- **Validação de permissions:** toda key recebida deve estar em `all_permission_keys()` (rejeita keys inválidas com 422).
- **`is_system` é imutável:** PUT/DELETE em perfil system → 403. PUT pode até deixar editar nome? Não — system é totalmente read-only nesta fase.
- **account_id:** resolvido via `get_default_account_uuid(session)` (single-tenant), padrão dos outros routers admin.
- Registrar router em `main.py`.

### Schemas de usuário — adicionar perfil
- `UserResponse`: + `profile_id: str | None`, `profile_name: str | None`.
- `CreateUserRequest`: + `profile_id: str | None` (opcional).
- `UpdateUserRequest`: + `profile_id: str | None`.
- `create_user`/`update_user` use cases: setar `profile_id` (validar que o profile existe na account; se inválido → 422/400).
- `list_users` e `/admin/me`: incluir profile_id/profile_name no response (join leve com profiles).

## Frontend (`apps/web`)

### Feature `features/profiles/`
- `types.ts`: `Profile` (id, name, is_system, permissions: string[]), `ProfileListItem` (+ permission_count, user_count), `PermissionCatalogGroup` ({module, permissions:[{key, action, label}]}).
- `components/ProfileListTable.tsx`: tabela com Nome, badge "Sistema" quando is_system, nº de permissões, nº de usuários, ações (Editar/Excluir — desabilitadas/ocultas em system).
- `components/ProfileDrawer.tsx`: usa o `Drawer` compartilhado. Campo Nome + **seletor de permissões agrupado por módulo**: cada módulo é uma seção com um checkbox-mestre "marcar módulo inteiro" (indeterminate quando parcial) e os checkboxes das ações (usando `label` PT-BR do catálogo). Perfil system abre em modo read-only.

### Página e navegação
- `app/(admin)/profiles/page.tsx`: header + ProfileListTable + ProfileDrawer (espelha a página de usuários).
- Sidebar: novo item `{ label: "Perfis", href: "/profiles", icon: "badge", adminOnly: true }`.

### Atribuição no usuário
- `features/users/types.ts`: `User` + `profile_id`/`profile_name`; inputs + `profile_id`.
- `UserDrawer.tsx`: select de Perfil (lista de perfis da account).
- `UserListTable.tsx`: coluna "Perfil".
- `lib/api.ts`: `listProfiles`, `getProfile`, `createProfile`, `updateProfile`, `deleteProfile`, `getPermissionCatalog`.

### Design
Seguir o design system NexoIA (tokens semânticos, Material Symbols, Drawer com scale-from-center, `useToast`). Sem hex hardcoded. Refinamento: agrupamento claro por módulo, estados indeterminate no checkbox-mestre, badge "Sistema" distinta, contadores discretos.

## Testes
- Unit (backend): router de profiles (list/create/update/delete, 403 em system, 409 nome dup, 422 key inválida); catálogo agrupado; user schemas com profile_id (create/update validando profile da account); ProfileRepository (get_by_id/update/delete/list_with_counts) via integration testcontainers.
- Frontend: `npx tsc --noEmit` limpo.

## Verificação manual
- Criar perfil "Gerente" com um subconjunto de permissões → aparece na lista com contadores.
- Editar/excluir perfil custom; Admin (system) read-only.
- Atribuir "Gerente" a um usuário; coluna Perfil reflete.
- (Enforcement não muda nada ainda — esperado.)
