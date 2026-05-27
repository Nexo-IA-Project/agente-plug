// apps/web/src/features/onboarding/lib/triggerEvents.ts

export type HublaEventCategory =
  | "lead"
  | "member"
  | "subscription"
  | "invoice"
  | "installment"
  | "refund";

export type HublaEventType =
  // Lead
  | "lead.abandoned_checkout"
  // Member
  | "customer.member_added"
  | "customer.member_removed"
  // Subscription
  | "subscription.created"
  | "subscription.activated"
  | "subscription.expiring"
  | "subscription.deactivated"
  | "subscription.renewal_disabled"
  | "subscription.renewal_enabled"
  // Invoice
  | "invoice.created"
  | "invoice.status_updated"
  | "invoice.payment_succeeded"
  | "invoice.payment_failed"
  | "invoice.expired"
  | "invoice.refunded"
  // Installment
  | "smart_installment.created"
  | "smart_installment.aborted"
  | "smart_installment.on_schedule"
  | "smart_installment.off_schedule"
  | "smart_installment.canceled"
  | "smart_installment.completed"
  // Refund Request
  | "refund_request.created"
  | "refund_request.accepted"
  | "refund_request.canceled"
  | "refund_request.rejected";

export interface TriggerEventTone {
  text: string;
  bg: string;
  border: string;
  ring: string;
  bgActive: string;
}

export interface TriggerEventMeta {
  value: HublaEventType;
  label: string;
  pillLabel?: string;
  technical: string;
  description: string;
  category: HublaEventCategory;
  categoryLabel: string;
  icon: string;
  tone: TriggerEventTone;
  /**
   * Frase que completa "Assim que [triggerVerb]" — usada no DelayBadge do 1º step.
   * Exemplo: "a venda for ativada", "o carrinho for abandonado".
   */
  triggerVerb: string;
}

const TONE_LEAD: TriggerEventTone = {
  text: "text-amber-500",
  bg: "bg-amber-500/10",
  border: "border-amber-500/30",
  ring: "ring-amber-500",
  bgActive: "bg-amber-500/15",
};
const TONE_MEMBER: TriggerEventTone = {
  text: "text-teal-500",
  bg: "bg-teal-500/10",
  border: "border-teal-500/30",
  ring: "ring-teal-500",
  bgActive: "bg-teal-500/15",
};
const TONE_SUB: TriggerEventTone = {
  text: "text-emerald-500",
  bg: "bg-emerald-500/10",
  border: "border-emerald-500/30",
  ring: "ring-emerald-500",
  bgActive: "bg-emerald-500/15",
};
const TONE_INVOICE: TriggerEventTone = {
  text: "text-violet-500",
  bg: "bg-violet-500/10",
  border: "border-violet-500/30",
  ring: "ring-violet-500",
  bgActive: "bg-violet-500/15",
};
const TONE_INSTALLMENT: TriggerEventTone = {
  text: "text-blue-500",
  bg: "bg-blue-500/10",
  border: "border-blue-500/30",
  ring: "ring-blue-500",
  bgActive: "bg-blue-500/15",
};
const TONE_REFUND: TriggerEventTone = {
  text: "text-rose-500",
  bg: "bg-rose-500/10",
  border: "border-rose-500/30",
  ring: "ring-rose-500",
  bgActive: "bg-rose-500/15",
};

export const CATEGORY_META: Record<
  HublaEventCategory,
  { label: string; tone: TriggerEventTone; icon: string }
> = {
  lead: { label: "Lead", tone: TONE_LEAD, icon: "person_add" },
  member: { label: "Membro", tone: TONE_MEMBER, icon: "badge" },
  subscription: { label: "Assinatura", tone: TONE_SUB, icon: "autorenew" },
  invoice: { label: "Fatura", tone: TONE_INVOICE, icon: "receipt_long" },
  installment: {
    label: "Parcelamento",
    tone: TONE_INSTALLMENT,
    icon: "credit_card",
  },
  refund: { label: "Reembolso", tone: TONE_REFUND, icon: "undo" },
};

export const TRIGGER_EVENT_CATEGORIES: readonly HublaEventCategory[] = [
  "lead",
  "member",
  "subscription",
  "invoice",
  "installment",
  "refund",
];

