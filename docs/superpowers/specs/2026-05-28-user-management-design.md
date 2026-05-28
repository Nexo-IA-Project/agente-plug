# Spec: Sistema de Gestão de Usuários com Permissões

**Data:** 2026-05-28  
**Status:** Aprovado  
**Branch alvo:** `feat/user-management`

---

## Visão Geral

Implementação de um sistema completo de gestão de usuários para o painel admin do NexoIA, com dois níveis de permissão (`admin` e `operator`), página de perfil com foto e crop, criação de usuários por admin com senha automática via email, reset de senha por admin, troca obrigatória de senha no primeiro login e configuração de SMTP no banco de dados.

A tabela `admin_users` é substituída pela tabela `users`. Os dados existentes são migrados automaticamente.

---

## Banco de Dados

### Tabela `users` — substitui `admin_users`

| Coluna | Tipo | Notas |
|--------|------|-------|
| `id` | UUID PK | `gen_random_uuid()` |
| `account_id` | INTEGER FK (accounts) | NOT NULL |
| `name` | VARCHAR(100) | NOT NULL |
| `email` | VARCHAR(200) | NOT NULL, UNIQUE por account |
| `password_hash` | VARCHAR(200) | NOT NULL, bcrypt |
| `role` | VARCHAR(20) | NOT NULL — `'admin'` ou `'operator'` |
| `avatar` | BYTEA | NULLABLE — JPEG 200×200 pós-crop |
| `must_change_password` | BOOLEAN | DEFAULT TRUE |
| `is_active` | BOOLEAN | DEFAULT TRUE |
| `created_at` | TIMESTAMPTZ | server_default NOW() |
| `last_login_at` | TIMESTAMPTZ | NULLABLE, atualizado no login |

**Constraint:** `UNIQUE (account_id, email)`

**Migration:** Copia `email`, `password_hash` e `created_at` de `admin_users` para `users`. Registros migrados recebem `role = 'admin'` fixo (o valor existente `"viewer"` é descartado — todos os usuários do painel eram admins), `must_change_password = FALSE` e `name` derivado da parte local do email (antes do `@`). A tabela `admin_users` é dropada após a cópia bem-sucedida dentro da mesma transaction Alembic.

### Tabela `smtp_config` — nova

| Coluna | Tipo | Notas |
|--------|------|-------|
| `id` | UUID PK | |
| `account_id` | INTEGER FK UNIQUE | 1 config por conta |
| `host` | VARCHAR(200) | NOT NULL — ex: `smtp.gmail.com` |
| `port` | INTEGER | NOT NULL — ex: `587` |
| `username` | VARCHAR(200) | NOT NULL |
| `encrypted_password` | TEXT | NOT NULL — Fernet encrypted |
| `use_tls` | BOOLEAN | DEFAULT TRUE |
| `from_name` | VARCHAR(100) | NOT NULL — ex: `"NexoIA"` |
| `from_email` | VARCHAR(200) | NOT NULL — endereço remetente |
| `updated_at` | TIMESTAMPTZ | atualizado em cada PUT |

**Criptografia:** senha cifrada com Fernet usando a chave `INTEGRATION_CREDENTIALS_KEY` já presente no ambiente — mesmo padrão de `integration_configs`.

---

## Backend

### Estrutura de arquivos novos

```
src/
  interface/http/routers/admin/
    users.py          # CRUD de usuários (admin) + reset-password
    me.py             # Perfil próprio: GET/PUT /me, avatar, senha
    smtp_config.py    # GET/PUT /smtp-config, POST /smtp-config/test
  shared/
    adapters/
      db/repositories/
        user_repo.py
        smtp_config_repo.py
      email/
        smtp_email_service.py   # SmtpEmailService — lê config do banco
    application/use_cases/admin/
      create_user.py            # gera senha + envia email
      reset_user_password.py    # nova senha + envia email
    domain/entities/
      user.py
      smtp_config.py
```

### Endpoints

**Usuários — `require_admin_role` (só admin)**

```
GET    /admin/users                    → UserListResponse (paginado)
POST   /admin/users                    → UserResponse (201) — gera senha, envia email
PUT    /admin/users/{id}               → UserResponse — edita name/role/is_active
DELETE /admin/users/{id}               → 204 — não pode deletar o próprio usuário nem o último admin
POST   /admin/users/{id}/reset-password → 204 — gera nova senha, envia email
```

