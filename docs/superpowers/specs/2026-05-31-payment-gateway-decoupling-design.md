# Desacoplamento de Gateways de Pagamento — Design

**Data:** 2026-05-31
**Status:** Aprovado (design, rev. 2 pós-code-review) — aguardando plano de implementação
**Branch sugerida:** `feat/payment-gateway-decoupling`

> **Rev. 2** incorpora um code-review profundo (3 lentes: precisão factual/regressão,
> solidez arquitetural, lacunas) que corrigiu 3 erros materiais da rev. 1 (reembolso
> inbound inexistente; inversão da regra anti-duplicação; premissa errada sobre
> `integration_configs`) e adicionou subsistemas vivos que faltavam (Pendências, SSE
> de Leads, métricas, seeds, contrato de API).

## Problema

Hoje o sistema tem um único meio de pagamento, engessado na **Hubla**. Todo o
schema, os tipos de evento e parte da lógica são concreto-Hubla:

- Não existe `PaymentGatewayPort` genérico — só `HublaPort` (capability outbound de reembolso).
- Os tipos de evento são um `Literal` Pydantic com **25** eventos Hubla hardcoded
  (`src/shared/domain/value_objects/hubla_event_type.py:16-48`).
- O produto está casado com Hubla pela chave natural: `products.hubla_id` +
  unique `(account_id, hubla_id)` (`models.py:278,287`).
- `onboarding_flows` dispara por `(product_id, trigger_event_type)`, com
  `trigger_event_type` validado por `Literal[HublaEventType]` em
  `schemas/onboarding.py:11,57,68,75`.
- `leads` e `hubla_events` são construídos em torno de `hubla_subscription_id`,
  `hubla_product_id`, status e tipos Hubla (`models.py:769-871`).
- O catálogo visual de eventos (`apps/web/src/features/onboarding/lib/triggerEvents.ts`,
  25 eventos, 6 categorias de exibição) vive todo no frontend, todo Hubla, e é
  consumido também por Leads e por `formatRelativeDelay`.

O parsing em si (`HublaEventParser` + `v1_normalizer`) é a parte mais limpa e isolada.

## Objetivo

Desacoplar o gateway de pagamento, transformando-o numa abstração **plugável**:
cada gateway (Hubla, Hotmart, Kiwify, Eduzz, Asaas, …) é um módulo de código
auto-contido, com seu parser, catálogo de eventos e estratégia de auth. Cada
produto pertence a um gateway; webhooks e onboarding sabem qual gateway processar.
Começamos com a Hubla como primeira implementação; os demais entram depois, só com
código novo.

### Requisito inegociável: zero-regressão

**Tudo que funciona hoje continua funcionando idêntico.** Esta mudança é um
*refactor* onde a Hubla vira a primeira implementação da abstração — não uma
reescrita. O fluxo single-tenant Hubla vivo (webhook → enrollment → onboarding →
leads → welcome → Pendências) deve se comportar exatamente como hoje.

## Decisões de design (keystones)

1. **Gateway = módulo de código + registro central**, mantido pela equipe de dev.
   Cada módulo declara seu catálogo; quando o provedor muda um evento, mexe-se só
   no módulo dele. O cliente "pluga", escolhe o evento que quer, e o sistema roda.
   Não há cadastro de evento linha-a-linha pelo cliente.
2. **Generalizar todo o schema agora** (base limpa). Como só existe Hubla, a
   migration de dados é mecânica: `gateway='hubla'` em tudo.
3. **Modelo de eventos em DUAS camadas** (ver Bloco 2). Não se força todo evento
   numa categoria de comportamento — só os que têm lógica embutida.
4. **Config via `Settings → Pagamentos`** (tela já existente). O secret continua em
   `accounts.settings` JSONB (a tabela `integration_configs` é código morto e NÃO
   será usada); a estrutura JSONB é generalizada por slug de gateway.
5. **Backend é dono do catálogo de eventos**; servido por endpoint; o frontend
   renderiza dinamicamente. Uma fonte de verdade por gateway, no backend.
6. **Rename atômico back+front** dos campos `hubla_*`→`gateway_*` no mesmo PR (o web
   app é o único consumidor dos endpoints admin), sem aliases de compat.

---

## Bloco 1 — A abstração de gateway

Cada gateway vira um módulo auto-contido, descoberto por um **registro central**.

