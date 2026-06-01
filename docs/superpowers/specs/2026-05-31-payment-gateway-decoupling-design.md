# Desacoplamento de Gateways de Pagamento — Design

**Data:** 2026-05-31
**Status:** Aprovado (design) — aguardando plano de implementação
**Branch sugerida:** `feat/payment-gateway-decoupling`

## Problema

Hoje o sistema tem um único meio de pagamento, engessado na **Hubla**. Todo o
schema, os tipos de evento e a lógica de negócio são concreto-Hubla:

- Não existe `PaymentGatewayPort` genérico — só `HublaPort`.
- Os tipos de evento são um `Literal` Pydantic com 25 eventos Hubla hardcoded
  (`src/shared/domain/value_objects/hubla_event_type.py`).
- O produto está casado com Hubla pela própria chave natural:
  `products.hubla_id` + unique `(account_id, hubla_id)`.
- `onboarding_flows` dispara por `(product_id, trigger_event_type)`, com
  `trigger_event_type` guardando a string Hubla direto.
- `leads` e `hubla_events` são inteiramente construídos em torno de
  `hubla_subscription_id`, `hubla_product_id`, status e tipos Hubla.
- O catálogo visual de eventos (`apps/web/.../onboarding/lib/triggerEvents.ts`,
  474 linhas, 42 eventos, 6 categorias) vive todo no frontend, todo Hubla.

O parsing em si (`HublaEventParser` + `v1_normalizer`) é a parte mais limpa e
isolada.

## Objetivo

Desacoplar o gateway de pagamento, transformando-o numa abstração **plugável**:
cada gateway (Hubla, Hotmart, Kiwify, Eduzz, Asaas, …) é um módulo de código
auto-contido, com seu próprio parser, catálogo de eventos e estratégia de auth.
Cada produto pertence a um gateway; webhooks e onboarding sabem qual gateway
processar. Começamos com a Hubla como primeira implementação da abstração;
os demais entram depois, só com código novo.

### Requisito inegociável: zero-regressão

**Tudo que funciona hoje continua funcionando idêntico.** Esta mudança é tratada
como um *refactor* onde a Hubla vira a primeira implementação da abstração — não
uma reescrita. O fluxo single-tenant Hubla vivo (webhook → enrollment →
onboarding → leads → welcome → reembolso) deve se comportar exatamente como hoje.

## Decisões de design (keystones)

1. **Gateway = módulo de código + registro central**, mantido pela equipe de dev.
   Cada módulo declara seu catálogo de eventos; quando o provedor muda um evento,
   mexe-se só no módulo dele. O usuário "pluga", escolhe o evento que quer, e o
   sistema roda sozinho. Não há cadastro de evento linha-a-linha pelo cliente.
2. **Generalizar todo o schema agora** (base limpa, sem dívida de nomenclatura).
   Como só existe Hubla, a migration de dados é mecânica: `gateway='hubla'` em tudo.
3. **Camada semântica canônica.** Cada evento de gateway mapeia pra uma categoria
   canônica de negócio. A lógica embutida reage à categoria canônica; o gatilho de
   onboarding reage ao evento específico do gateway. Por dentro, cada adapter se
   "rebola" pra normalizar seu payload; por fora, tudo aparece igual ao usuário.
4. **Config via `Settings → Pagamentos`** (tela já existente), usando a tabela
   `integration_configs`. Cada gateway declara seus campos de config e sua
   estratégia de auth de webhook (Hubla não exige auth na entrada; outros podem).
5. **Backend é dono do catálogo de eventos** (código + categoria canônica +
   metadata visual: label, cor, ícone, descrição, verbo). Servido por endpoint; o
   frontend renderiza dinamicamente. Uma fonte de verdade por gateway, no backend.

---

## Bloco 1 — A abstração de gateway

Cada gateway vira um módulo auto-contido, descoberto por um **registro central**,
espelhando o padrão de `skills/` que o projeto já usa.

```
src/shared/adapters/payment_gateways/
  base.py        # protocolo PaymentGateway + dataclasses (GatewayEvent, NormalizedEvent)
  registry.py    # registro central: list_available(), get(slug)
  hubla/
    gateway.py   # identidade, config_fields, estratégia de auth do webhook
    catalog.py   # catálogo de eventos (absorve hubla_event_type.py + triggerEvents.ts)
    parser.py    # parse + normalize (absorve event_parser.py + v1_normalizer.py)
  hotmart/  …(depois)
  asaas/    …(depois)
```

Port no domínio (`src/shared/domain/ports/payment_gateway.py`) define o contrato
`PaymentGateway` que todo módulo implementa:

| Método/atributo | O que entrega |
|---|---|
| `slug`, `display_name`, `icon` | identidade + metadata pro card de Settings |
| `event_catalog()` | lista de `GatewayEvent` (código + categoria canônica + label/cor/ícone/descrição/verbo) |
| `config_fields()` | quais campos de credencial o gateway pede (dirige o form de config) |
| `verify_webhook(request)` | estratégia de auth de entrada — Hubla: token na query; Hotmart: header `hottok`; Asaas: token header |
| `parse(payload) → NormalizedEvent` | onde cada gateway se "rebola" pra extrair e normalizar o payload cru no modelo canônico |

