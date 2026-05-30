# Base multi-tenant + modelo de Perfis/Permissões (RBAC por tenant)

**Data:** 2026-05-30
**Status:** Aprovado (design)

## Context

O sistema nasceu single-tenant ("engessado"), mas a estrutura já é ~2/3 multi-tenant: existe a
tabela `accounts` (PK UUID) e 14 tabelas de domínio já usam `account_id UUID` + FK. Porém **8
tabelas** (`users`, `smtp_config`, `knowledge_documents`, `knowledge_chunks`, `kb_usage_logs`,
`access_cases`, `refund_cases`) ainda usam `account_id` como **Integer sem FK**, e o JWT carrega
`account_id` inteiro (`1`) que hoje é ignorado (o tenant real é resolvido como "primeira conta"
via `get_default_account_uuid`).

A visão de negócio tem **duas camadas**:
- **Plataforma (dono — nós):** painel separado, futuro, onde criamos tenants e damos um Admin a
  cada cliente. **Fora do escopo agora** — só precisa que a base seja compatível.
- **Tenant (cliente):** cada conta tem um **Admin** que cria **perfis ilimitados** (gerente,
  operador, etc.) com permissões granulares (tela + ações) para seus usuários.

**Esta entrega = só a BASE**, data-safe, sem mudar o comportamento atual:
1. Unificar a estrutura para multi-tenant (account_id UUID + FK em todas as tabelas).
2. Criar o **modelo de dados** de perfis/permissões + catálogo + seed dos perfis padrão na conta #1.
3. O sistema continua funcionando **idêntico** — **sem UI nova de perfis** e **sem trocar os
   guards de autorização** (enforcement e telas vêm na próxima fase).

**Resultado pretendido:** por baixo dos panos tudo vira tenant-scoped e correto; cada usuário
passa a ter um `profile_id`; e fica tudo pronto para a próxima fase ligar o enforcement por
permissão e a UI de gestão de perfis — sem retrabalho de estrutura nem risco aos dados.

## Não-objetivos (explícito)
- **Sem** UI de criação/edição de perfis (próxima fase).
- **Sem** trocar `require_admin_role`/`require_admin` por checagem de permissão (próxima fase).
- **Sem** painel da plataforma / criação de tenants / super-admin global (fase futura).
- **Sem** resolver o tenant pelo usuário logado em runtime (continua "primeira conta"); webhooks idem.
- Nenhum dado pode ser perdido.

## Decisões registradas para a PRÓXIMA fase (não implementar agora)
- **Enforcement:** checagem de permissão via **lookup no banco por request** (resolvido a partir
  do usuário do JWT), cacheável — mudança de permissão vale na hora, sem re-login.
- **Catálogo é a fonte da verdade** (código); o perfil Admin de cada tenant recebe todas as
  permissões do catálogo no seed.

---

## Parte 1 — Fundação multi-tenant (migração data-safe)