```
src/shared/adapters/payment_gateways/
  base.py        # protocolos + dataclasses (GatewayEvent, NormalizedEvent, WebhookRequest)
  registry.py    # registro central: list_available(), get(slug)
  hubla/
    gateway.py   # identidade, config_fields, verify_webhook, idempotency_key, capabilities
    catalog.py   # catálogo de eventos (absorve hubla_event_type.py + triggerEvents.ts)
    parser.py    # parse + normalize (absorve event_parser.py + v1_normalizer.py)
    refund.py    # implementação da RefundCapability (absorve HublaPort)
  hotmart/  …(depois)
  asaas/    …(depois)
```

### Ports no domínio (Clean Architecture — domínio sem dependência de framework)

`src/shared/domain/ports/payment_gateway.py`:

| Método/atributo | O que entrega |
|---|---|
| `slug`, `display_name`, `icon` | identidade + metadata pro card de Settings |
| `event_catalog()` | lista de `GatewayEvent` (ver Bloco 2) |
| `config_fields()` | quais campos de credencial o gateway pede (dirige o form de config) |
| `verify_webhook(req: WebhookRequest)` | auth de entrada — recebe um **value object** próprio, não o `Request` do FastAPI |
| `idempotency_key(req: WebhookRequest) → str \| None` | chave de dedup gateway-específica (Hubla: `{event_type}:{sale_id}`); `None` = sem dedup (degradação explícita) |
| `parse(payload) → NormalizedEvent` | extrai e normaliza o payload cru no modelo canônico |
| `refund_capability` | `RefundCapability \| None` — capability **outbound** opcional (ver abaixo) |

**`WebhookRequest`** (value object, montado na camada `interface`):
`headers: Mapping`, `query: Mapping`, `raw_body: bytes`. O `raw_body` é essencial
para gateways que validam **HMAC sobre o corpo cru** (Hotmart/Asaas), antes do parse JSON.

**Reembolso é capability OUTBOUND, não evento inbound.** Hoje o reembolso é
síncrono, iniciado pelo agente na conversa (`agent/skills/processar_reembolso/use_case.py`
chama `HublaPort.process_refund(purchase_id, reason)`); **nenhum** evento de webhook
dispara reembolso. Modela-se como protocolo separado:

```
src/shared/domain/ports/refund_capability.py
  class RefundCapability(Protocol):
      async def get_purchase_by_email(email, account_id) -> Purchase | None
      async def process_refund(purchase_id, reason) -> RefundResult
```

O call site do agente resolve a capability num único ponto (registry →
`gateway.refund_capability`). Se for `None` (gateway sem reembolso por API), o
comportamento de negócio é **escalar para humano** (`escalar_para_humano`), com
narrowing explícito (`if cap is None:`) — sem `# type: ignore`, passando no gate `mypy`.

## Bloco 2 — Modelo de eventos em duas camadas

A rev. 1 errou ao exigir que "todo evento mapeia pra exatamente uma categoria
canônica" — ~12 dos 25 eventos Hubla (os 6 `smart_installment.*`, os 4
`refund_request.*`, `invoice.created/status_updated/expired`, `renewal_enabled/disabled`,
`customer.member_removed`) não têm categoria de comportamento natural. Duas camadas
independentes resolvem isso:

### Camada 1 — Categoria de EXIBIÇÃO (por gateway, para a UI)

Cada `GatewayEvent` declara uma **categoria de exibição** própria do gateway, só
para agrupar/colorir no catálogo da UI — exatamente como o `triggerEvents.ts` faz
hoje (Hubla: `lead`, `member`, `subscription`, `invoice`, `installment`, `refund`,
com cor/ícone/label). Não tem significado cross-gateway; cada gateway define as suas.

`GatewayEvent`:
```
gateway_event_code: str        # "subscription.activated"
display_category: str          # "subscription" (grupo da UI daquele gateway)
label, pill_label, description, icon, tone, trigger_verb   # metadata visual (migra do triggerEvents.ts)
canonical_behavior: CanonicalBehavior | None   # camada 2 (quase sempre None)
co_trigger_group: str | None   # camada 2 (ver gatilho de onboarding)
```

### Camada 2 — Comportamento CANÔNICO (mínimo, para lógica embutida)

Um enum **pequeno e fechado** no domínio (`CanonicalBehavior`), contendo **apenas**
os conceitos que disparam lógica embutida hoje. Atualmente isso é essencialmente um:

