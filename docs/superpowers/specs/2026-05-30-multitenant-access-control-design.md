# PRD / Design — Controle de Acesso Multi-Tenant (Identidade Única + Login Multi-Conta)

**Data:** 2026-05-30
**Status:** Aprovado para planejamento
**Escopo:** Núcleo de controle de acesso multi-tenant. **NÃO** inclui o painel de super-admin de plataforma (PRD próprio, fase posterior).

---

## 1. Problema e objetivo

Hoje a tabela `users` amarra numa única linha três conceitos: a **credencial** (email + `password_hash`), a **conta** (`account_id` FK NOT NULL) e o **papel** (`role` + `profile_id`), com unicidade de email *por conta* (`uq_users_account_email`). Isso impede o cenário desejado: **uma pessoa (um login, uma senha) trabalhando em N empresas**, possivelmente com papéis diferentes em cada uma.

Não há auto-onboarding: as contas são criadas internamente pela equipe (a criação em si fica no PRD do painel de plataforma). Esta entrega resolve o **modelo de acesso e o fluxo de login** para múltiplas empresas, mais a **gestão de funcionários dentro de cada empresa**.

**Objetivo:** separar **Identidade** de **Vínculo (membership)**, entregando login único, modal de escolha de conta, troca de conta, owner protegido, vínculo silencioso de funcionários por e-mail e enforcement por conta — **sem perder nenhum dado do único tenant em produção**.

### Cenários que precisam funcionar (todos via "sem trava")
- Funcionário vinculado a N contas com o **mesmo e-mail e a mesma senha**.
- Mesma pessoa sendo **operator numa empresa e admin/owner em outra**.
- Adicionar um funcionário cujo e-mail **já existe** → cria só o vínculo, sem nova senha.
- No login, se houver mais de um vínculo, **modal de escolha** mostrando o papel em cada empresa.

---

## 2. Modelo de dados

### `identities` — a pessoa / credencial (1 por e-mail, global)
| coluna | tipo | nota |
|---|---|---|
| id | UUID PK | |
| email | varchar **UNIQUE GLOBAL** | substitui o unique por conta |
| password_hash | varchar | a senha **única** |
| name | varchar | nome da pessoa |
| avatar | bytea null | movido de `users` |
| must_change_password | bool (def. true) | nível credencial |
| is_active | bool (def. true) | kill switch global da pessoa |
| created_at | timestamptz | |
| last_login_at | timestamptz null | |

### `memberships` — vínculo pessoa ↔ empresa ↔ papel
| coluna | tipo | nota |
|---|---|---|
| id | UUID PK | |
| identity_id | UUID FK→identities NOT NULL | |
| account_id | UUID FK→accounts NOT NULL | |
| role | varchar (`admin`/`operator`) | papel **nesta** conta |
| profile_id | UUID FK→profiles null | permissões custom **nesta** conta |
| is_owner | bool (def. false) | **owner protegido** — só plataforma/seed seta |
| is_active | bool (def. true) | ativo **nesta** empresa |
| created_at | timestamptz | |

**Constraints:**
- `unique(identity_id, account_id)` — um vínculo por pessoa por conta.
- `partial unique(account_id) where is_owner = true` — no máximo 1 owner por conta.
- Índices: `(account_id)`, `(identity_id)`.

### Tabelas mantidas
- `profiles` e `profile_permissions` **inalteradas** (já são por conta). O `profile_id` migra de `users` para `memberships`.
- `accounts` ganha campos de cadastro **nullable** (mínimo para o backfill preencher fake): `legal_name`, `tax_id`, `contact_email`, `contact_phone`. CRUD completo desses campos é o PRD do painel de plataforma.

### Fora de escopo
- Limpeza da tabela/legado órfão `admin_users` (não é tocada).
- Drop de `users` (acontece em PR separado **após** validação em produção — ver Seção 6).

### Alternativa descartada
Manter tudo em `users` e apenas "linkar por e-mail" — quebra a senha única (cada linha teria sua própria senha) e não entrega login único. Por isso o split Identidade/Membership.

---

## 3. Fluxo de login e troca de conta

### `POST /admin/auth/login` — `{email, password}`
```
1. Busca identity por email (GLOBAL, sem account)        ← corrige o bug atual de login sem scope
2. verify_password (bcrypt) + checa identity.is_active    → 401 / 403
3. Se must_change_password == true:
     emite "pre-auth token" curto (flag must_change)
     frontend força troca de senha ANTES de escolher conta
4. Carrega memberships ATIVOS (join accounts, só contas ativas):
     0 vínculos  → 403 "sem acesso a nenhuma empresa"
     1 vínculo   → emite TOKEN COMPLETO scoped naquela conta → entra direto
     N vínculos  → emite "pre-auth token" + lista
                   [{account_id, account_name, role, is_owner}] → modal de escolha
```

### `POST /admin/auth/select-account` — `{account_id}` (com pre-auth token)
Revalida no banco que a identidade tem membership ativo na conta → emite **token completo**.

