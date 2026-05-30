# Config de Plataforma (núcleo) vs Tenant — separar OpenAI/SMTP

**Data:** 2026-05-30
**Status:** Aprovado (design) — implementar em PR próprio **depois** da base multi-tenant (#71) e **antes** da fase de UI de perfis + enforcement.

## Context

A tela de Settings hoje mistura config de **dois donos**: a da **plataforma** (de nós, o dono) e a do **tenant** (cada cliente). Decisão de classificação (2026-05-30):

- **PLATAFORMA (global, dono = super-admin):** **OpenAI (API key)** e **SMTP** (servidor `no-reply@ianexo` p/ notificações/senhas do sistema). Não pode ser editável por tenant (vaza credencial/custo da plataforma e não escala p/ N tenants).
- **TENANT (por `account_id`):** ChatNexo, Meta (API key/WABA), Hubla, Cademi, `alert_whatsapp_target`, comportamento da IA — cada cliente traz o seu. **Permanecem** em `accounts.settings`.

**Resultado pretendido:** OpenAI/SMTP saem do escopo por-tenant e viram **config global de plataforma**, sem perder os valores já configurados em produção e sem quebrar o runtime. A UI de Settings do tenant deixa de mostrá-las (a próxima fase já nasce limpa).

## Não-objetivos
- Painel super-admin da plataforma (fase futura) — aqui só deixamos a estrutura + uma seção de edição mínima.
- Enforcement por permissão (fase futura).
- Mexer nas configs de tenant (ChatNexo/Meta/Hubla/Cademi/comportamento) — ficam como estão.

## Modelo de dados
**Nova tabela `platform_config`** (linha única global — sem `account_id`):
- `id` (PK), `singleton` bool unique (garante 1 linha) **ou** apenas convenção "primeira linha".
- `openai_api_key` (texto, Fernet-encriptado — mesmo padrão das credenciais).
- SMTP: `smtp_host`, `smtp_port`, `smtp_security` (starttls/smtps/none), `smtp_username`, `smtp_password` (Fernet), `from_name`, `from_email`.
- `updated_at`.

## Migração (data-safe, com backfill de produção)
1. `create table platform_config`.
2. **Backfill** (Python, idempotente):
   - SMTP: `SELECT * FROM smtp_config` (linha da conta #1) → insere em `platform_config` copiando o `smtp_password` **cifrado como está** (mesma `INTEGRATION_CREDENTIALS_KEY`).
   - OpenAI: lê `openai_api_key` de `accounts.settings` (IntegrationConfig da 1ª conta); se ausente, deixa nulo (fallback `.env` em runtime). Copia o valor como está.
3. Remove `openai_api_key` de `accounts.settings` (JSONB) das contas.
4. Aposenta `smtp_config` por-tenant (mantém a tabela por ora ou dropa — decidir na implementação; preferir manter 1 release como deprecated p/ rollback).
`downgrade()` reverte: recria valores em `accounts.settings`/`smtp_config` a partir de `platform_config`.

## Código
- Novo `PlatformConfigRepository` (lê/grava a linha única; decripta Fernet).
- OpenAI: o cliente LLM e o RAG passam a ler a chave do `platform_config` (fallback `.env` `OPENAI_API_KEY`), **não** do `IntegrationConfig` por-tenant.
- SMTP: o serviço de e-mail (envio de senha/notificação) passa a ler do `platform_config`, não do `smtp_config` por-account.
- `IntegrationConfig` (entity) perde `openai_api_key`; os call-sites do OpenAI migram p/ `PlatformConfigRepository`.

## UI
- **Remove** os blocos OpenAI e SMTP da tela de Settings do tenant.
- Cria seção/área **"Plataforma / Núcleo"** que edita `platform_config` (campo OpenAI + bloco SMTP com botão Testar). Por ora acessível ao admin atual (single-tenant, você é o dono); na fase futura, **gated ao super-admin** e movida pro painel separado.

## Testes
- Unit: `PlatformConfigRepository` (round-trip, decripta Fernet); LLM/SMTP lendo do global.
- Integration (testcontainers + alembic): migração cria `platform_config` e **backfilla** a partir de `smtp_config` + `accounts.settings`; OpenAI some de `accounts.settings`; SMTP global funciona; reversível.
- Smoke: envio de e-mail de teste continua funcionando lendo do global.

## Verificação manual (pós-deploy)
- `SELECT * FROM platform_config` tem a chave OpenAI + SMTP de produção (vindos do backfill).
- Envio de e-mail de teste OK. Agent (OpenAI) responde. Settings do tenant não mostra mais OpenAI/SMTP.
