export interface LeadStatusBadge {
  label: string;
  /** Tailwind classes for the pill */
  className: string;
}

export const LEAD_STATUS_BADGES: Record<string, LeadStatusBadge> = {
  active: {
    label: "Ativado",
    className: "bg-emerald-500/10 text-emerald-500 border-emerald-500/30",
  },
  inactive: {
    label: "Inativo",
    className: "bg-amber-500/10 text-amber-500 border-amber-500/30",
  },
  abandoned: {
    label: "Abandonado",
    className: "bg-amber-500/10 text-amber-500 border-amber-500/30",
  },
  refunded: {
    label: "Reembolsado",
    className: "bg-orange-500/10 text-orange-500 border-orange-500/30",
  },
  cancelled: {
    label: "Cancelado",
    className: "bg-rose-500/10 text-rose-500 border-rose-500/30",
  },
  unknown: {
    label: "—",
    className:
      "bg-surface-container text-on-surface-variant border-outline-variant",
  },
};

export function getLeadStatusBadge(status: string): LeadStatusBadge {
  return LEAD_STATUS_BADGES[status] ?? LEAD_STATUS_BADGES.unknown;
}
