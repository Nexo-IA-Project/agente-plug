# RBAC Enforcement + Navegação/IA + Perfis em cards — design

**Data:** 2026-05-30
**Status:** Aprovado (design). Entrega única, sobre a main (com #71/#72/#73) + a reorg do #74.

## Context

A base RBAC (#71) e a UI de perfis (#73) existem, mas **as permissões não bloqueiam nada** — só há trava por `role` (admin/operator). A página `/profiles` nem tem permission key. O dono quer: (1) **trava real e encapsulada** por permissão em toda página/rota (front + back), pra ninguém acessar o que não deve; (2) **navegação profissional** (grupo "Configurações" recolhível com Integrações + API/Tokens + Comportamento; remover "Contas"); (3) **Perfis em cards** (não tabela).

## Decisões travadas
- **Admin = acesso total (bypass).** `require_permission` e `/me` tratam `role=="admin"` como todas as permissões. Evita lockout e dispensa migration de re-seed.
- **Permissões resolvidas do banco por request** (não no JWT) — muda na hora, sem re-login. Cacheável (opcional).
- **Atendentes ChatNexo** ficam em Integrações (são chaves do ChatNexo). **Comportamento da IA** é item próprio (não é integração).
- **Entrega única** (PR único, revisado com cuidado).

## Catálogo de permissões
`shared/domain/permissions/catalog.py`: **adicionar** `profiles.view` e `profiles.manage`, ambas em `ADMIN_ONLY_KEYS`. Manter `accounts.view` no catálogo (página some, key inócua). Sem migration: admin bypassa; operador não recebe `profiles.*` (correto). Comportamento e Integrações usam `settings.view`.

Mapa rota→permissão exigida (para guard de página e endpoints):
| Rota / página | Permissão |
|---|---|
| /dashboard | dashboard.view |
| /kb | kb.view |
| /products | products.view |
| /leads | leads.view |
| /onboarding · /onboarding/pendencias | onboarding.view · onboarding.view (ação resolver = onboarding.resolve_unmapped) |
| /templates | templates.view |
| /users | users.view |
| /profiles | profiles.view |
| /settings (Integrações) | settings.view |
| /settings/comportamento | settings.view |
| /settings/tokens | tokens.view |

## Backend — enforcement
- **`require_permission(key: str)`** (novo, em `interface/http/deps/`): depende de `require_admin` (AdminAuth). Se `auth.user_role == "admin"` → passa. Senão resolve as permissões do usuário pelo `profile_id` (via `ProfileRepository` / query `profile_permissions`) e exige `key`; 403 se faltar. Resolução do banco por request; helper `resolve_user_permissions(session, user) -> set[str]` reutilizável (admin → `set(all_permission_keys())`; sem profile → conjunto vazio).
- **Aplicar nos endpoints**: trocar/duplicar guards. GET de listagem → `*.view`; mutações → `*.create/edit/delete/manage`. Routers afetados: documents/kb, products, leads, onboarding(followup), templates(meta), users, profiles, settings, api_tokens, dlq. Endpoints de conta-própria (`/admin/me*`, auth, change-password) **não** mudam (qualquer logado).
- **`/admin/me`**: adicionar `permissions: list[str]` (admin → `all_permission_keys()`; senão as do profile). (Mantém profile_id/profile_name do #73.)

## Frontend — guard encapsulado + navegação + cards
- **PermissionContext/provider**: ao montar, busca `/admin/me` e expõe `permissions: Set<string>`, `isAdmin`, `can(key)`. `usePermission()` reescrito para usar isso (não mais lista hardcoded). Loga out/!auth → vazio.
- **Guard de rota reutilizável**: componente `<RequirePermission perm="...">{children}</RequirePermission>` (ou hook `useRouteGuard(perm)`) que, enquanto carrega permissões, mostra spinner; sem a permissão → tela "Acesso restrito" (ou redirect /dashboard). **Cada página protegida envolve seu conteúdo** com o guard (padrão a ser seguido por toda página nova). Mapa rota→perm centralizado num módulo (`features/auth/lib/routePermissions.ts`) para reuso no guard e no Sidebar.
- **Sidebar**: itens filtrados por `can(perm)` (não mais `adminOnly` solto). **Remover "Contas".** Grupo **"Configurações"** recolhível (abre/fecha com transição suave ~300ms, chevron que gira, conteúdo com height+opacity): filhos **Integrações** (`/settings`), **Comportamento** (`/settings/comportamento`), **API / Tokens** (`/settings/tokens`). Grupo abre automaticamente se a rota atual for filha. Clique no pai só expande/recolhe.
- **Comportamento**: criar página `/settings/comportamento` que renderiza a `BehaviorSection`; **remover** a BehaviorSection da página `/settings` (que fica só Integrações: ChatNexo+Atendentes, Hubla, Meta).
- **Perfis em cards**: substituir `ProfileListTable` por `ProfileCards` — grade responsiva `grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4`; cada card: nome, badge "Sistema" (se is_system), dois indicadores (permissões / usuários) com ícone, ações Editar/Excluir (ocultas em system). Refinado (hover sutil, tokens NexoIA), bonito individualmente. Página passa a envolver com `<RequirePermission perm="profiles.view">`.

## Animação (suave, conforme pedido)
Sidebar: transição de `max-height`/`opacity`/`transform` ~300–350ms `ease-in-out` (sem lib; CSS), chevron rotação 200ms. Nada abrupto.

## Testes
- Backend unit: `resolve_user_permissions` (admin=all; operator=profile; sem profile=∅); `require_permission` (admin passa, operador com/sem a key → 200/403); `/me` retorna permissions; routers-chave com novo guard (ex.: operador sem `profiles.view` → 403 em /admin/profiles; admin → 200).
- Catálogo: `profiles.view/manage` presentes e em ADMIN_ONLY_KEYS.
- Frontend: `tsc --noEmit`; guard bloqueia sem permissão (smoke via lógica do hook).

## Verificação manual
- Logar como operador (sem profiles.view) → /profiles bloqueado (front) e /admin/profiles → 403 (back); itens somem do Sidebar. Admin → tudo acessível. Menu Configurações abre/fecha suave. Contas sumiu. Perfis em cards.

## Não-objetivos
- Painel Super Admin (futuro) — OpenAI/SMTP seguem fora do tenant (#74).
- Cache distribuído de permissões (resolução por request basta agora).
