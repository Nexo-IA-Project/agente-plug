/**
 * Identidade visual unificada dos 6 tipos de evento Hubla.
 *
 * Cada evento mapeia a uma cor (hue do significado no funil), um ícone Material
 * Symbols, um label PT-BR para humanos, o nome técnico (chave da API Hubla) e
 * uma descrição operacional. Consumido por FlowDrawer (radio-grid) e FlowCard
 * (trigger pill) para que a diferenciação seja batível ao olho sem leitura.
 */

export type HublaEventType =
  | "subscription.activated"
  | "subscription.created"
  | "lead.abandoned"
  | "subscription.deactivated"
  | "subscription.expiring"
  | "invoice.refunded";

export interface TriggerEventTone {
  /** Classes Tailwind aplicadas ao ícone e ao texto colorido */
  text: string;
  /** Fundo tingido leve (10% opacity) — usado em pills e ícone container */
  bg: string;
  /** Borda colorida em 30% opacity — usada em cards selecionados e pills */
  border: string;
  /** Ring colorido para card selecionado */
  ring: string;
  /** Fundo do card quando selecionado (15% opacity) */
  bgActive: string;
}

export interface TriggerEventMeta {
  value: HublaEventType;
  label: string;
  technical: string;
  description: string;
  /** Nome do ícone Material Symbols Outlined */
  icon: string;
  /** Frase curta para o pill ("Venda ativada", "Carrinho abandonado", ...) */
  pillLabel: string;
  tone: TriggerEventTone;
}

export const TRIGGER_EVENTS: readonly TriggerEventMeta[] = [
  {
    value: "subscription.activated",
    label: "Venda ativada",
    pillLabel: "Venda ativada",
    technical: "subscription.activated",
    description: "Compra confirmada pela Hubla — pagamento aprovado.",
    icon: "shopping_cart_checkout",
    tone: {
      text: "text-emerald-500",
      bg: "bg-emerald-500/10",
      border: "border-emerald-500/30",
      ring: "ring-emerald-500",
      bgActive: "bg-emerald-500/15",
    },
  },
  {
    value: "subscription.created",
    label: "Venda pendente",
    pillLabel: "Venda pendente",
    technical: "subscription.created",
    description: "Checkout iniciado — aguardando confirmação (PIX, boleto).",
    icon: "hourglass_top",
    tone: {
      text: "text-sky-500",
      bg: "bg-sky-500/10",
      border: "border-sky-500/30",
      ring: "ring-sky-500",
      bgActive: "bg-sky-500/15",
    },
  },
  {
    value: "lead.abandoned",
    label: "Carrinho abandonado",
    pillLabel: "Carrinho abandonado",
    technical: "lead.abandoned",
    description: "Cliente iniciou checkout e desistiu antes de pagar.",
    icon: "remove_shopping_cart",
    tone: {
      text: "text-amber-500",
      bg: "bg-amber-500/10",
      border: "border-amber-500/30",
      ring: "ring-amber-500",
      bgActive: "bg-amber-500/15",
    },
  },
  {
    value: "subscription.deactivated",
    label: "Assinatura cancelada",
    pillLabel: "Cancelamento",
    technical: "subscription.deactivated",
    description: "Cliente cancelou ou perdeu acesso ao produto.",
    icon: "logout",
    tone: {
      text: "text-rose-500",
      bg: "bg-rose-500/10",
      border: "border-rose-500/30",
      ring: "ring-rose-500",
      bgActive: "bg-rose-500/15",
    },
  },
  {
    value: "subscription.expiring",
    label: "Assinatura expirando",
    pillLabel: "Expirando",
    technical: "subscription.expiring",
    description: "Assinatura próxima do vencimento — janela de retenção.",
    icon: "schedule",
    tone: {
      text: "text-orange-500",
      bg: "bg-orange-500/10",
      border: "border-orange-500/30",
      ring: "ring-orange-500",
      bgActive: "bg-orange-500/15",
    },
  },
  {
    value: "invoice.refunded",
    label: "Fatura reembolsada",
    pillLabel: "Reembolso",
    technical: "invoice.refunded",
    description: "Pagamento foi devolvido ao cliente.",
    icon: "undo",
    tone: {
      text: "text-violet-500",
      bg: "bg-violet-500/10",
      border: "border-violet-500/30",
      ring: "ring-violet-500",
      bgActive: "bg-violet-500/15",
    },
  },
] as const;

export function getTriggerEventMeta(value: string | null | undefined): TriggerEventMeta | null {
  if (!value) return null;
  return TRIGGER_EVENTS.find((e) => e.value === value) ?? null;
}