### `POST /admin/auth/switch-account` — `{account_id}` (com token válido)
Re-emite token para outro membership da **mesma** identidade. Não pede senha de novo. Revalida o vínculo no banco.

### Token completo (claims JWT)
`identity_id`, `account_id`, `membership_id`, `role`, `email`, `must_change_password`, `exp`.
O `account_id` **sempre** vem do token (conta escolhida). `get_default_account_uuid()` deixa de ser fonte de verdade (mantido só como fallback temporário durante a transição).

### Segurança
- `select-account` / `switch-account` **revalidam o vínculo no banco** a cada chamada — nunca confiam só no token.
- Pre-auth token tem escopo mínimo (só trocar senha / escolher conta), não acessa dados.
- Token de conta cujo vínculo foi removido enquanto logado → próximo request 401 → volta ao login/chooser.

---

## 4. Gestão de funcionários dentro do tenant

As rotas `/admin/users` passam a operar sobre **memberships da conta atual** (a do token).

### `GET /admin/users`
Lista memberships da `account_id` do token (nome/e-mail/role/profile/is_active/is_owner). **Não** revela outras empresas da pessoa (privacidade).

### `POST /admin/users` — `{email, name?, role, profile_id?}`
```
busca identity por email (global)
├── NÃO existe → cria identity (gera senha, must_change_password=true)
│                + membership(account atual, role, profile) + envia e-mail com senha
└── JÁ existe  → VÍNCULO SILENCIOSO: cria só o membership(account atual, ...)
                 sem nova senha. Opcional: e-mail "você foi adicionado à Empresa X".
                 Resposta expõe só nome/e-mail — nada das outras contas.
guard: já existe membership (identity, account) → 409 "já faz parte desta empresa"
```

### `PUT /admin/users/{membership_id}`
Muda `role`/`profile_id`/`is_active` **do membership** (não toca a identidade).

### `DELETE /admin/users/{membership_id}`
Apaga **o membership** (tira a pessoa desta empresa). A identidade continua viva se tiver vínculo em outra conta; se ficar sem vínculos, permanece (apenas não loga em lugar nenhum até ganhar novo vínculo).

### `POST /admin/users/{membership_id}/reset-password`
Opera na **identidade**: nova senha + `must_change_password=true` + e-mail.
⚠️ Como a senha é global, redefine o acesso da pessoa em **todas** as empresas dela — a UI deve avisar isso explicitamente.

### Blindagem do owner (atravessa criar/editar/remover)
- Membership com `is_owner=true` **não pode** ser editado, desativado, rebaixado nem removido por ninguém do tenant (nem por outro admin) → 403.
- Só o staff de plataforma mexe no owner (fora de escopo desta entrega → por ora via seed/SQL controlado).
- Guard "último admin": não remove/desativa o último admin **ativo** da conta.

### Hierarquia resultante por empresa
- **1 owner** (criado pela plataforma) — permissão geral, blindado.
- **N admins** comuns — permissão geral, editáveis/removíveis entre si.
- **N operators** — permissões via profile.

---

## 5. Enforcement / RBAC

- `account_id` resolvido **sempre** do token (membership escolhido); fim do fallback single-tenant como fonte de verdade.
- `require_admin` retorna `AdminAuth` com `identity_id`, `account_id`, `membership_id`, `role`.
- `require_permission(key)` resolve via `role` do membership (+ `profile_permissions` quando operator). Admin = todas as 47 permissões do catálogo (inalterado). Owner = admin + blindagem.
- Garantia: token da conta A nunca lê/escreve dados da conta B.
- `audit_events`: o ator passa a referenciar `identity_id` (+ `account_id` já presente no contexto).

---

## 6. Migração + backfill de produção (CRÍTICO)

**Estratégia: expand/contract — nunca destruir antes de validar.**

### Realidade de produção (inspeção read-only em 2026-05-30)
- 1 conta: **G2 Educação** (`47418057-77cc-469e-8263-d7311fe64155`).
- 3 usuários, todos nessa conta, e-mails distintos, **zero duplicata cross-account**, todos `is_active=true`, `must_change_password=false`:
  - `suporte@ianexo.com.br` — admin (mais antigo) → **owner** 🛡️ (decidido)
  - `guilherme.zanzoti@gmail.com` — operator
  - `fabiowebmain@gmail.com` (Fabio Dias) — operator
- `accounts` sem campos de cadastro; `identities`/`memberships` não existem; `alembic_version` = `c3d4e5f6a7b8`.

### Passo 1 — Migração "expand" (este PR), idempotente, numa transação
1. Cria `identities`, `memberships` e os campos de cadastro nullable em `accounts`.
2. Backfill (data migration no Alembic):
   - Cada e-mail distinto em `users` → 1 `identity` copiando `password_hash`, `name`, `avatar`, `must_change_password`, `is_active`, `last_login_at`, `created_at`. **Senha e estado preservados bit a bit** (não força troca, não invalida sessão).
   - Cada linha de `users` → 1 `membership(identity, account_id, role, profile_id, is_active, created_at)`.
   - **Owner:** em cada conta, o admin mais antigo recebe `is_owner=true` → em prod, `suporte@ianexo.com.br`.
   - Cadastro fake da empresa onde vazio: `legal_name='(pendente)'`, demais nullable.