**Garantir a conta #1.** Hoje a primeira conta é resolvida por `SELECT accounts ORDER BY
created_at LIMIT 1` e já existe em produção (products/flows referenciam ela). A migração captura
esse UUID; se nenhuma conta existir (ambiente novo), cria uma (`name='Conta Principal'`)
idempotentemente.

**Unificar `account_id` Integer → UUID + FK** nas 8 tabelas. Como existe **exatamente 1 tenant**,
o backfill é determinístico e seguro. Padrão por tabela (migração Alembic):
1. `ADD COLUMN account_id_uuid UUID NULL`.
2. `UPDATE <tabela> SET account_id_uuid = :account_uuid` (o UUID da conta #1 — todas as linhas).
3. Recriar constraints que dependiam do antigo `account_id` (ex.: `uq_users_account_email`,
   `uq` de `smtp_config.account_id`) sobre a nova coluna.
4. `DROP COLUMN account_id` (integer); `ALTER COLUMN account_id_uuid RENAME TO account_id`;
   `SET NOT NULL`; adicionar `FOREIGN KEY (account_id) REFERENCES accounts(id)` + índice.

Tabelas afetadas: `users`, `smtp_config`, `knowledge_documents`, `knowledge_chunks`,
`kb_usage_logs`, `access_cases`, `refund_cases`. (`admin_users` já foi dropada — ignorar.)
`downgrade` reverte para Integer preenchendo `1`.

**Auth/JWT vira UUID (mantendo comportamento).**
- `UserModel.account_id` passa a ser UUID (consequência da migração).
- Login (`auth.py`) passa a colocar o `account_id` UUID (string) no JWT; `AdminAuth.account_id`
  vira `UUID`. `require_admin_sse`/`_decode` ajustados ao novo tipo.
- `AccountConfigRepository.get(account_id: UUID)` aceita UUID (hoje recebe `1` e ignora).
  **Comportamento inalterado:** continua resolvendo a conta via `get_default_account_uuid` /
  primeira conta. Trocar os call-sites de `get(account_id=1)` para `get(account_id=<uuid>)` (o
  uuid resolvido), sem mudar a lógica de resolução. Isso deixa a base pronta para a Fase 3 passar
  a confiar em `auth.account_id` diretamente.

> Os routers de domínio continuam usando `get_default_account_uuid(session)` — **sem mudança de
> comportamento**. A unificação é estrutural; a resolução por usuário fica para a Fase 3.

---

## Parte 2 — Modelo de Perfis/Permissões (dados + catálogo + seed)

**Catálogo de permissões (código — fonte da verdade).** Um módulo Python define todas as chaves
de permissão, agrupadas por **módulo/tela** com **ações**. Formato da chave: `"<modulo>.<acao>"`.
Ações típicas: `view`, `create`, `edit`, `delete`, e específicas quando fizer sentido
(`settings.edit_credentials`, `settings.edit_smtp`, `users.manage`, `templates.delete`,
`tokens.manage`, `documents.delete`). Os módulos seguem as telas mapeadas: dashboard, kb,
accounts, products, leads, onboarding, onboarding/pendencias, templates, users, settings,
settings/tokens, profile. Cada entrada do catálogo tem: `key`, `module` (rótulo p/ agrupar na
futura UI), `label`, `action`. O catálogo é versionado em código e serve para: (a) seed do perfil
Admin (recebe todas as chaves), (b) futura UI de marcação, (c) futura validação de enforcement.

**Tabelas novas (migração Alembic):**
- `profiles`: `id UUID PK`, `account_id UUID FK accounts ON DELETE CASCADE`, `name String`,
  `is_system Boolean default false` (perfil semente, não deletável), `created_at`, `updated_at`.
  `UniqueConstraint(account_id, name)`.
- `profile_permissions`: `id UUID PK`, `profile_id UUID FK profiles ON DELETE CASCADE`,
  `permission_key String(100)`. `UniqueConstraint(profile_id, permission_key)`. (Conjunto de
  chaves concedidas ao perfil. Chaves validadas contra o catálogo no nível de aplicação.)
- `users.profile_id`: `UUID NULL FK profiles ON DELETE SET NULL` (nullable na introdução; será
  preenchido no seed e usado pelo enforcement na próxima fase). **Mantém-se `users.role`** por
  enquanto (os guards atuais ainda usam) — será aposentado na fase de enforcement.

**Seed por conta (na conta #1):**
- Perfil **"Admin"** — `is_system=true`. Recebe **todas** as chaves do catálogo
  (`profile_permissions` = catálogo inteiro). Não deletável. (É o perfil máximo *do tenant*; o
  super-admin global da plataforma é outra camada, futura.)
- Perfil **"Operador"** — editável (`is_system=false`). Recebe um subconjunto que reproduz o
  acesso atual do operador (tudo menos as ações hoje "admin-only": `users.manage`,
  `templates.delete`, `documents.delete`, `tokens.manage`, `settings.edit_credentials`,
  `settings.edit_smtp`).
- **Atribuição:** usuários existentes com `role='admin'` → `profile_id` do Admin; `role='operator'`
  → `profile_id` do Operador. (Idempotente; baseado no `role` atual.)

> Importante: como o **enforcement não muda nesta PR**, os perfis/permissões ficam **gravados e
> corretos**, mas ainda não governam acesso. O comportamento de autorização permanece o atual
> (`require_admin_role` etc.). Isso satisfaz "deixar a base pronta" sem risco.

**Domínio (entidades + repos):** entidades `Profile` e `PermissionKey` (catálogo) + um
`ProfileRepository` (criar/listar/seed) e ajuste no `UserRepository` para gravar/ler `profile_id`.
Sem novos endpoints HTTP nesta PR (a API de gestão de perfis é da próxima fase).

---

## Arquitetura / isolamento
- **Catálogo** (`shared/domain/permissions/catalog.py`): única fonte das chaves; sem dependência
  externa; testável isoladamente.
- **`profiles` / `profile_permissions`**: dados puros, tenant-scoped por `account_id`.
- **Migrações**: uma para a fundação (unificação account_id) e uma para o RBAC (tabelas + seed) —
  ou duas revisões encadeadas. Ambas idempotentes e reversíveis.

## Estratégia de testes
- **Unit:** catálogo (todas as chaves únicas, formato `modulo.acao`); `ProfileRepository`
  (criar perfil, anexar permissões, seed Admin = catálogo completo); mapeamento role→profile.
- **Integration (testcontainers + alembic):**
  - Migração da fundação: seed/exist conta; após upgrade, `users.account_id` etc. são UUID com FK;
    contagem de linhas preservada (nenhuma perdida); `downgrade` volta a Integer.
  - Migração RBAC: `profiles`/`profile_permissions` criadas; conta #1 tem perfis "Admin"
    (com catálogo completo) e "Operador"; usuários existentes ganham `profile_id` conforme `role`.
  - Smoke: app sobe (`import main`), login ainda funciona, JWT carrega account_id UUID, e os
    fluxos atuais (leads/products/onboarding) seguem resolvendo a primeira conta sem erro.

## Verificação manual (pós-deploy)
- Login funciona; telas atuais idênticas.
- `select id from accounts` → 1 conta; `users.account_id` = esse UUID; `profiles` tem Admin+Operador;
  cada user tem `profile_id`. `pg_stat_activity`/contagens sem perda de dados.

## Riscos & rollback
- Migração aditiva-then-swap por tabela; `downgrade` recria Integer. Como só há 1 tenant, backfill
  é não-ambíguo. Reverter = `alembic downgrade` + redeploy do commit anterior.
- **JWTs antigos no deploy:** tokens já emitidos carregam `account_id` inteiro (`1`). Como o
  runtime ignora esse valor (resolve a primeira conta), `AdminAuth.account_id` deve aceitar o
  valor de forma tolerante (não fazer `UUID(...)` estrito que quebre o token antigo) — ou tratar
  como opcional. Sessões expiram em 60min de qualquer forma. Garantir no `_decode` que um token
  legado não derruba o login até o próximo refresh.

## Fora de escopo (resumo)
UI de perfis; enforcement por permissão; painel da plataforma/criação de tenants; super-admin
global; resolução de tenant por usuário em runtime; roteamento de webhook por conta.