- `access_granted` — concede acesso → dispara welcome + access_case (PurchaseHandler).

A maioria dos eventos tem `canonical_behavior = None` e **não dispara nada embutido**
— e tudo bem. O usuário ainda enxerga "isso é uma compra" pela camada de exibição e
pode criar um onboarding flow em cima de qualquer evento (camada de gatilho, abaixo).

> **Por que não há comportamento canônico de reembolso:** reembolso é outbound
> (Bloco 1). O evento inbound `invoice.refunded` hoje **não** dispara lógica embutida;
> só vira log + atualização de status do lead. Mantemos assim (zero-regressão).

### Preservação da assimetria anti-duplicação (CRÍTICO)

O código distingue dois conjuntos de propósito (`hubla_event_type.py:52-71`):

- `PURCHASE_EVENT_TYPES = {subscription.activated}` → roda o PurchaseHandler
  (welcome + access_case). **Restrito a `subscription.activated` de propósito.**
- `ACTIVATION_EVENT_TYPES = {subscription.activated, customer.member_added}` →
  matching de flows de onboarding (grupo de co-disparo).

A nota no código é explícita: `customer.member_added` **NÃO** deve rodar o
PurchaseHandler, para evitar welcome/access_case duplicado. Tradução pro modelo novo:

- O PurchaseHandler embutido dispara só quando o evento tem um marcador estrito de
  "compra que concede acesso pela primeira vez" — na Hubla, só `subscription.activated`.
  Modela-se com um marcador dedicado no catálogo (ex: `runs_purchase_handler: bool`,
  `True` só em `subscription.activated`), **não** colapsando os dois eventos em
  `access_granted` para fins de welcome.
- `customer.member_added` participa do **grupo de co-disparo** de onboarding (abaixo),
  mas tem `runs_purchase_handler = False`. Assimetria preservada exatamente.

## Bloco 3 — Gatilho de onboarding: evento cru + grupo de co-disparo

O flow guarda o **evento cru** escolhido (granularidade fina do catálogo rico). O
gateway declara **grupos de co-disparo** (`co_trigger_group`): eventos do mesmo grupo
casam flows configurados para qualquer evento do grupo. Hoje há um grupo:
`access_granted_group = {subscription.activated, customer.member_added}` — fiel ao
`ACTIVATION_EVENT_TYPES` atual (`list_active_by_product_and_events`). Os demais eventos
não têm grupo → matching exato (como hoje).

Assim: o usuário escolhe "Venda ativada" e o flow dispara também em
`customer.member_added` (comportamento atual), sem perder granularidade para eventos
sem grupo.

**Validação do `trigger_event_type`:** hoje é `Literal[HublaEventType]` (estático,
resolvido em import-time). Passa a ser um **validator custom** no schema Pydantic que
resolve o gateway pelo `product_id` do request e checa o código contra o
`event_catalog()` daquele gateway. O default hardcoded `"subscription.activated"`
(`schemas/onboarding.py:68`) sai — o default passa a vir do gateway (evento marcado
como "compra padrão" no catálogo).

## Bloco 4 — Dados (migration de generalização)

Migration mecânica: `UPDATE ... SET gateway='hubla'` em todas as linhas existentes.
**Reversível** (`downgrade()` obrigatório — zero-regressão exige rollback).

| Tabela | Hoje | Depois |
|---|---|---|
| `products` | `hubla_id`, unique `uq_products_account_hubla` | + `gateway`; `hubla_id`→`gateway_product_id`; unique `(account_id, gateway, gateway_product_id)` |
| `product_hubla_aliases` | `hubla_id`, `uq_product_alias_account_hubla` | → `product_gateway_aliases` + `gateway`; unique `(account_id, gateway, gateway_product_id)` |
| `hubla_events` | `hubla_subscription_id`, `hubla_product_id`; índices `ix_hubla_events_*` | → `payment_events` + `gateway` + `canonical_behavior` (nullable); ids renomeados; índices renomeados |
| `leads` | `hubla_subscription_id`, `hubla_product_id`; `uq_leads_account_subscription`; índices `account_*` | + `gateway`; ids renomeados; unique `(account_id, gateway, gateway_subscription_id)`; índices renomeados |
| `onboarding_flows` | `trigger_event_type` | **sem mudança de coluna**; validação passa a custom (Bloco 3) |

