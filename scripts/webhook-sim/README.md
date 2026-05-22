# Webhook Simulator

Dispara webhooks Hubla para o endpoint local sem depender da plataforma Hubla.

## Pré-requisitos

- API rodando em `http://localhost:8000` (ou defina `API_URL` no `.env.local`)
- Worker rodando (para processar o job de compra)

## Configuração

Adicione ao `.env.local` na raiz do repositório:

```
TEST_CONTACT_PHONE=+5511999999999
TEST_HUBLA_PRODUCT_ID=QaIlGtff9tlU94JjDKSq
```

`TEST_HUBLA_PRODUCT_ID` deve corresponder ao `hubla_id` de um `Course` cadastrado no painel.

## Uso

```bash
# Disparo simples (usa TEST_CONTACT_PHONE e TEST_HUBLA_PRODUCT_ID do .env.local)
uv run python scripts/webhook-sim/fire_webhook.py

# Sobrescrever telefone
uv run python scripts/webhook-sim/fire_webhook.py --phone +5511988887777

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
2. Envia `POST /webhook/purchase` com `x-hubla-token: {secret}`
3. API enfileira job `purchase` no worker
4. Worker processa: cria/atualiza contato, abre conversa no ChatNexo, enrolla em flows do curso
5. Mensagem de boas-vindas é enviada para o `TEST_CONTACT_PHONE` via WhatsApp