export const TRIGGER_EVENTS: readonly TriggerEventMeta[] = [
  // Lead
  {
    value: "lead.abandoned_checkout",
    label: "Carrinho abandonado",
    pillLabel: "Carrinho abandonado",
    technical: "lead.abandoned_checkout",
    description:
      "Cliente preencheu e-mail/telefone no checkout mas não concluiu compra em 20 minutos.",
    category: "lead",
    categoryLabel: "Lead",
    icon: "remove_shopping_cart",
    tone: TONE_LEAD,
    triggerVerb: "o carrinho for abandonado",
  },
  // Member
  {
    value: "customer.member_added",
    label: "Acesso concedido",
    pillLabel: "Acesso concedido",
    technical: "customer.member_added",
    description: "Cliente recebeu acesso ao produto ou área de membros.",
    category: "member",
    categoryLabel: "Membro",
    icon: "lock_open",
    tone: TONE_MEMBER,
    triggerVerb: "o acesso for concedido",
  },
  {
    value: "customer.member_removed",
    label: "Acesso removido",
    pillLabel: "Acesso removido",
    technical: "customer.member_removed",
    description:
      "Acesso foi revogado (cancelamento, banimento, expiração).",
    category: "member",
    categoryLabel: "Membro",
    icon: "lock",
    tone: TONE_MEMBER,
    triggerVerb: "o acesso for removido",
  },
  // Subscription
  {
    value: "subscription.created",
    label: "Assinatura criada",
    pillLabel: "Assinatura criada",
    technical: "subscription.created",
    description:
      "Checkout iniciado — aguardando confirmação de pagamento (PIX, boleto, cartão pendente).",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "hourglass_top",
    tone: TONE_SUB,
    triggerVerb: "a venda for criada",
  },
  {
    value: "subscription.activated",
    label: "Venda ativada",
    pillLabel: "Venda ativada",
    technical: "subscription.activated",
    description: "Pagamento confirmado pela Hubla — assinatura ativa.",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "shopping_cart_checkout",
    tone: TONE_SUB,
    triggerVerb: "a venda for ativada",
  },
  {
    value: "subscription.expiring",
    label: "Assinatura expirada",
    pillLabel: "Assinatura expirada",
    technical: "subscription.expiring",
    description: "Data de fim atingida sem renovação.",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "schedule",
    tone: TONE_SUB,
    triggerVerb: "a assinatura expirar",
  },
  {
    value: "subscription.deactivated",
    label: "Assinatura desativada",
    pillLabel: "Assinatura desativada",
    technical: "subscription.deactivated",
    description:
      "Cancelada manualmente, por fraude, ou outras razões operacionais.",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "block",
    tone: TONE_SUB,
    triggerVerb: "a assinatura for cancelada",
  },
  {
    value: "subscription.renewal_disabled",
    label: "Renovação automática desligada",
    pillLabel: "Auto-renovação OFF",
    technical: "subscription.renewal_disabled",
    description:
      "Cliente desabilitou renovação automática — risco de churn, janela de retenção.",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "toggle_off",
    tone: TONE_SUB,
    triggerVerb: "a renovação automática for desligada",
  },
  {
    value: "subscription.renewal_enabled",
    label: "Renovação automática ligada",
    pillLabel: "Auto-renovação ON",
    technical: "subscription.renewal_enabled",
    description: "Cliente reativou renovação automática.",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "toggle_on",
    tone: TONE_SUB,
    triggerVerb: "a renovação automática for reativada",
  },
  // Invoice
  {
    value: "invoice.created",
    label: "Fatura emitida",
    pillLabel: "Fatura emitida",
    technical: "invoice.created",
    description: "Fatura criada — aguardando pagamento.",
    category: "invoice",
    categoryLabel: "Fatura",
    icon: "receipt",
    tone: TONE_INVOICE,
    triggerVerb: "a fatura for emitida",
  },
  {
    value: "invoice.status_updated",
    label: "Status da fatura mudou",
    pillLabel: "Status atualizado",
    technical: "invoice.status_updated",
    description: "Mudança genérica no status da fatura.",
    category: "invoice",
    categoryLabel: "Fatura",
    icon: "sync",
    tone: TONE_INVOICE,
    triggerVerb: "o status da fatura mudar",
  },
  {
    value: "invoice.payment_succeeded",
    label: "Pagamento confirmado",
    pillLabel: "Pagamento OK",
    technical: "invoice.payment_succeeded",
    description: "Fatura paga com sucesso.",
    category: "invoice",
    categoryLabel: "Fatura",
    icon: "task_alt",
    tone: TONE_INVOICE,
    triggerVerb: "o pagamento for confirmado",
  },
  {
    value: "invoice.payment_failed",
    label: "Pagamento falhou",
    pillLabel: "Pagamento falhou",
    technical: "invoice.payment_failed",
    description: "Cartão recusado, PIX não confirmado, etc — dunning.",
    category: "invoice",
    categoryLabel: "Fatura",
    icon: "money_off",
    tone: TONE_INVOICE,
    triggerVerb: "o pagamento falhar",
  },
  {
    value: "invoice.expired",
    label: "Fatura vencida",
    pillLabel: "Fatura vencida",
    technical: "invoice.expired",
    description: "Fatura venceu sem pagamento.",
    category: "invoice",
    categoryLabel: "Fatura",
    icon: "event_busy",
    tone: TONE_INVOICE,
    triggerVerb: "a fatura vencer",
  },
  {
    value: "invoice.refunded",
    label: "Fatura reembolsada",
    pillLabel: "Fatura reembolsada",
    technical: "invoice.refunded",
    description: "Valor devolvido ao cliente.",
    category: "invoice",
    categoryLabel: "Fatura",
    icon: "currency_exchange",
    tone: TONE_INVOICE,
    triggerVerb: "a fatura for reembolsada",
  },
  // Installment
  {
    value: "smart_installment.created",
    label: "Parcelamento criado",
    pillLabel: "Parcelamento criado",
    technical: "smart_installment.created",
    description: "Parcelamento inteligente iniciado.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "splitscreen",
    tone: TONE_INSTALLMENT,
    triggerVerb: "o parcelamento for criado",
  },
  {
    value: "smart_installment.aborted",
    label: "Cobrança de parcela falhou",
    pillLabel: "Parcela falhou",
    technical: "smart_installment.aborted",
    description: "Tentativa de cobrança de uma parcela falhou.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "warning",
    tone: TONE_INSTALLMENT,
    triggerVerb: "a cobrança de parcela falhar",
  },
  {
    value: "smart_installment.on_schedule",
    label: "Parcelamento em andamento",
    pillLabel: "Em andamento",
    technical: "smart_installment.on_schedule",
    description: "Parcelamento ativo, sem problemas.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "trending_up",
    tone: TONE_INSTALLMENT,
    triggerVerb: "o parcelamento estiver em andamento",
  },
  {
    value: "smart_installment.off_schedule",
    label: "Parcela em atraso",
    pillLabel: "Em atraso",
    technical: "smart_installment.off_schedule",
    description: "Uma ou mais parcelas estão atrasadas.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "running_with_errors",
    tone: TONE_INSTALLMENT,
    triggerVerb: "uma parcela atrasar",
  },
  {
    value: "smart_installment.canceled",
    label: "Parcelamento cancelado",
    pillLabel: "Cancelado",
    technical: "smart_installment.canceled",
    description: "Parcelamento foi cancelado.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "cancel",
    tone: TONE_INSTALLMENT,
    triggerVerb: "o parcelamento for cancelado",
  },
  {
    value: "smart_installment.completed",
    label: "Parcelamento concluído",
    pillLabel: "Concluído",
    technical: "smart_installment.completed",
    description: "Todas as parcelas foram pagas.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "check_circle",
    tone: TONE_INSTALLMENT,
    triggerVerb: "o parcelamento for concluído",
  },
  // Refund Request
  {
    value: "refund_request.created",
    label: "Pedido de reembolso aberto",
    pillLabel: "Reembolso solicitado",
    technical: "refund_request.created",
    description:
      "Cliente solicitou reembolso — última chance antes da aprovação.",
    category: "refund",
    categoryLabel: "Reembolso",
    icon: "help",
    tone: TONE_REFUND,
    triggerVerb: "o cliente pedir reembolso",
  },
  {
    value: "refund_request.accepted",
    label: "Reembolso aprovado",
    pillLabel: "Reembolso aprovado",
    technical: "refund_request.accepted",
    description: "Solicitação aceita — reembolso será processado.",
    category: "refund",
    categoryLabel: "Reembolso",
    icon: "thumb_up",
    tone: TONE_REFUND,
    triggerVerb: "o reembolso for aprovado",
  },
  {
    value: "refund_request.canceled",
    label: "Pedido de reembolso cancelado",
    pillLabel: "Cancelado pelo cliente",
    technical: "refund_request.canceled",
    description: "Cliente cancelou a solicitação.",
    category: "refund",
    categoryLabel: "Reembolso",
    icon: "undo",
    tone: TONE_REFUND,
    triggerVerb: "o pedido de reembolso for cancelado",
  },
  {
    value: "refund_request.rejected",
    label: "Pedido de reembolso negado",
    pillLabel: "Negado",
    technical: "refund_request.rejected",
    description: "Solicitação recusada.",
    category: "refund",
    categoryLabel: "Reembolso",
    icon: "thumb_down",
    tone: TONE_REFUND,
    triggerVerb: "o reembolso for negado",
  },
];

/**
 * Alias para retro-compatibilidade com flows/eventos antigos que ainda
 * estão no banco com nomes pré-migration (lead.abandoned, subscription.expiring).
 * Usado pelo getTriggerEventMeta para que o LeadDrawer renderize timeline corretamente.
 */
const DEPRECATED_ALIASES: Record<string, HublaEventType> = {
  "lead.abandoned": "lead.abandoned_checkout",
  "subscription.expiring": "subscription.expiring",
};

export function getTriggerEventMeta(
  value: string,
): TriggerEventMeta | undefined {
  const aliased = DEPRECATED_ALIASES[value] ?? value;
  return TRIGGER_EVENTS.find((e) => e.value === aliased);
}

export function getEventsByCategory(
  category: HublaEventCategory,
): TriggerEventMeta[] {
  return TRIGGER_EVENTS.filter((e) => e.category === category);
}
