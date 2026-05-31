"use client";

import type { AuditEventItem } from "@/features/audit/types";

const RESOURCE_COLORS: Record<string, string> = {
  auth:          "bg-primary-container text-on-primary-container",
  user:          "bg-secondary-container text-on-secondary-container",
  product:       "bg-tertiary-container text-on-tertiary-container",
  flow:          "bg-[#d1fae5] text-[#064e3b] dark:bg-[#064e3b] dark:text-[#d1fae5]",
  flow_step:     "bg-[#e0f2fe] text-[#0c4a6e] dark:bg-[#0c4a6e] dark:text-[#e0f2fe]",
  document:      "bg-surface-container-high text-on-surface-variant",
  meta_template: "bg-[#ede9fe] text-[#4c1d95] dark:bg-[#4c1d95] dark:text-[#ede9fe]",
  settings:      "bg-error-container text-on-error-container",
  api_token:     "bg-surface-container-highest text-on-surface",
  profile:       "bg-secondary-container text-on-secondary-container",
  dlq:           "bg-error-container text-on-error-container",
};

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(iso));
}

interface Props {
  items: AuditEventItem[];
  isLoading: boolean;
  onDetails?: (item: AuditEventItem) => void;
}

export function AuditTable({ items, isLoading, onDetails }: Props) {
  if (isLoading) {
    return (
      <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-outline-variant bg-surface-container-low">
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Usuário</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Ação</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant">IP · Localidade</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Data e Hora</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {[...Array(5)].map((_, i) => (
              <tr key={i} className="border-b border-outline-variant last:border-0">
                <td className="px-4 py-3"><div className="h-3.5 w-32 animate-pulse rounded-full bg-surface-container-high" /></td>
                <td className="px-4 py-3"><div className="h-6 w-28 animate-pulse rounded-full bg-surface-container-high" /></td>
                <td className="px-4 py-3">
                  <div className="h-3.5 w-24 animate-pulse rounded-full bg-surface-container-high" />
                  <div className="mt-1 h-3 w-16 animate-pulse rounded-full bg-surface-container-high" />
                </td>
                <td className="px-4 py-3"><div className="h-3.5 w-36 animate-pulse rounded-full bg-surface-container-high" /></td>
                <td key="btn" className="px-4 py-3"><div className="h-4 w-16 animate-pulse rounded-full bg-surface-container-high" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex min-h-[240px] items-center justify-center rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
        <div className="flex flex-col items-center gap-3 text-on-surface-variant">
          <span
            className="material-symbols-outlined"
            style={{ fontSize: "48px", fontVariationSettings: "'FILL' 0, 'wght' 300" }}
          >
            history
          </span>
          <p className="text-sm font-medium">Nenhuma ação registrada</p>
          <p className="text-xs text-on-surface-variant/60">As ações do painel aparecerão aqui</p>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-outline-variant bg-surface-container-low">
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Usuário</th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Ação</th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant">IP · Localidade</th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Data e Hora</th>
            <th className="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const colorClass = RESOURCE_COLORS[item.resource_type] ?? "bg-surface-container-high text-on-surface";
            return (
              <tr
                key={item.id}
                className="border-b border-outline-variant last:border-0 transition-colors hover:bg-surface-container-low/50"
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary-container text-xs font-semibold text-on-secondary-container">
                      {item.user_name ? item.user_name.charAt(0).toUpperCase() : "?"}
                    </div>
                    <span className="text-sm text-on-surface truncate max-w-[140px]">
                      {item.user_name ?? <span className="text-on-surface-variant">—</span>}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${colorClass}`}>
                    {item.action}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="font-mono text-xs text-on-surface-variant">
                    {item.ip_address ?? "—"}
                  </div>
                  {item.geo_city && (
                    <div className="mt-0.5 flex items-center gap-1 text-xs text-on-surface-variant/70">
                      <span className="material-symbols-outlined" style={{ fontSize: "12px" }}>location_on</span>
                      {item.geo_city}, {item.geo_country}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-on-surface-variant tabular-nums">
                  {formatDate(item.created_at)}
                </td>
                <td className="px-4 py-3 text-right">
                  {onDetails && (
                    <button
                      onClick={() => onDetails(item)}
                      className="rounded-lg px-2.5 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary-container/40"
                    >
                      Ver Detalhes
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
