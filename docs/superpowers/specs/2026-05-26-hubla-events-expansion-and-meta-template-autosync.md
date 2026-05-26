# Spec: Expansão Eventos Hubla + Auto-Sync Templates Meta

**Data:** 2026-05-26
**Status:** Backlog (a ser desenvolvido em conjunto)

---

## Contexto

Durante validação end-to-end do webhook Hubla em prod (2026-05-26) descobrimos 2 gaps relacionados:

1. **Sistema suporta só 6 dos 24 eventos** que a Hubla emite, limitando as automações possíveis.
2. **Templates Meta não são sincronizados** quando se troca de WABA — o banco fica com 26 templates "fantasmas" de WABAs antigas, e flows quebram com erro `(#132001) Template name does not exist in the translation` quando apontam pra templates que não existem na WABA atual.

As duas mudanças tocam o mesmo módulo (`/templates` + `/onboarding`), então faz sentido entregar juntas.

---

## Parte 1 — Expansão dos Eventos Hubla

### Estado atual

`apps/web/src/features/onboarding/lib/triggerEvents.ts` suporta 6 eventos:

| Nome no código | Hubla real | Status |
|---|---|---|
| `subscription.activated` | `subscription.activated` | ✅ |
| `subscription.created` | `subscription.created` | ✅ |
| `lead.abandoned` | `lead.abandoned_cart` | ❌ nome divergente |
| `subscription.deactivated` | `subscription.deactivated` | ✅ |
| `subscription.expiring` | `subscription.expired` | ❌ nome divergente |
| `invoice.refunded` | `invoice.refunded` | ✅ |

### Objetivo

Suportar os 24 eventos oficiais da Hubla v2 (ver `docs/hubla-webhook-events.md`):

- **Lead** (1): `lead.abandoned_cart`
- **Member** (2): `member.access_granted`, `member.access_removed`
- **Subscription** (6): `created`, `activated`, `expired`, `deactivated`, `auto_renewal_disabled`, `auto_renewal_enabled`
- **Invoice** (6): `created`, `status_updated`, `payment_completed`, `payment_failed`, `expired`, `refunded`
- **Installment** (6): `created`, `failed`, `in_progress`, `overdue`, `cancelled`, `completed`
- **Refund Request** (4): `created`, `accepted`, `cancelled`, `rejected`

### Mudanças

**Backend:**
- Schema Pydantic `HublaEventType = Literal[...24 valores...]` em `shared/domain/value_objects/`
- Validação do payload no `webhook_hubla.py`
- `HublaEventHandler._route()` precisa rotear cada tipo pra ação correta (alguns não disparam onboarding, só persistem em `hubla_events`)
- Migration: rename do enum/string `lead.abandoned` → `lead.abandoned_cart` e `subscription.expiring` → `subscription.expired` em flows existentes

**Frontend:**
- `triggerEvents.ts` — adiciona 18 entries novas com ícone Material Symbols, cor por categoria semântica, label PT-BR e descrição
- `FlowDrawer` — radio-grid passa de 2×3 para algo paginado/grouped (24 itens grandes pra mostrar)
- UI organizada por **grupos** (Lead / Subscription / Invoice / Installment / Refund Request / Member)

### Eventos de alto valor pra automação

Prioridade pra disparar flows úteis:
- `member.access_granted` — boas-vindas independente de subscription
- `invoice.payment_failed` — dunning (lembrar cliente de atualizar cartão)
- `subscription.auto_renewal_disabled` — janela de retenção pré-expiração
- `refund_request.created` — última chance antes de aprovar reembolso

---

## Parte 2 — Auto-Sync de Templates Meta

### Estado atual

- Templates Meta ficam em `meta_templates` (banco)
- Hoje o sync é manual (presumindo que existe endpoint, vamos validar)
- Quando se troca `META_API_KEY` / `META_WABA_ID` na UI, **nada acontece** com o banco de templates
- Resultado em prod hoje: 51 templates no banco, mas só 25 são reais na WABA atual (26 são fantasmas de WABAs antigas)

### Objetivo

Quando o user salvar credenciais Meta novas no `/settings`:
1. Validar credenciais (chama `GET /me` da Meta Graph API)
2. Buscar templates da nova WABA (`GET /{waba_id}/message_templates?limit=100`)
3. **Diff**:
   - Inserir templates novos
   - **Apagar templates do banco que não existem mais** na nova WABA
   - Atualizar templates em ambos (status, components, language)
4. **Validar steps** — flows com `meta_template_name` que sumiu → marca como `is_active=false` + log warning
5. **Toast no frontend** com resumo: "X sincronizados, Y removidos, Z flows desativados"

### Mudanças

**Backend:**
- `MetaClient.list_templates(waba_id)` se ainda não existir
- `SyncMetaTemplates` use case: faz o diff + commit em transação
- Trigger pontos:
  - **Auto:** `update_account_config` detecta mudança em `meta_*` → chama sync após save
  - **Manual:** endpoint `POST /admin/meta-templates/sync` (botão "Sincronizar agora")