O `HublaPort` atual (reembolso) vira uma **capability opcional** que o gateway
pode ou não implementar — reembolso continua funcionando, mas agora por-gateway.

## Bloco 2 — Modelo canônico de eventos

Enum no domínio `CanonicalEventCategory` define os conceitos de negócio
independentes de gateway: `purchase` (compra/acesso concedido),
`subscription_created`, `subscription_renewed`, `subscription_canceled`,
`subscription_expiring`, `abandoned_cart`, `refund`, `payment_failed`, etc.
Cada `GatewayEvent` do catálogo mapeia pra **exatamente uma** categoria canônica.

`parser.parse()` produz um `NormalizedEvent` que carrega **as duas coisas**:

- `gateway_event_code` — o evento cru e específico (ex: `subscription.activated`),
  pra exibição/log e pro gatilho de onboarding.
- `canonical_category` — o conceito de negócio (ex: `purchase`).

Quem reage a quê:

- **Lógica embutida** (welcome, liberação de acesso, reembolso) reage à
  **categoria canônica** → 100% agnóstica de gateway. Um `PURCHASE_APPROVED` da
  Hotmart e um `subscription.activated` da Hubla disparam o mesmo welcome.
- **Gatilho de onboarding flow** fica na granularidade fina do **evento específico
  do gateway** (o usuário escolhe "Venda ativada" no catálogo daquele gateway).
  Preserva a flexibilidade atual sem perder granularidade.

> A correspondência flexível atual (`ACTIVATION_EVENT_TYPES` = `subscription.activated`
> + `customer.member_added` → "acesso concedido") é preservada via categoria
> canônica: ambos mapeiam pra `purchase`, então a lógica embutida de acesso/welcome
> dispara igual independentemente de qual dos dois eventos chegou.

## Bloco 3 — Dados (migration de generalização)

Migration mecânica: `UPDATE ... SET gateway='hubla'` em todas as linhas existentes.

| Tabela | Hoje | Depois |
|---|---|---|
| `products` | `hubla_id`, unique `(account_id, hubla_id)` | + `gateway`; `hubla_id`→`gateway_product_id`; unique `(account_id, gateway, gateway_product_id)` |
| `product_hubla_aliases` | `hubla_id` | → `product_gateway_aliases` + `gateway`; unique `(account_id, gateway, gateway_product_id)` |
| `hubla_events` | nome Hubla, `hubla_subscription_id`, `hubla_product_id` | → `payment_events` + `gateway` + `canonical_category`; ids renomeados; índices renomeados |
| `leads` | `hubla_subscription_id`, `hubla_product_id` | + `gateway`; ids renomeados; unique `(account_id, gateway, gateway_subscription_id)`; opcional `last_canonical_category` |
| `onboarding_flows` | `trigger_event_type` (string Hubla) | **sem mudança de coluna** — gateway derivado do produto; a string passa a ser validada contra o catálogo do gateway do produto |

Campos como `utm_*`, `offer_id`, `fbp`, `payment_method`, `session_*` já são
conceitos genéricos — ficam, e cada gateway preenche o que tiver (null quando não
se aplica). `subscription_status` continua como string nativa do gateway (display).

Entidades de domínio renomeiam junto (`HublaEvent`→`PaymentEvent`; campos de
`Lead`/`Product`). O `hubla_event_type.py` (Literal de 25 eventos) é **absorvido
pelo catálogo do módulo Hubla**; os conjuntos semânticos (`PURCHASE_EVENT_TYPES`,
`ACTIVATION_EVENT_TYPES`) viram checagens de categoria canônica.

## Bloco 4 — Webhook + pipeline de ingestão

**Endpoint genérico** `/webhook/{gateway}`: resolve o gateway no registro pelo
slug → `gateway.verify_webhook(request)` (auth própria de cada um) → dedup →
persiste cru → enfileira job genérico `kind="gateway_event"` com `{gateway, payload}`.

**Âncoras de compatibilidade (zero-regressão):**

- `/webhook/hubla` e `/webhook/purchase` **continuam existindo com a mesma URL** —
  o cliente não reconfigura nada no painel da Hubla. Internamente delegam pro
  caminho genérico com `gateway="hubla"`.
- Os job kinds `hubla_event` e `purchase` seguem aceitos como alias de
  `gateway_event` com gateway=hubla.

**Worker:** `handle_hubla_event` → `handle_gateway_event(gateway, payload)`. O
`HublaEventHandler` atual (que já faz quase todo o pipeline: log de evento →
upsert lead → resolve produto → enrolla flows → comportamentos embutidos) vira
`GatewayEventHandler` genérico. A única troca: o parsing/lookup específico-Hubla
dá lugar a `registry.get(gateway).parse()` → `NormalizedEvent`; daí pra frente o
fluxo é o mesmo de hoje. Roteamento:

