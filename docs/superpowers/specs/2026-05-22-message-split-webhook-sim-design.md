# Design: Message Splitting + Webhook Simulator

**Data:** 2026-05-22
**Branch:** feat/favicon-logo-session
**Status:** Aprovado

---

## 1. Contexto

O sistema envia mensagens de texto via ChatNexo (fork do Chatwoot). Atualmente `send_message()` envia o texto inteiro em uma única chamada, o que parece robótico para o usuário final no WhatsApp. Além disso, não existe um script local para simular webhooks Hubla (`subscription.activated`) sem depender do ambiente de produção da Hubla.

---

## 2. Escopo

### 2.1 Message Splitting em `ChatNexoClient.send_message()`
Modificar o método existente para quebrar mensagens longas em partes menores, enviadas sequencialmente com delay dinâmico entre elas — simulando comportamento humano de digitação no WhatsApp.

`send_template()` **não** é afetado — templates Meta têm formato fixo e não devem ser fragmentados.

### 2.2 Webhook Simulator (`scripts/webhook-sim/`)
Pasta com scripts Python e payloads JSON para disparar webhooks Hubla localmente, sem depender da plataforma Hubla. Inclui cálculo correto de assinatura HMAC para que o endpoint `/webhook/purchase` aceite os payloads.

---

## 3. Design Detalhado

### 3.1 Lógica de Split de Mensagem

**Arquivo novo:** `apps/api/src/shared/adapters/chatnexo/message_splitter.py`

Função pura `split_message(text: str) -> list[str]`:

1. Quebra o texto em parágrafos usando `\n\n` como delimitador
2. Qualquer parágrafo com mais de **400 chars** é subdividido por sentença (delimitadores: `.`, `?`, `!`), agrupando sentenças até 400 chars por parte
3. Partes com menos de **80 chars após strip** são descartadas (evita enviar whitespace ou fragmentos triviais)
4. Se o resultado for apenas 1 parte, retorna `[text]` sem modificação

**Thresholds configuráveis via `.env.local`:**
```
CHATNEXO_SPLIT_MAX_CHARS=400    # tamanho máximo de um parágrafo antes de subdividir
CHATNEXO_SPLIT_MIN_CHARS=80     # partes menores que isso são descartadas
```

### 3.2 Delay Dinâmico

**Em `ChatNexoClient.send_message()`:**

Entre cada parte enviada, o sistema aguarda um delay calculado sobre o tamanho da parte **anterior**:

```
delay = len(parte_anterior) * CHATNEXO_DELAY_MS_PER_CHAR
delay = max(CHATNEXO_MIN_DELAY_MS, min(delay, CHATNEXO_MAX_DELAY_MS))
```

**Variáveis em `.env.local` + `.env.example`:**
```
CHATNEXO_DELAY_MS_PER_CHAR=30   # ms por caractere (default: 30ms)
CHATNEXO_MIN_DELAY_MS=800       # mínimo entre partes (default: 800ms)
CHATNEXO_MAX_DELAY_MS=4000      # máximo entre partes (default: 4000ms)
```

Exemplo: parágrafo de 120 chars → delay = 120 × 30 = 3600ms (dentro do range 800–4000).

### 3.3 Modificação em `send_message()`

```
apps/api/src/shared/adapters/chatnexo/client.py
```

O método `send_message()` passa a:
1. Chamar `split_message(text)` para obter as partes
2. Se `len(partes) == 1`: envia direto, sem delay (comportamento atual)
3. Se `len(partes) > 1`: para cada parte, envia via `_post()`, depois aguarda delay dinâmico (exceto após a última parte)

O delay usa `asyncio.sleep(delay_ms / 1000)` — não bloqueia o event loop.

### 3.4 Estrutura do Webhook Simulator

```
scripts/
  webhook-sim/
    README.md
    fire_webhook.py
    payloads/
      hubla_subscription_activated.json
      hubla_subscription_activated_multi.json
```

#### `fire_webhook.py`

- Lê `.env.local` da raiz do repositório via `python-dotenv`
- Usa `HUBLA_WEBHOOK_SECRET` para calcular assinatura HMAC-SHA256 do payload
- Substitui `{{PHONE}}` no payload por `TEST_CONTACT_PHONE` do `.env.local` (ou `--phone` via argumento)
- Substitui `{{HUBLA_PRODUCT_ID}}` por `TEST_HUBLA_PRODUCT_ID` do `.env.local` (ou `--product-id`)
- Envia `POST {API_URL}/webhook/purchase` com header `x-hubla-token: {assinatura}`
- Imprime status HTTP e body da resposta

