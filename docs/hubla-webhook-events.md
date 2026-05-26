# Hubla Webhook Events v2.0 — Referência

**Fonte oficial:** [Documentação Hubla — Eventos v2](https://hubla.gitbook.io/docs/webhooks/eventos-v2)

**Total:** 24 eventos em 6 categorias.

---

## Lead (1)

| Evento | Quando dispara |
|---|---|
| `lead.abandoned_cart` | Cliente entrou no checkout, preencheu email/telefone, mas não concluiu compra em 20 minutos |

## Membro (2)

| Evento | Quando dispara |
|---|---|
| `member.access_granted` | Acesso ao produto/área de membros foi concedido |
| `member.access_removed` | Acesso foi revogado (cancelamento, banimento, etc) |

## Assinatura (6)

| Evento | Quando dispara |
|---|---|
| `subscription.created` | Assinatura criada (checkout iniciado / aguardando pagamento) |
| `subscription.activated` | Assinatura ativada (pagamento confirmado) |
| `subscription.expired` | Data de fim atingida sem renovação |
| `subscription.deactivated` | Assinatura desativada (cancelada manualmente, fraude, etc) |
| `subscription.auto_renewal_disabled` | Cliente desabilitou renovação automática |
| `subscription.auto_renewal_enabled` | Cliente reativou renovação automática |

## Fatura (6)

| Evento | Quando dispara |
|---|---|
| `invoice.created` | Fatura emitida (boleto/PIX/cartão pendente) |
| `invoice.status_updated` | Status da fatura mudou (qualquer mudança) |
| `invoice.payment_completed` | Pagamento confirmado |
| `invoice.payment_failed` | Falha no pagamento (cartão recusado, PIX não confirmado, etc) |
| `invoice.expired` | Fatura venceu sem pagamento |
| `invoice.refunded` | Fatura reembolsada |

## Parcelamento Inteligente (6)

| Evento | Quando dispara |
|---|---|
| `installment.created` | Parcelamento criado |
| `installment.failed` | Tentativa de cobrança de parcela falhou |
| `installment.in_progress` | Parcelamento ativo (em andamento) |
| `installment.overdue` | Parcela em atraso |
| `installment.cancelled` | Parcelamento cancelado |
| `installment.completed` | Todas as parcelas pagas |

## Solicitação de Reembolso (4)

| Evento | Quando dispara |
|---|---|
| `refund_request.created` | Cliente abriu solicitação de reembolso |
| `refund_request.accepted` | Solicitação aceita (reembolso será processado) |
| `refund_request.cancelled` | Solicitação cancelada pelo cliente |
| `refund_request.rejected` | Solicitação recusada |

---

## Eventos atualmente suportados no Onboarding

Arquivo: `apps/web/src/features/onboarding/lib/triggerEvents.ts`

| Nome no nosso código | Evento Hubla real | Status |
|---|---|---|
| `subscription.activated` | `subscription.activated` | ✅ bate |
| `subscription.created` | `subscription.created` | ✅ bate |
| `lead.abandoned` | `lead.abandoned_cart` | ❌ nome divergente |
| `subscription.deactivated` | `subscription.deactivated` | ✅ bate |
| `subscription.expiring` | `subscription.expired` | ❌ nome divergente |
| `invoice.refunded` | `invoice.refunded` | ✅ bate |

**4 eventos com nomes corretos, 2 divergentes.**

## Eventos NÃO suportados ainda (18)

### Alto valor pra automação
- `member.access_granted` — gatilho clássico de boas-vindas (paralelo ao `subscription.activated`, útil em cenários sem subscription)
- `member.access_removed` — win-back, oferta de retenção pós-cancelamento
- `invoice.payment_failed` — dunning: lembrar cliente de atualizar cartão
- `subscription.auto_renewal_disabled` — janela de retenção pré-expiração
- `refund_request.created` — última chance antes de aprovar reembolso

### Operacional / financeiro
- `invoice.created`, `invoice.status_updated`, `invoice.payment_completed`, `invoice.expired`
- `installment.*` (6 eventos)
- `subscription.auto_renewal_enabled`
- `refund_request.accepted` / `cancelled` / `rejected`

---

## Próximos passos sugeridos

1. **Corrigir 2 nomes divergentes** no `triggerEvents.ts` + verificar parser no backend
2. **Adicionar `member.access_granted`** (alto impacto — boas-vindas independente de subscription)
3. **Adicionar `invoice.payment_failed`** (dunning automatizado)
4. **Spec dedicado** pra expandir os 18 eventos de uma vez, incluindo:
   - Atualizar UI do FlowDrawer com novos grupos/cores
   - Validação Pydantic `Literal[HublaEventType]` com novos valores
   - Parser de payload pra capturar campos específicos de cada categoria
