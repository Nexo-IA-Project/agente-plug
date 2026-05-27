# Webhook Simulator

Dispara webhooks Hubla para o endpoint local sem depender da plataforma Hubla.

## Pré-requisitos

- API rodando em `http://localhost:8000` (ou defina `API_URL` no `.env.local`)
- Worker rodando (para processar o job de compra)
- ChatNexo acessível em `CHATNEXO_BASE_URL` com `CHATNEXO_INBOX_ID` configurado

## Configuração

Adicione ao `.env.local` na raiz do repositório:

```
# Caixa de entrada do ChatNexo onde as conversas serão criadas
CHATNEXO_INBOX_ID=113

# Número de teste (formato E.164 com código do país)
TEST_CONTACT_PHONE=+55119984479440

# hubla_id de um Course cadastrado no painel (/admin/courses)
TEST_HUBLA_PRODUCT_ID=<id_do_produto_na_hubla>
```

`TEST_HUBLA_PRODUCT_ID` deve corresponder ao campo `hubla_id` de um `Course` ativo no painel.
`CHATNEXO_INBOX_ID=113` é a caixa de entrada padrão (account_id=1).

## Uso

```bash
# Disparo simples (usa TEST_CONTACT_PHONE e TEST_HUBLA_PRODUCT_ID do .env.local)
uv run python scripts/webhook-sim/fire_webhook.py

# Sobrescrever telefone
uv run python scripts/webhook-sim/fire_webhook.py --phone +55119984479440

# Sobrescrever produto
uv run python scripts/webhook-sim/fire_webhook.py --product-id QaIlGtff9tlU94JjDKSq

# Payload multi-produto
uv run python scripts/webhook-sim/fire_webhook.py --payload hubla_subscription_activated_multi

# Apontar para outra instância
uv run python scripts/webhook-sim/fire_webhook.py --url http://staging.example.com
```

## Payloads disponíveis

| Arquivo | Descrição |
|---|---|
| `hubla_subscription_activated.json` | Compra simples — 1 produto |
| `hubla_subscription_activated_multi.json` | Compra com 2 produtos no array `products[]` |

## O que acontece ao disparar

1. Script lê `HUBLA_WEBHOOK_SECRET` do `.env.local`
2. Envia `POST /webhook/purchase?token={secret}` (token via query string — Hubla não envia headers)
3. API enfileira job `purchase` no worker
4. Worker processa: cria/atualiza contato, abre conversa no ChatNexo (inbox 113), enrolla em flows do curso
5. Mensagem de boas-vindas é enviada para o `TEST_CONTACT_PHONE` via WhatsApp
