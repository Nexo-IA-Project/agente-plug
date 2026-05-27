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
  | "lead.abandoned_cart"
  // Member
  | "member.access_granted"
  | "member.access_removed"
  // Subscription
  | "subscription.created"
  | "subscription.activated"
  | "subscription.expired"
  | "subscription.deactivated"
  | "subscription.auto_renewal_disabled"
  | "subscription.auto_renewal_enabled"
  // Invoice
  | "invoice.created"
  | "invoice.status_updated"
  | "invoice.payment_completed"
  | "invoice.payment_failed"
  | "invoice.expired"
  | "invoice.refunded"
  // Installment
  | "installment.created"
  | "installment.failed"
  | "installment.in_progress"
  | "installment.overdue"
  | "installment.cancelled"
  | "installment.completed"
  // Refund Request
  | "refund_request.created"
  | "refund_request.accepted"
  | "refund_request.cancelled"
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
    value: "lead.abandoned_cart",
    label: "Carrinho abandonado",
    pillLabel: "Carrinho abandonado",
    technical: "lead.abandoned_cart",
    description:
      "Cliente preencheu e-mail/telefone no checkout mas não concluiu compra em 20 minutos.",
    category: "lead",
    categoryLabel: "Lead",
    icon: "remove_shopping_cart",
    tone: TONE_LEAD,
  },
  // Member
  {
    value: "member.access_granted",
    label: "Acesso concedido",
    pillLabel: "Acesso concedido",
    technical: "member.access_granted",
    description: "Cliente recebeu acesso ao produto ou área de membros.",
    category: "member",
    categoryLabel: "Membro",
    icon: "lock_open",
    tone: TONE_MEMBER,
  },
  {
    value: "member.access_removed",
    label: "Acesso removido",
    pillLabel: "Acesso removido",
    technical: "member.access_removed",
    description:
      "Acesso foi revogado (cancelamento, banimento, expiração).",
    category: "member",
    categoryLabel: "Membro",
    icon: "lock",
    tone: TONE_MEMBER,
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
  },
  {
    value: "subscription.expired",
    label: "Assinatura expirada",
    pillLabel: "Assinatura expirada",
    technical: "subscription.expired",
    description: "Data de fim atingida sem renovação.",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "schedule",
    tone: TONE_SUB,
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
  },
  {
    value: "subscription.auto_renewal_disabled",
    label: "Renovação automática desligada",
    pillLabel: "Auto-renovação OFF",
    technical: "subscription.auto_renewal_disabled",
    description:
      "Cliente desabilitou renovação automática — risco de churn, janela de retenção.",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "toggle_off",
    tone: TONE_SUB,
  },
  {
    value: "subscription.auto_renewal_enabled",
    label: "Renovação automática ligada",
    pillLabel: "Auto-renovação ON",
    technical: "subscription.auto_renewal_enabled",
    description: "Cliente reativou renovação automática.",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "toggle_on",
    tone: TONE_SUB,
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
  },
  {
    value: "invoice.payment_completed",
    label: "Pagamento confirmado",
    pillLabel: "Pagamento OK",
    technical: "invoice.payment_completed",
    description: "Fatura paga com sucesso.",
    category: "invoice",
    categoryLabel: "Fatura",
    icon: "task_alt",
    tone: TONE_INVOICE,
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
  },
  // Installment
  {
    value: "installment.created",
    label: "Parcelamento criado",
    pillLabel: "Parcelamento criado",
    technical: "installment.created",
    description: "Parcelamento inteligente iniciado.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "splitscreen",
    tone: TONE_INSTALLMENT,
  },
  {
    value: "installment.failed",
    label: "Cobrança de parcela falhou",
    pillLabel: "Parcela falhou",
    technical: "installment.failed",
    description: "Tentativa de cobrança de uma parcela falhou.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "warning",
    tone: TONE_INSTALLMENT,
  },
  {
    value: "installment.in_progress",
    label: "Parcelamento em andamento",
    pillLabel: "Em andamento",
    technical: "installment.in_progress",
    description: "Parcelamento ativo, sem problemas.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "trending_up",
    tone: TONE_INSTALLMENT,
  },
  {
    value: "installment.overdue",
    label: "Parcela em atraso",
    pillLabel: "Em atraso",
    technical: "installment.overdue",
    description: "Uma ou mais parcelas estão atrasadas.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "running_with_errors",
    tone: TONE_INSTALLMENT,
  },
  {
    value: "installment.cancelled",
    label: "Parcelamento cancelado",
    pillLabel: "Cancelado",
    technical: "installment.cancelled",
    description: "Parcelamento foi cancelado.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "cancel",
    tone: TONE_INSTALLMENT,
  },
  {
    value: "installment.completed",
    label: "Parcelamento concluído",
    pillLabel: "Concluído",
    technical: "installment.completed",
    description: "Todas as parcelas foram pagas.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "check_circle",
    tone: TONE_INSTALLMENT,
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
  },
  {
    value: "refund_request.cancelled",
    label: "Pedido de reembolso cancelado",
    pillLabel: "Cancelado pelo cliente",
    technical: "refund_request.cancelled",
    description: "Cliente cancelou a solicitação.",
    category: "refund",
    categoryLabel: "Reembolso",
    icon: "undo",
    tone: TONE_REFUND,
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
  },
];

/**
 * Alias para retro-compatibilidade com flows/eventos antigos que ainda
 * estão no banco com nomes pré-migration (lead.abandoned, subscription.expiring).
 * Usado pelo getTriggerEventMeta para que o LeadDrawer renderize timeline corretamente.
 */
const DEPRECATED_ALIASES: Record<string, HublaEventType> = {
  "lead.abandoned": "lead.abandoned_cart",
  "subscription.expiring": "subscription.expired",
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