**Perfil — `require_admin` (qualquer autenticado)**

```
GET    /admin/me                → MeResponse (id, name, email, role, avatar_url, must_change_password)
PUT    /admin/me                → MeResponse — só `name` editável (email imutável)
PUT    /admin/me/avatar         → 204 — body: { "data": "<base64 JPEG>" }
GET    /admin/me/avatar         → image/jpeg — serve bytea direto
PUT    /admin/me/password       → 204 — body: { "current_password", "new_password" }
```

**SMTP — `require_admin_role` (só admin)**

```
GET    /admin/smtp-config        → SmtpConfigResponse (sem encrypted_password)
PUT    /admin/smtp-config        → SmtpConfigResponse — upsert
POST   /admin/smtp-config/test   → 200 {"ok": true} | 422 {"detail": "<erro SMTP>"}
```

### Dependências de permissão

Em `src/interface/http/deps/admin_auth.py`:

- `require_admin` — existente: valida JWT, retorna usuário autenticado
- `require_admin_role` — novo: chama `require_admin`, verifica `user.role == 'admin'`, levanta `HTTP 403` caso contrário

### Fluxo: criar usuário

1. Admin envia `POST /admin/users` com `name`, `email`, `role`
2. Backend gera senha aleatória segura (16 chars: letras + números + símbolos)
3. Senha é hasheada com bcrypt e salva em `users`; `must_change_password = TRUE`
4. `SmtpEmailService` carrega config do banco e envia email com assunto "Seu acesso ao NexoIA" contendo nome, email e senha temporária
5. Retorna `UserResponse` (sem senha)

### Fluxo: primeiro login + troca obrigatória

1. Usuário faz login → JWT gerado com `must_change_password: true` no payload
2. Frontend detecta flag e redireciona para `/change-password`
3. `/change-password` bloqueia navegação para qualquer outra página enquanto flag ativa
4. Usuário define nova senha → `PUT /admin/me/password` → `must_change_password = FALSE`
5. Acesso liberado normalmente

### Fluxo: reset de senha (admin)

1. Admin clica "Resetar senha" na lista de usuários
2. `POST /admin/users/{id}/reset-password` — gera nova senha, atualiza hash, seta `must_change_password = TRUE`
3. Email enviado ao usuário com nova senha temporária
4. Próximo login força troca novamente

### SmtpEmailService

`src/shared/adapters/email/smtp_email_service.py`

- Carrega `smtp_config` do banco via `SmtpConfigRepository`
- Descriptografa senha com Fernet
- Usa `aiosmtplib` para envio assíncrono
- Método `send_email(to, subject, body_html)` — usado por `create_user` e `reset_user_password`
- Se `smtp_config` não configurado → levanta `SmtpNotConfiguredError` (500 com mensagem clara)

### Templates de email

Dois templates HTML inline (sem dependência de template engine):

1. **Boas-vindas / acesso criado** — nome, email, senha temporária, aviso de troca obrigatória
2. **Senha resetada** — nome, nova senha temporária, aviso de troca obrigatória

---

## Frontend

### Novas páginas

| Rota | Componente | Acesso |
|------|-----------|--------|
| `/users` | `UsersPage` | Admin only |
| `/profile` | `ProfilePage` | Todos |
| `/change-password` | `ChangePasswordPage` | Todos (bloqueio por flag) |

### Modificações em páginas existentes

- `/settings` — nova seção "Email (SMTP)" visível apenas para admin; seção de credenciais de integração oculta para operator
- `Sidebar` — item "Usuários" visível apenas para admin; rodapé mostra avatar + nome do usuário logado
- `/templates` — botão "Excluir template" oculto para operator

### Endpoints existentes que ganham `require_admin_role`

Os endpoints abaixo atualmente usam `require_admin` (qualquer autenticado). Passam a exigir `role='admin'`:

- `PUT /admin/settings` — editar credenciais de integração
- `DELETE /admin/meta-templates/{id}` — excluir template Meta
- `DELETE /admin/documents/{id}` — excluir documento KB
- `DELETE /admin/api-tokens/{id}` — revogar token de API

### Contexto de autenticação

`src/features/auth/context/AuthContext.tsx`:

