"use client";

import type { AuditEventItem } from "@/features/audit/types";
import { parseUserAgent } from "@/features/audit/lib/parseUserAgent";

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  }).format(new Date(iso));
}

const DEVICE_ICONS: Record<string, string> = {
  desktop: "computer",
  mobile: "smartphone",
  tablet: "tablet",
};

interface Props {
  items: AuditEventItem[];
  isLoading: boolean;
}

export function AccessTable({ items, isLoading }: Props) {
  if (isLoading) {
    return (
      <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-outline-variant bg-surface-container-low">
              {["Data/Hora", "Evento", "Usuário", "IP", "Localização", "Navegador", "SO", "Dispositivo"].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...Array(5)].map((_, i) => (
              <tr key={i} className="border-b border-outline-variant last:border-0">
                {[...Array(8)].map((_, j) => (
                  <td key={j} className="px-4 py-3">
                    <div className="h-3.5 w-16 animate-pulse rounded-full bg-surface-container-high" />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex min-h-[200px] items-center justify-center rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
        <div className="flex flex-col items-center gap-2 text-on-surface-variant">
          <span className="material-symbols-outlined" style={{ fontSize: "40px", fontVariationSettings: "'FILL' 0, 'wght' 300" }}>login</span>
          <p className="text-sm font-medium">Nenhum acesso registrado</p>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-outline-variant bg-surface-container-low">
            {["Data/Hora", "Evento", "Usuário", "IP", "Localização", "Navegador", "SO", "Dispositivo"].map((h) => (
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const ua = parseUserAgent(item.metadata?.user_agent as string | null);
            const isLogin = item.action === "Login";
            return (
              <tr key={item.id} className="border-b border-outline-variant last:border-0 transition-colors hover:bg-surface-container-low/50">
                <td className="whitespace-nowrap px-4 py-3 text-xs tabular-nums text-on-surface-variant">
                  {formatDate(item.created_at)}
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${
                    isLogin
                      ? "bg-[#d1fae5] text-[#064e3b] dark:bg-[#064e3b] dark:text-[#d1fae5]"
                      : "bg-surface-container-high text-on-surface-variant"
                  }`}>
                    <span className="material-symbols-outlined" style={{ fontSize: "12px" }}>
                      {isLogin ? "login" : "logout"}
                    </span>
                    {item.action}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary-container text-xs font-semibold text-on-secondary-container">
                      {item.user_name ? item.user_name.charAt(0).toUpperCase() : "?"}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-on-surface max-w-[120px]">
                        {item.user_name ?? "—"}
                      </p>
                      {item.user_email && item.user_email !== item.user_name && (
                        <p className="truncate text-xs text-on-surface-variant max-w-[120px]">
                          {item.user_email}
                        </p>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-on-surface-variant whitespace-nowrap">
                  {item.ip_address ?? "—"}
                </td>
                <td className="px-4 py-3 text-xs text-on-surface-variant whitespace-nowrap">
                  {item.geo_city ? `${item.geo_city}, ${item.geo_region} - ${item.geo_country}` : "—"}
                </td>
                <td className="px-4 py-3 text-xs text-on-surface whitespace-nowrap">{ua.browser}</td>
                <td className="px-4 py-3 text-xs text-on-surface whitespace-nowrap">{ua.os}</td>
                <td className="px-4 py-3 text-xs text-on-surface-variant whitespace-nowrap">
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
                      {DEVICE_ICONS[ua.device]}
                    </span>
                    {ua.device}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