`gateway_subscription_id` é **nullable** — gateways payment-cêntricos (Asaas/PIX
avulso) podem não ter assinatura; nesse caso a chave usa o id de transação. Campos
`utm_*`, `offer_id`, `fbp`, `session_*`, `payment_method` permanecem (genéricos o
bastante; null quando não se aplica). `subscription_status` continua string nativa
do gateway, **mas** a UI passa a usar `last_canonical_behavior`/display category para
badge/filtro (evita misturar vocabulários `active` vs `CONFIRMED`).

**Snapshots de histórico** (`onboarding_enrollments.product_name/purchase_id`,
`onboarding_enrollment_steps.*`) não referenciam `hubla_*` diretamente — não quebram.
Mas a renomeação das entities `Lead`/`Product`/`HublaEvent` atravessa
`EnrollContact`/`VariableResolver`/`resync_flow`; a renomeação deve ser **atômica e completa**.

**Mapas de alias legados que DEVEM sobreviver:**
- `LEGACY_EVENT_TYPE_MAP` (14 entradas, `hubla_event_type.py:83-98`) — usado em
  runtime (`normalize_event_type`) e como referência da migration de dados de
  `onboarding_flows.trigger_event_type`. Migra para o módulo Hubla.
- `DEPRECATED_ALIASES` (2 entradas, `triggerEvents.ts:457`) — usado por
  `getTriggerEventMeta` para renderizar timelines antigas. O endpoint de catálogo
  (Bloco 6) deve expor o mapa de legados para o frontend.

Entidades de domínio renomeiam (`HublaEvent`→`PaymentEvent`; campos de `Lead`/`Product`).
`hubla_event_type.py` (Literal de 25) é absorvido pelo catálogo do módulo Hubla.

## Bloco 5 — Webhook + pipeline de ingestão

**Endpoint genérico** `/webhook/{gateway}`: resolve o gateway no registro →
monta `WebhookRequest` (com `raw_body`) → `gateway.verify_webhook(req)` → calcula
`gateway.idempotency_key(req)` → dedup (só se a chave não for `None`) → persiste cru
em `webhook_events` → enfileira `kind="gateway_event"` com `{gateway, payload}`.

**Âncoras de compatibilidade (zero-regressão) — preservar as DIFERENÇAS atuais:**

- `/webhook/hubla` e `/webhook/purchase` **continuam com a mesma URL**. Internamente
  delegam pro caminho genérico com `gateway="hubla"`. Mas os dois NÃO são equivalentes
  hoje e a delegação **deve preservar cada um**:
  - `/webhook/hubla`: dedup key `hubla:{event_type}:{sale_id}`; sem `sale_id` →
    segue sem dedup; **nunca** 422; enfileira `kind="hubla_event"`.
  - `/webhook/purchase`: parseia com `HublaEventParser`, **pode dar 422**; dedup key
    `purchase:{purchase_id}`; enfileira `kind="purchase"`.
  - Os prefixos Redis (`hubla:` vs `purchase:`) e o contrato de 422 do `/purchase`
    são mantidos. O `idempotency_key` do gateway Hubla deve reproduzir essas chaves.
- Job kinds `hubla_event` e `purchase` seguem como alias de `gateway_event` (gateway=hubla).
  O `handle_purchase` já delega pro `handle_hubla_event` (`handlers/purchase.py:25`).
- `WebhookSource` (`webhook_event.py:10`) ganha valores por gateway (ou um campo
  `gateway` separado) — sem quebrar o log de `webhook_events`.

**Worker:** `handle_hubla_event` → `handle_gateway_event(gateway, payload)`. O
`HublaEventHandler` vira `GatewayEventHandler` genérico, preservando todo o pipeline
atual (`hubla_event_handler.py`): normaliza → resolve contato → **insert
`payment_events`** (log) → **upsert `leads`** (UTMs/sessão/valor) → publica SSE
`lead.upserted` → roteia. A única troca: parsing/lookup específico-Hubla → `registry.get(gateway).parse()`.
Roteamento preservado:
- produto resolvido por `(gateway, gateway_product_id)` + aliases + fallback por nome
- flow disparado por evento cru + grupo de co-disparo (Bloco 3)
- PurchaseHandler (welcome + access_case) só no evento marcado `runs_purchase_handler`
  (Hubla: `subscription.activated`) — assimetria preservada (Bloco 2)
