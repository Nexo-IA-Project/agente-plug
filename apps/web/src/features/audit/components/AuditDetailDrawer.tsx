"use client";

import { useEffect, useRef } from "react";
import type { AuditEventItem } from "@/features/audit/types";

const RESOURCE_LABELS: Record<string, string> = {
  auth: "Autenticação",
  user: "Usuário",
  product: "Produto",
  flow: "Flow de Onboarding",
  flow_step: "Step de Flow",
  document: "Documento KB",
  meta_template: "Template Meta",
  settings: "Configurações",
  api_token: "Token de API",
  profile: "Perfil",
  dlq: "Dead-Letter Queue",
};

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).format(new Date(iso));
}

interface Props {
  item: AuditEventItem | null;
  onClose: () => void;
}

export function AuditDetailDrawer({ item, onClose }: Props) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!item) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [item, onClose]);

  if (!item) return null;

  const metaWithoutUA = item.metadata
    ? Object.fromEntries(Object.entries(item.metadata).filter(([k]) => k !== "user_agent"))
    : {};
  const hasActionMetadata = Object.keys(metaWithoutUA).length > 0;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div className="relative mx-4 w-full max-w-xl overflow-hidden rounded-2xl border border-outline-variant bg-white shadow-2xl dark:bg-surface-container">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-outline-variant px-6 py-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
              Detalhes do Evento
            </p>
            <p className="mt-0.5 font-mono text-xs text-on-surface-variant/60">{item.id}</p>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-container-high"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>close</span>
          </button>
        </div>

        {/* Body */}
        <div className="space-y-5 px-6 py-5">
          {/* Ação + Tipo */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Ação</p>
              <span className="mt-1.5 inline-flex items-center rounded-full bg-primary-container px-3 py-1 text-xs font-medium text-on-primary-container">
                {item.action}
              </span>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Entidade</p>
              <p className="mt-1.5 text-sm text-on-surface">
                {RESOURCE_LABELS[item.resource_type] ?? item.resource_type}
              </p>
            </div>
          </div>

          {/* ID da entidade */}
          {item.resource_id && item.resource_id !== "auth" && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">ID da Entidade</p>
              <p className="mt-1.5 font-mono text-xs text-on-surface">{item.resource_id}</p>
            </div>
          )}

          {/* Usuário */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Usuário</p>
            <div className="mt-1.5 flex items-center gap-2">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary-container text-xs font-semibold text-on-secondary-container">
                {item.user_name ? item.user_name.charAt(0).toUpperCase() : "?"}
              </div>
              <div>
                <p className="text-sm font-medium text-on-surface">{item.user_name ?? "—"}</p>
                {item.user_email && item.user_email !== item.user_name && (
                  <p className="text-xs text-on-surface-variant">{item.user_email}</p>
                )}
              </div>
            </div>
          </div>

          {/* Data/Hora + IP/Geo */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Data e Hora</p>
              <p className="mt-1.5 text-sm text-on-surface">{formatDate(item.created_at)}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Origem</p>
              <p className="mt-1.5 font-mono text-xs text-on-surface">{item.ip_address ?? "—"}</p>
              {item.geo_city && (
                <p className="text-xs text-on-surface-variant">
                  {item.geo_city}, {item.geo_country}
                </p>
              )}
            </div>
          </div>

          {/* Metadados JSON */}
          {hasActionMetadata && (
            <div>
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
                  Metadados
                </p>
                <button
                  onClick={() => navigator.clipboard.writeText(JSON.stringify(metaWithoutUA, null, 2))}
                  className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-on-surface-variant transition-colors hover:bg-surface-container-high"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>content_copy</span>
                  Copiar JSON
                </button>
              </div>
              <pre className="mt-2 max-h-48 overflow-auto rounded-xl bg-surface-container-high p-3 font-mono text-xs text-on-surface">
                {JSON.stringify(metaWithoutUA, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-outline-variant px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-xl border border-outline-variant px-4 py-2 text-sm text-on-surface-variant transition-colors hover:bg-surface-container-high"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