- `OnboardingFlowRepository`: método `deactivate_with_invalid_steps(template_names_disponiveis)` que desativa flows cujos steps usam template inexistente

**Frontend:**
- Página `/templates`: botão "Sincronizar com Meta agora"
- Após salvar credenciais Meta em `/settings`: toast intermediário "Sincronizando templates..." + final "X importados, Y removidos"
- Lista de templates mostra badge "Sync: há 2 min" / "Stale: há 3 dias"

---

## Não-objetivos

- **Não automatizar criação de templates Meta** — usuário ainda cria via Meta Business ou nosso painel
- **Não migrar flows pra novos templates automaticamente** — apenas desativa quando o template some
- **Não suportar múltiplas WABAs simultâneas** — uma conta = uma WABA

---

## Critérios de Aceite

### Hubla Events
- [ ] 24 eventos disponíveis no dropdown do FlowDrawer agrupados por categoria
- [ ] Webhook real aceita os 24 tipos sem erro
- [ ] Flow com trigger novo (ex: `member.access_granted`) dispara corretamente

### Auto-Sync Templates
- [ ] Editar credenciais Meta → templates da nova WABA aparecem no painel automaticamente
- [ ] Templates fantasmas (não existem na nova WABA) são removidos do banco
- [ ] Flows que apontam pra template removido viram `is_active=false`
- [ ] Botão "Sincronizar agora" em `/templates` funciona como gatilho manual
- [ ] Erros de credencial Meta voltam erro 422 amigável

---

## Parte 3 — Bugs adjacentes descobertos durante validação (2026-05-26)

Devem ser corrigidos junto com Parte 1+2 pra evitar regressão.

### 3.1 — Nome/email do contato não atualiza no ChatNexo quando contato já existe

**Sintoma:** No painel ChatNexo, contato `+5511984479440` ficou com nome de atendente ("Sofia") ao invés de "Fabio Dias" que veio do payload.

**Causa:** `ChatNexoClient.create_conversation` no fluxo `422 fallback` (contato já existe) apenas pega o `contact_id` via search. Não faz `PATCH /contacts/{id}` pra atualizar `name`/`email` com os dados novos do payload.

**Fix:**
```python
# Após search retornar contato existente:
if existing_name != payer_full_name or existing_email != payer_email:
    await self._patch(
        f"/accounts/{account_id}/contacts/{contact_id}",
        json={"name": payer_full_name, "email": payer_email or None},
    )
```

### 3.2 — Steps com `template_variables = {}` quebram templates NAMED

**Sintoma:** Erro Meta `#132012 Parameter format does not match` ao enviar `cmp1` (que usa `{{name}}` NAMED).

**Causa:** Steps em prod estão com `template_variables = {}` (vazio). O `VariableResolver` deveria mapear `name` → `customer_name` via `ConventionStrategy`, mas:
- Ou a convention não está sendo aplicada quando `template_variables` está vazio
- Ou o `processed_params` enviado pro ChatNexo não respeita o `parameter_format` (NAMED vs POSITIONAL)

**Fix necessário:**
1. Investigar `dispatch_onboarding_step.py` — confirmar se `VariableResolver` é invocado mesmo com `template_variables={}` 
2. Antes de enviar, ler `parameter_format` do template (`meta_templates.components`) e formatar `processed_params` adequado:
   - `NAMED`: `{"name": "Fabio Dias"}`
   - `POSITIONAL`: `{"1": "Fabio Dias"}`
3. Erro Meta `#132012` deveria virar `log.error("template_params_mismatch", expected=..., sent=...)` pra debug futuro

### 3.3 — Anti-spam da Meta durante testes (`#131049`)

**Sintoma:** "This message was not delivered to maintain healthy ecosystem engagement"

**Não é bug do nosso código** — Meta bloqueia repetições do mesmo template pro mesmo destino. Considerações:
- Em prod real (1 cliente recebe 1 vez), não acontece
- Pra testes, teria que usar números diferentes ou ambiente sandbox WhatsApp
- Vale documentar no `CONTRIBUTING.md` ou similar pra evitar confusão futura

---

## Quick fix (não-spec, pode ser feito antes)

**Limpeza imediata** do banco prod (26 templates fantasmas) — pode ser via SQL direto:

```sql
DELETE FROM meta_templates
WHERE name NOT IN (
  'reabrir_conversa', 'reembolso',
  'cmp1','cmp2','cmp3','cmp4','cmp5','cmp6','cmp7','cmp8',
  'form_entregue',
  'erro_de_integrao_wedrop', 'erro_de_integrao_armazendrop',
  'login_incorreto_wedrop', 'login_incorreto_armazen',
  'loja_entregue',
  'onb_le', 'onb1','onb2','onb3','onb4','onb5','onb6','onb7','onb8'
);
```

(Os 25 nomes listados acima vieram do `GET /1496328978661186/message_templates` da WABA atual.)