- `mark_processed` em `finally`

## Bloco 6 — Subsistemas acoplados (renomeação coordenada)

Estes consomem `hubla_*` e DEVEM ser renomeados no mesmo PR (rev. 1 ignorou):

1. **Pendências / Unmapped Products** (subsistema inteiro):
   - `application/use_cases/admin/unmapped_products.py` (agrupa por `hubla_product_id`,
     cria alias, re-enfileira `kind="hubla_event"`),
   - `interface/http/routers/admin/unmapped_products.py` (contrato JSON com `hubla_product_id`),
   - `apps/web/.../onboarding/pendencias/page.tsx` + `features/unmapped/types.ts`,
   - `application/unmapped_alert.py` (texto "ID Hubla não cadastrado").
2. **Stream SSE de Leads**: `leads_pubsub.py` serializa `hubla_*` no envelope; o filtro
   do stream (`routers/admin/leads.py:251`) lê `hubla_product_id`; o EventSource do
   frontend consome. Renomear o envelope + o filtro + o consumidor juntos.
3. **Métricas Prometheus** (`observability/metrics.py:117`): `hubla_unmapped_product_total`
   e labels `WEBHOOK_RECEIVED.source="hubla"/"hubla-unified"`. Decidir nomes genéricos
   (impacta dashboards/alertas — documentar a mudança de série temporal).
4. **Contrato de API JSON/CSV**: `/admin/products` (`hubla_id` no body + msg de erro),
   `/admin/leads` + export CSV (`hubla_subscription_id`, `hubla_product_id`),
   `/admin/settings` (`hubla_webhook_secret` no response). Rename atômico back+front.
5. **Seeds**: `scripts/seed_products.py` (`INSERT ... hubla_id`, `ON CONFLICT ON
   CONSTRAINT uq_products_account_hubla`) e `scripts/seed_loja_express.py`
   (`find_active_by_hubla_id`). Atualizar — foi por aqui que os cursos foram cadastrados.
6. **Catálogo no frontend**: `triggerEvents.ts` é consumido por onboarding (FlowDrawer),
   **Leads** (`leads/page.tsx`, `LeadDrawer`) e `formatRelativeDelay.ts` — todos
   **síncronos**. Ao migrar o catálogo pro backend, definir como esses pontos obtêm a
   metadata: o `PaymentEvent`/`Lead` passa a carregar `gateway` + display metadata
   resolvida no backend (ou um cache client-side do catálogo por gateway, carregado
   uma vez). Não pode virar `undefined` no render.

## Bloco 7 — Config / Settings

`Settings → Pagamentos` já existe — agora dirigida pelo registro:
- `GET /admin/gateways` → cruza dois eixos: **disponível** (existe no registro de
  código) × **habilitado** (credenciado na conta, via `accounts.settings` JSONB).
  Os cards "em breve" acendem conforme o módulo é liberado.
- A subpágina de cada gateway gera o form a partir de `gateway.config_fields()` e
  mostra a URL `/webhook/{slug}?token=…` quando o gateway usa token. **A página da
  Hubla mostra exatamente o que mostra hoje.**
- Credenciais ficam em `accounts.settings` JSONB, generalizadas por slug
  (`settings.gateways.{slug}`), reusando `AccountConfigRepository` + Fernet +
  `token_resolver` (que já funcionam). **A tabela `integration_configs` (código morto)
  não é usada.** O `IntegrationType` (enum fechado) não entra no caminho.
- `GET /admin/gateways/{slug}/events` → serve o catálogo daquele gateway (códigos +
  display metadata + mapa de aliases legados), consumido pelo seletor de eventos e
  pelos consumidores do antigo `triggerEvents.ts`.

## Bloco 8 — Frontend

- **Form de produto**: input único `hubla_id` → dropdown de gateway (habilitados) +
  input `gateway_product_id` (label adapta: "ID na Hubla"). Com só Hubla, UX idêntica.
- **Seletor de eventos (FlowDrawer)**: busca o catálogo via `GET /admin/gateways/{slug}/events`
  e renderiza o mesmo grid rico dinamicamente. Conteúdo do `triggerEvents.ts` migra
  pro catálogo do módulo Hubla no backend.
- **Leads**: `hubla_*`→`gateway_*`, ganha coluna/filtro de gateway, badge/status via
  display category. Os consumidores síncronos do catálogo (Bloco 6.6) ajustados.

