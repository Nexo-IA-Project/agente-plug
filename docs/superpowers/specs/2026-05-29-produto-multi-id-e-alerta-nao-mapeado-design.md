# Múltiplos hubla_id por produto + alerta de produto não reconhecido

**Data:** 2026-05-29
**Status:** Aprovado (design)

## Contexto

Os follow-ups de onboarding são disparados a partir de eventos Hubla. O roteamento
(`HublaEventHandler._route`) resolve o produto por `products.hubla_id` e então busca os
flows. Hoje cada produto tem **um único** `hubla_id`.

Na prática a Hubla envia ids diferentes para o mesmo produto, dependendo do tipo de
webhook/offer:
- **v2** (`customer.member_added`) envia o id de produto canônico (ex: MVS `QaIlGtff…`, que
  bate com o catálogo → funciona).
- **v1** (`NewSale`, normalizado para `subscription.activated`) envia o **id do offer** (ex:
  Loja Express chega com `xpf1yv5W4DTcrjjahV1B` e `6KZgHokkUYRiOe8aS91C`, mas o catálogo tem o
  id de produto `mHfbJg3hAf0juI6IXJ0F`).

Quando o id não casa nenhum produto, o roteamento **dropa o evento silenciosamente** (só um
`log.warning`): o lead aparece "verde"/"Ativado" no painel, mas o follow-up **não dispara e
ninguém fica sabendo**. Já existe uma ponte (fallback por nome exato, PR #68), mas a solução
definitiva precisa de duas coisas:

1. Um produto poder ter **vários `hubla_id`** (os offers viram aliases do mesmo produto/flow).
2. **Acabar com a falha silenciosa**: quando um evento chega com um id que não casa nenhum
   produto, isso vira **alerta visível e acionável**, nunca um drop calado.

**Resultado pretendido:** qualquer id que a Hubla mandar resolve para o produto certo (se
cadastrado), e quando não resolve o operador é avisado na hora e consegue corrigir + recuperar
as vendas afetadas.

## Arquitetura (visão geral)

```
evento Hubla → handle() (cria/atualiza lead) → _route()
   ├─ find_active_by_hubla_id (products.hubla_id OU product_hubla_aliases)
   ├─ fallback por nome exato (rede secundária; PR #68)
   ├─ casou  → marca lead.product_unmatched=false → enrolla flows
   └─ NÃO casou → marca lead.product_unmatched=true
                  + log ERROR + métrica + alerta ChatNexo (não-silencioso)

Aba "Pendências" (deriva de leads.product_unmatched=true, agrupado por hubla_product_id)
   → "Associar a produto" (cria alias)  → "Reprocessar N leads" (re-enfileira hubla_events)
```

## 1. Modelo de dados

**Nova tabela `product_hubla_aliases`** (migration alembic — aditiva, não destrutiva):
- `id` UUID PK
- `account_id` UUID FK `accounts(id)` ON DELETE CASCADE
- `product_id` UUID FK `products(id)` ON DELETE CASCADE
- `hubla_id` VARCHAR(200) NOT NULL
- `created_at` timestamptz default now()
- `UniqueConstraint(account_id, hubla_id)` → um id mapeia no máximo um produto
- Index em `(account_id, hubla_id)` (atende o lookup) e em `product_id`

`products.hubla_id` permanece como id **principal** (display + compat). Não há migração de
dados: os aliases são apenas ids adicionais.

**`leads.product_unmatched`** BOOLEAN NOT NULL DEFAULT false. Índice parcial
`WHERE product_unmatched` por `account_id` para filtro/contagem rápidos.

**Settings:** novo campo de configuração `alert_whatsapp_target` (telefone/conversa interna)
em `IntegrationConfig` (JSONB `accounts.settings`), editável na tela de Settings — destino do
alerta ChatNexo. Sem valor configurado → alerta de ChatNexo é pulado (log/métrica continuam).

## 2. Resolução de produto (repo + roteamento)

`SqlProductRepository.find_active_by_hubla_id(account_id, hubla_id)` passa a resolver por
**id principal OU alias** (uma query com `LEFT JOIN`/`OR`, ou duas queries: primeiro principal,
depois alias). Mantém a assinatura atual — nenhum caller muda.

`_route` (em `HublaEventHandler`):
1. `find_active_by_hubla_id` (principal ou alias).
2. Se None e há `product_name`: `find_active_by_name` (fallback exato, já existente).
3. **Casou:** marca `lead.product_unmatched=false` (cobre reprocesso de um lead antes
   não-mapeado) e segue o fluxo atual (flows + enroll + purchase handler legado).
4. **Não casou:** marca `lead.product_unmatched=true`, emite `log.error
   hubla_event_product_unmapped`, incrementa métrica, dispara alerta ChatNexo. **Não** enrolla.

A flag do lead é aplicada via `LeadRepository` (novo método `set_product_unmatched(lead_id,
value)`), chamado a partir do resultado do `_route` (o lead já foi upsertado em `handle()`
antes do `_route`; `_route` devolve o veredito de match e `handle()`/`_route` atualiza a flag).

## 3. Aba de pendências + UI

**Backend (`interface/http/routers/admin/`):**
- `GET /admin/unmapped-products` → lista derivada de `leads WHERE product_unmatched=true`,
  agrupada por `(hubla_product_id, product_name)`: `{hubla_product_id, product_name,
  affected_leads, first_seen, last_seen}`.
- `POST /admin/unmapped-products/resolve` body `{hubla_product_id, product_id}` → cria alias em
  `product_hubla_aliases`; retorna `{affected_leads}` (quantos seriam reprocessados).
- `POST /admin/unmapped-products/reprocess` body `{hubla_product_id, schedule_mode}` →
  re-enfileira os `hubla_events` afetados (ver seção 4). `schedule_mode ∈ {from_now,
  original}`.

**Frontend (`features/onboarding/` ou novo `features/unmapped/`):**
- Página nova em **Onboarding → "Pendências"**: tabela de ids não mapeados (nome, id, nº de
  leads, visto em); ação "Associar a produto" (dropdown de produtos ativos) → resolve; depois
  botão "Reprocessar N leads" com modal de confirmação (escolha de `schedule_mode`).
- **Painel de Leads:** marcador `⚠️ Produto não reconhecido` nas linhas com
  `product_unmatched=true`; filtro "só não reconhecidos"; contador no topo. Reusa o
  `useLeadsStream`/SSE existente (o envelope do lead passa a incluir `product_unmatched`).

## 4. Reprocessamento

"Reprocessar" re-enfileira na `job_queue` um job `hubla_event` por evento afetado, usando o
**payload original** guardado em `hubla_events.payload` (selecionado por `account_id` +
`hubla_product_id` dos leads `product_unmatched=true`). O handler é idempotente: lead upsert +
dedup de enrollment por `(account_id, contact_id, flow_id, purchase_id)`.

**Timing (mitiga risco de spam):** o modal oferece duas opções:
- `original`: respeita `activatedAt`/`purchase_time` do evento — steps já vencidos disparam
  imediatamente (aviso explícito no modal).
- `from_now` (**default**): trata como se a compra fosse agora — o handler usa `clock.now()`
  como `purchase_time`, reagendando os steps a partir do momento do reprocesso.

`schedule_mode` viaja no payload re-enfileirado; `_route`/`EnrollContact` respeitam.

## 5. Alerta + observabilidade

A cada evento **não-mapeado**:
- `log.error("hubla_event_product_unmapped", hubla_product_id, product_name, payer_phone,
  lead_id)`.
- Métrica Prometheus `hubla_unmapped_product_total` (label `product_name`), exposta em
  `/metrics`.
- Alerta **ChatNexo** para `alert_whatsapp_target` (se configurado): mensagem com nome do
  produto, id não reconhecido, nome/telefone do lead e instrução ("cadastre o id em Produtos").

**Frequência:** a cada evento (decisão do produto). *Anotação para o futuro:* dá para
deduplicar por `hubla_product_id` numa janela curta (ex: TTL Redis) se o volume incomodar —
fora de escopo agora.

## 6. Estratégia de testes

**Unit:**
- `find_active_by_hubla_id` resolve por alias (mock de sessão).
- `_route`: casa por alias; casa por nome; **não casa → seta unmatched + dispara alerta +
  não enrolla**; ao casar reseta `unmatched=false`.
- Use cases `resolve` (cria alias) e `reprocess` (monta os jobs corretos; respeita
  `schedule_mode`).
- Alerta ChatNexo pulado quando `alert_whatsapp_target` ausente.

**Integration (testcontainers + alembic):**
- Migration cria `product_hubla_aliases` + coluna `leads.product_unmatched`.
- Lookup por alias retorna o produto correto.
- Evento não-mapeado marca `leads.product_unmatched=true`.
- `GET /admin/unmapped-products` agrupa corretamente; `resolve` cria alias; `reprocess`
  re-enfileira os eventos esperados.

## Fora de escopo
- Throttle/dedup do alerta por id (anotado para depois).
- Múltiplos produtos compartilhando o mesmo id (proibido pela unique constraint).
- Reescrever `products.hubla_id` como tabela única (mantido como principal por compat).