```typescript
interface AuthUser {
  id: string
  name: string
  email: string
  role: 'admin' | 'operator'
  must_change_password: boolean
}
```

Hook `usePermission()`:
```typescript
const { isAdmin, can } = usePermission()
// Ações: 'manage_users', 'delete_template', 'edit_credentials', 'edit_smtp'
```

JWT payload é expandido para incluir `role` e `must_change_password`.

### Bloqueio de troca de senha

Em `src/shared/components/layout/AdminLayout.tsx`: se `user.must_change_password === true`, redireciona para `/change-password` e bloqueia qualquer outra rota do layout admin.

### Página `/users`

- Tabela com: avatar, nome, email, role (pill colorido), status (ativo/inativo), data de criação
- Ações por linha: "Resetar senha" + "Editar" (drawer) + "Desativar/Ativar"
- Botão "Novo usuário" abre drawer com formulário (name, email, role)
- Drawer de edição: name, role, is_active — email é somente leitura
- Confirmação antes de "Resetar senha"

### Página `/profile`

- Avatar circular clicável → abre modal de crop
- Modal de crop: `react-image-crop`, aspect ratio 1:1, área mínima 100×100, botão "Salvar foto"
- Campos editáveis: `name`
- Campo email: somente leitura para todos
- Seção "Alterar senha": campos `senha atual`, `nova senha`, `confirmar nova senha`

### Matriz de permissões (frontend)

| Elemento | Admin | Operador |
|----------|-------|----------|
| Item "Usuários" na sidebar | ✓ | oculto |
| Seção SMTP em /settings | ✓ | oculto |
| Seção credenciais em /settings | ✓ | oculto |
| Botão "Excluir" em /templates | ✓ | oculto |
| Editar próprio perfil (nome, foto) | ✓ | ✓ |
| Trocar própria senha | ✓ | ✓ |
| Alterar próprio email | ✗ | ✗ |

Elementos ocultos são removidos do DOM (não apenas `disabled`) para evitar inspeção via DevTools. A API aplica as mesmas restrições com `require_admin_role` (defesa em profundidade).

### Avatar

- Biblioteca: `react-image-crop`
- Crop aspect ratio: 1:1, output 200×200px JPEG quality 85
- Envio: `{ data: "<base64>" }` via `PUT /admin/me/avatar`
- Exibição: `GET /admin/me/avatar` — URL cacheada no cliente com query param `?v=<timestamp>` para invalidação após upload

---

## Configuração de SMTP (`/settings`)

Campos do formulário (visível só para admin):

- **Host SMTP** — ex: `smtp.gmail.com`
- **Porta** — ex: `587`
- **Usuário** — email de autenticação
- **Senha** — campo password, nunca exibida após salva
- **Usar TLS** — toggle (default: ativado)
- **Nome do remetente** — ex: `NexoIA`
- **Email do remetente** — ex: `noreply@empresa.com`
- Botão **"Testar configuração"** — chama `POST /admin/smtp-config/test`, mostra resultado inline

Ao abrir a página, `GET /admin/smtp-config` retorna config sem a senha (campo omitido). Campo de senha exibe placeholder `"••••••••"` se já configurada.

---

## Testes

### Unitários (pytest)

- `test_create_user_use_case.py` — geração de senha, hash, flag `must_change_password`
- `test_reset_password_use_case.py` — nova senha, flag setada, email enviado
- `test_require_admin_role.py` — 403 para role='operator', 200 para role='admin'
- `test_smtp_email_service.py` — mock do `aiosmtplib`, verifica campos do email enviado
- `test_users_router.py` — CRUD completo, reset-password, guard de role

### Integração

- `test_user_repo.py` — CRUD + constraint unique email por account
- `test_smtp_config_repo.py` — upsert, criptografia/descriptografia da senha

---

## Dependências novas

| Pacote | Onde | Motivo |
|--------|------|--------|
| `aiosmtplib` | `apps/api` | Envio SMTP assíncrono |
| `react-image-crop` | `apps/web` | Crop de avatar no cliente |

---

## Fora de escopo (neste momento)

- Recuperação de senha via tela de login ("esqueci minha senha")
- Login social (Google, GitHub)
- 2FA / MFA
- Logs de auditoria de ações por usuário
- Notificações em tempo real para admin quando novo usuário é criado