3. **NÃO dropa `users` nem `admin_users`** — ficam como rede de segurança.

### Passo 2 — Verificação dentro da migração (aborta + rollback se falhar)
```
assert count(identities)  == count(distinct lower(email) em users)
assert count(memberships) == count(users)
assert toda linha de users tem membership correspondente
assert toda conta com >=1 user tem EXATAMENTE 1 is_owner
assert nenhuma identity com password_hash nulo
```
E-mails duplicados entre contas → falha cedo (não há escrita destrutiva neste passo).

### Passo 3 — Contract (PR SEPARADO, só após produção validada)
Drop de `users` (e limpeza de `admin_users`). Fora deste PR de propósito.

### Garantias sobre o tenant de produção (cláusulas firmes)
- A conta mantém o **mesmo `account_id` (UUID)** → `conversations`, `messages`, `leads`, `hubla_events`, `products`, `followup_*`, `knowledge_*` etc. **intocados**.
- **Senha do usuário atual preservada** → loga com a mesma senha após a migração.
- Usuário atual mantém acesso (owner/membership).
- **Nada apagado**: `users` continua existindo até o PR de contract.

### Reversibilidade
- `downgrade` dropa `memberships`/`identities` e os campos novos de `accounts`. Como `users` continua intacta, rollback = downgrade + redeploy da imagem anterior restaura o estado exato.

---

## 7. Estratégia de rollout (faseada)

1. **DEV primeiro:** implementar, rodar a migração no banco de desenvolvimento, validar as 5 asserts + testes manuais de login (1-vínculo, multi-vínculo, troca de senha, vínculo silencioso, owner protegido).
2. **Só com tudo OK em dev → PRODUÇÃO:** backup do banco imediatamente antes; deploy (CI roda `alembic upgrade heads`); health check; testes de fumaça (login do `suporte`, dos dois operators). Se algo falhar → downgrade + imagem anterior.

---

## 8. Seed (destravar testes / ambiente novo)

Script idempotente (`ON CONFLICT DO NOTHING`) que cria: 1 `account` com dados fake + 1 `identity` owner com credenciais conhecidas + `membership(is_owner=true)`. Roda em dev/CI sem depender de produção.

---

## 9. Frontend

- **Login** trata 3 desfechos: entra direto (1 vínculo) · força troca de senha (`must_change`) · **modal de escolha de conta** (N vínculos: nome da empresa + papel).
- **Seletor de empresa na TopBar** — visível só com >1 vínculo; trocar = novo token + reload do contexto da conta.
- **Página de usuários** → gestão de **memberships** da conta atual (criar por e-mail com vínculo silencioso, editar role/profile, ativar/desativar, remover; owner exibido bloqueado 🛡️).
- **Correção de tipo:** `account_id` no payload JWT do front passa de `number` → `string` (UUID).
- **Reset de senha** exibe aviso "redefine o acesso da pessoa em todo o sistema".
- Mantém o fluxo de change-password de primeiro login.

---

## 10. Superfície de refactor no código (para dimensionar o plano)

- `interface/http/routers/admin/auth.py` — login/select/switch-account.
- `interface/http/deps/admin_auth.py` + `deps/permissions.py` — `account_id` sempre do token; role/profile via membership; `AdminAuth` ganha `identity_id`/`membership_id`.
- `shared/adapters/db/repositories/user_repo.py` → `identity_repo.py` + `membership_repo.py`.
- `interface/http/routers/admin/users.py` — opera em membership (CRUD + vínculo silencioso + blindagem owner).
- Endpoints `/admin/me/*` (avatar/senha/perfil) → operam na identity.
- `audit_events` — ator vira `identity_id`.
- Migração Alembic (expand) + script de seed.
- Frontend: `lib/auth.ts`, `features/auth/*` (jwt type, AuthContext, login, chooser, switcher), página de usuários, TopBar.

---

## 11. Critérios de aceite

- **Backfill:** 3 identities + 3 memberships; `suporte@ianexo.com.br` com `is_owner=true`; senhas preservadas (login com senha atual funciona); G2 Educação intacta com todos os dados ligados; as 5 asserts passam; `downgrade` restaura.
- **Login:** 1-vínculo entra direto; multi-vínculo mostra modal; senha errada / identidade inativa → erro correto; `must_change_password` força troca antes de prosseguir.
- **Troca de conta:** switch re-emite token sem pedir senha; dados recarregam para a conta escolhida.
- **Vínculo silencioso:** e-mail existente → só membership, sem nova senha; e-mail novo → senha + e-mail; vínculo duplicado → 409.
- **Owner:** editar/remover/rebaixar/desativar owner por qualquer admin do tenant → 403; guard de último admin mantido.
- **Enforcement:** token da conta A nunca acessa dados da conta B; `require_permission` resolve via membership.
- **Rollout:** validado em dev antes de produção; produção com backup prévio e rollback testado.