## Bloco 9 — Rollout + testes

Hubla = primeira implementação + migration mecânica reversível. Garantias:
URLs de webhook intactas (com dedup/422 preservados por endpoint); flows mantêm
`trigger_event_type`; produtos mantêm ids (→ `gateway_product_id`, gateway=hubla);
secret não se move.

**Testes:**
- **Unit**: registro (disponível×habilitado); catálogo Hubla (25 eventos presentes;
  só `subscription.activated` com `runs_purchase_handler=True`; grupo de co-disparo
  `access_granted`); `parse()` (payloads-ouro → `NormalizedEvent`); `verify_webhook`
  + `idempotency_key` reproduzindo as chaves atuais; `RefundCapability` resolvida e
  `None`-path (escala humano).
- **Integração**: webhook → enrollment → onboarding ponta-a-ponta pelo caminho
  genérico com payload Hubla, **provando paridade**; teste explícito de que
  `customer.member_added` dispara onboarding mas **não** duplica welcome/access_case.
- **Migration**: linhas recebem `gateway='hubla'`; constraints/índices renomeados
  batem; `downgrade()` restaura; zero perda; flows com `trigger_event_type` legado
  continuam válidos (LEGACY_EVENT_TYPE_MAP).
- **Contrato**: snapshot dos JSON de `/admin/products`, `/admin/leads`, export CSV e
  envelope SSE com os novos nomes; frontend types sincronizados (`tsc --noEmit`).

## Fora de escopo (YAGNI)

- Módulos Hotmart/Kiwify/Eduzz/Asaas — entram depois, cada um plugando na abstração.
  Este design entrega abstração + Hubla. **Nota:** a camada canônica (Bloco 2) é
  deliberadamente mínima justamente para não ser sobreajustada à Hubla; o segundo
  gateway validará a abstração de fato.
- UI de gestão de gateways separada de Settings.
- Cadastro de eventos pelo cliente.
- Comportamento embutido inbound para reembolso (não existe hoje; não se cria agora).

## Arquivos-chave afetados

**Backend:**
- `domain/ports/payment_gateway.py`, `domain/ports/refund_capability.py` (novos)
- `domain/value_objects/canonical_behavior.py` (novo, mínimo)
- `adapters/payment_gateways/` (novo: base, registry, hubla/{gateway,catalog,parser,refund})
- `domain/value_objects/hubla_event_type.py` (absorvido no catálogo Hubla)
- `adapters/hubla/{event_parser,v1_normalizer}.py`, `ports/hubla_port.py` (migram)
- `application/hubla_event_handler.py` → `gateway_event_handler.py`
- `application/purchase_handler.py` (revisar marcador `runs_purchase_handler`)
- `application/use_cases/admin/unmapped_products.py`, `application/unmapped_alert.py`
- `interface/http/routers/webhook_hubla.py`, `webhook_purchase.py` + rota genérica
- `interface/worker/handlers/{hubla_event,purchase}.py` → genérico
- `interface/http/routers/admin/{products,leads,unmapped_products,settings}.py` + novo `gateways.py`
- `interface/http/schemas/onboarding.py` (validator custom), `schemas/admin_*`
- `domain/entities/{product,lead,hubla_event}.py`, repos correspondentes
- `adapters/redis/leads_pubsub.py`, `adapters/observability/metrics.py`
- `domain/entities/webhook_event.py` (`WebhookSource`)
- `scripts/seed_products.py`, `scripts/seed_loja_express.py`
- migrations em `migrations/versions/` (com `downgrade()`)
- `agent/skills/processar_reembolso/use_case.py` (resolver RefundCapability)

**Frontend:**
- `features/products/` (gateway + gateway_product_id), `features/leads/`,
  `features/unmapped/`, `features/onboarding/` (catálogo via API; `triggerEvents.ts`
  → backend), `formatRelativeDelay.ts`
- `app/(admin)/settings/pagamentos/`, `app/(admin)/onboarding/pendencias/`
- `lib/api.ts` (listGateways, getGatewayEvents, …)

**Docs:** `CLAUDE.md` (tabelas/eventos/endpoints/métricas Hubla documentados;
`triggerEvents.ts` como SSoT) está desatualizado (ainda fala `followup_*`/`/followup`
embora o código já use `onboarding_*` após a migration `8bdd77da3217`) — atualizar
junto com este refactor.