- produto resolvido por `(gateway, gateway_product_id)` + aliases
- flow disparado por `(product_id, gateway_event_code)` — granularidade fina preservada
- welcome / access / refund disparados por `canonical_category` — agnóstico

## Bloco 5 — Config / Settings

A tela `Settings → Pagamentos` já existe — agora dirigida pelo registro:

- `GET /admin/gateways` → lista os gateways disponíveis (vêm do código) + estado
  (habilitado/credenciado por conta). Os cards "em breve"
  (Hotmart/Kiwify/Eduzz/Asaas) acendem sozinhos conforme o módulo é liberado.
- A subpágina de cada gateway gera o form a partir de `gateway.config_fields()` e
  mostra a URL de webhook `/webhook/{slug}?token=…` quando o gateway usa token.
  **A página da Hubla mostra exatamente o que mostra hoje.**
- Credenciais por gateway ficam na `integration_configs` (Fernet, `enabled`, keyed
  por slug). A migration move o `hubla_webhook_secret` atual pra lá, e o
  `token_resolver` passa a ler de lá (mantendo o fallback `.env`). Valor migrado =
  comportamento idêntico.
- `GET /admin/gateways/{slug}/events` → serve o catálogo daquele gateway (consumido
  pelo seletor de eventos do onboarding).

## Bloco 6 — Frontend

- **Form de produto**: o input único `hubla_id` vira **dropdown de gateway**
  (gateways habilitados) + input `gateway_product_id` (label se adapta: "ID na
  Hubla"). Com só a Hubla habilitada, a UX fica idêntica à de hoje (default Hubla).
- **Seletor de eventos do onboarding (FlowDrawer)**: em vez do `triggerEvents.ts`
  estático, busca o catálogo do gateway do produto via
  `GET /admin/gateways/{slug}/events` e renderiza o **mesmo grid rico** (categorias,
  cores, ícones) dinamicamente. Todo o conteúdo atual do `triggerEvents.ts` migra
  pro catálogo do módulo Hubla no backend — nada visual se perde.
- **Leads**: referências `hubla_*`→`gateway_*`, ganha coluna/filtro de gateway.
  Visual praticamente intacto.

## Bloco 7 — Rollout + testes

Hubla = primeira implementação da abstração + migration mecânica. Garantias de
zero-regressão:

- URLs de webhook intactas; flows existentes mantêm seus `trigger_event_type`;
  produtos mantêm seus ids (viram `gateway_product_id`, gateway=hubla); secret
  migrado pro novo local de leitura.

**Testes:**

- **Unit**: registro; completude do catálogo Hubla (todo evento mapeia pra uma
  categoria canônica); parser (payloads-ouro → `NormalizedEvent`); mapeamento
  canônico.
- **Integração**: webhook → enrollment → onboarding ponta-a-ponta pelo caminho
  genérico com payload Hubla, **provando paridade** com o comportamento de hoje.
- **Migration**: linhas existentes recebem `gateway='hubla'`, constraints batem,
  zero perda de dado.

## Fora de escopo (YAGNI)

- Implementação dos módulos Hotmart/Kiwify/Eduzz/Asaas — entram depois, cada um
  como código novo plugando na abstração. Este design só entrega a abstração + Hubla.
- UI de gestão de gateways separada de Settings (cards já vivem em `Settings →
  Pagamentos`).
- Cadastro de eventos pelo cliente — catálogo é mantido pela equipe de dev.

## Arquivos-chave afetados

Backend:
- `src/shared/domain/ports/payment_gateway.py` (novo)
- `src/shared/domain/value_objects/canonical_event_category.py` (novo)
- `src/shared/adapters/payment_gateways/` (novo módulo + registro + Hubla)
- `src/shared/domain/value_objects/hubla_event_type.py` (absorvido no catálogo Hubla)
- `src/shared/adapters/hubla/{event_parser,v1_normalizer}.py` (migram pro módulo)
- `src/shared/application/hubla_event_handler.py` → `gateway_event_handler.py`
- `src/interface/http/routers/webhook_hubla.py` + `webhook_purchase.py` (compat) + rota genérica
- `src/interface/worker/handlers/hubla_event.py` → `gateway_event.py`
- `src/shared/domain/entities/{product,lead,hubla_event}.py` (renomeiam)
- `src/shared/adapters/db/repositories/{product_repo,lead_repo,...}.py`
- `src/interface/http/routers/admin/gateways.py` (novo)
- migrations em `migrations/versions/`

Frontend:
- `apps/web/src/features/products/` (form: gateway + gateway_product_id)
- `apps/web/src/features/onboarding/` (catálogo dinâmico via API; `triggerEvents.ts` migra pro backend)
- `apps/web/src/features/leads/` (gateway_* + coluna/filtro)
- `apps/web/src/app/(admin)/settings/pagamentos/` (dirigido pelo registro)
- `apps/web/src/lib/api.ts` (novas funções: listGateways, getGatewayEvents, …)