**Argumentos CLI:**
```bash
uv run python scripts/webhook-sim/fire_webhook.py [--payload NOME] [--phone NUMERO] [--product-id ID] [--url URL]
```

Defaults: `--payload hubla_subscription_activated`, `--url http://localhost:8000`

#### Payloads JSON

`hubla_subscription_activated.json` — compra simples (1 produto):
```json
{
  "type": "subscription.activated",
  "version": "2.0.0",
  "event": {
    "product": { "id": "{{HUBLA_PRODUCT_ID}}", "name": "Produto Teste" },
    "products": [
      { "id": "{{HUBLA_PRODUCT_ID}}", "name": "Produto Teste", "offers": [] }
    ],
    "subscription": {
      "id": "test-subscription-{{TIMESTAMP}}",
      "payer": {
        "firstName": "Teste",
        "lastName": "NexoIA",
        "document": "00000000000",
        "email": "teste@nexoia.com.br",
        "phone": "{{PHONE}}"
      },
      "activatedAt": "{{TIMESTAMP_ISO}}",
      "paymentMethod": "credit_card",
      "type": "one_time",
      "status": "active"
    },
    "user": {
      "id": "test-user-id",
      "email": "teste@nexoia.com.br",
      "phone": "{{PHONE}}"
    }
  }
}
```

`hubla_subscription_activated_multi.json` — mesmo formato, mas com `products[]` contendo 2 itens para testar múltiplos produtos.

#### Variáveis em `.env.local`

```
TEST_CONTACT_PHONE=+5511999999999
TEST_HUBLA_PRODUCT_ID=QaIlGtff9tlU94JjDKSq
```

---

## 4. Arquivos Modificados / Criados

| Arquivo | Tipo | Descrição |
|---|---|---|
| `apps/api/src/shared/adapters/chatnexo/message_splitter.py` | NOVO | Função pura `split_message()` |
| `apps/api/src/shared/adapters/chatnexo/client.py` | MODIFICADO | `send_message()` usa split + delay |
| `apps/api/src/shared/config/settings.py` | MODIFICADO | 5 novas variáveis de split/delay |
| `.env.example` | MODIFICADO | Documenta as novas variáveis |
| `apps/api/tests/unit/adapters/chatnexo/test_message_splitter.py` | NOVO | Testes unitários do splitter |
| `apps/api/tests/unit/adapters/chatnexo/test_client_split.py` | NOVO | Testes do send_message com mock HTTP |
| `scripts/webhook-sim/fire_webhook.py` | NOVO | Script de disparo |
| `scripts/webhook-sim/payloads/hubla_subscription_activated.json` | NOVO | Payload simples |
| `scripts/webhook-sim/payloads/hubla_subscription_activated_multi.json` | NOVO | Payload multi-produto |
| `scripts/webhook-sim/README.md` | NOVO | Instruções de uso |
| `apps/api/tests/unit/scripts/test_fire_webhook.py` | NOVO | Testes de HMAC e montagem de headers |

---

## 5. Testes

| Arquivo de Teste | Cenários |
|---|---|
| `test_message_splitter.py` | Mensagem simples (1 parte), múltiplos parágrafos, parágrafo longo >400 chars (subdivisão por sentença), parte <80 chars descartada, só whitespace |
| `test_client_split.py` | 1 parte → 1 chamada HTTP sem sleep; N partes → N chamadas HTTP; delay calculado corretamente (mock `asyncio.sleep`); `send_template()` não afetado |
| `test_fire_webhook.py` | Cálculo HMAC correto, substituição de placeholders `{{PHONE}}` e `{{HUBLA_PRODUCT_ID}}`, headers corretos |

Todos rodam dentro de `pytest tests/unit` — sem alteração no CI.

---

## 6. Fora de Escopo

- Split em `send_template()` — templates Meta têm formato fixo
- UI para configurar os parâmetros de split
- Simulador para outros eventos Hubla (`subscription.canceled`, `refunded`) — estrutura preparada para adicionar mais payloads depois

---

## 7. Decisões de Design

| Decisão | Motivo |
|---|---|
| Split em `send_message()`, não em skill separada | Skills são para decisões do LLM; o split é infraestrutura transparente aos callers |
| `message_splitter.py` separado do `client.py` | Função pura sem deps externas — testável isoladamente sem mock HTTP |
| Placeholders `{{PHONE}}` em vez de hardcode | Número do contato nunca entra no git |
| Delay dinâmico baseado no tamanho da parte anterior | Simula tempo real de digitação humana |
| `asyncio.sleep` (não `time.sleep`) | Não bloqueia o event loop — worker processa outros jobs em paralelo |
