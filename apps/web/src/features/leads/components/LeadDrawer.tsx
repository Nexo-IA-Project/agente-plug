"use client";

import { useEffect, useState } from "react";
import { Drawer } from "@/shared/components/Drawer";
import { getLead } from "@/lib/api";
import { getTriggerEventMeta } from "@/features/followup/lib/triggerEvents";
import { getLeadStatusBadge } from "../lib/statusBadges";
import type { Lead, LeadDetail } from "../types";

interface Props {
  lead: Lead | null;
  open: boolean;
  onClose: () => void;
}

function formatCents(c: number | null): string {
  if (c == null) return "—";
  return `R$ ${(c / 100).toFixed(2).replace(".", ",")}`;
}

function formatDateTime(d: string | null): string {
  if (!d) return "—";
  return new Date(d).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface InfoChipProps {
  label: string;
  value: string | null | undefined;
  icon?: string;
  mono?: boolean;
}

function InfoChip({ label, value, icon, mono = false }: InfoChipProps) {
  return (
    <div className="rounded-lg border border-outline-variant bg-surface-container-low p-3">
      <p className="flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-on-surface-variant">
        {icon && (
          <span className="material-symbols-outlined" style={{ fontSize: "12px" }}>
            {icon}
          </span>
        )}
        {label}
      </p>
      <p
        className={`mt-1 truncate text-sm text-on-surface ${mono ? "font-mono" : ""}`}
      >
        {value || "—"}
      </p>
    </div>
  );
}

export function LeadDrawer({ lead, open, onClose }: Props) {
  const [detail, setDetail] = useState<LeadDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && lead) {
      setLoading(true);
      getLead(lead.id)
        .then(setDetail)
        .catch(() => setDetail(null))
        .finally(() => setLoading(false));
    } else {
      setDetail(null);
    }
  }, [open, lead?.id]);

  if (!lead) {
    return <Drawer open={open} onClose={onClose} title="Lead">{null}</Drawer>;
  }

  const statusBadge = getLeadStatusBadge(lead.subscription_status);

  return (
    <Drawer open={open} onClose={onClose} title={lead.payer_name || "Lead sem nome"}>
      <div className="space-y-6">
        {/* Header card: nome + status badge + produto */}
        <div className="rounded-xl border border-outline-variant bg-surface-container p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-xs uppercase tracking-wider text-on-surface-variant">
                {lead.product_name || "—"}
              </p>
              <p className="mt-1 truncate text-base font-semibold text-on-surface">
                {lead.payer_name || "Sem nome"}
              </p>
              {lead.offer_name && (
                <p className="mt-0.5 text-xs text-on-surface-variant">
                  Oferta: {lead.offer_name}
                </p>
              )}
            </div>
            <span
              className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${statusBadge.className}`}
            >
              {statusBadge.label}
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-on-surface">
              {formatCents(lead.amount_total_cents)}
            </span>
            {lead.payment_method && (
              <span className="text-xs uppercase tracking-wider text-on-surface-variant">
                via {lead.payment_method}
              </span>
            )}
          </div>
        </div>

        {/* Info grid */}
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
            Dados do contato
          </p>
          <div className="grid grid-cols-2 gap-2">
            <InfoChip label="Telefone" value={lead.payer_phone} icon="phone" mono />
            <InfoChip label="Email" value={lead.payer_email} icon="mail" />
            <InfoChip label="CPF" value={lead.payer_document} icon="badge" mono />
            <InfoChip
              label="Hubla ID"
              value={lead.hubla_subscription_id}
              icon="qr_code_2"
              mono
            />
          </div>
        </div>

        {/* Origem (UTMs) */}
        {(lead.utm_source || lead.utm_campaign) && (
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
              Origem
            </p>
            <div className="grid grid-cols-2 gap-2">
              <InfoChip label="UTM source" value={lead.utm_source} icon="campaign" />
              <InfoChip
                label="UTM campaign"
                value={lead.utm_campaign}
                icon="ads_click"
              />
            </div>
          </div>
        )}

        {/* Timeline de eventos */}
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
            Histórico de eventos
          </p>
          {loading ? (
            <div className="flex items-center gap-2 text-on-surface-variant">
              <span
                className="material-symbols-outlined animate-spin"
                style={{ fontSize: "18px" }}
              >
                progress_activity
              </span>
              <span className="text-xs">Carregando timeline...</span>
            </div>
          ) : (detail?.events ?? []).length === 0 ? (
            <p className="text-xs text-on-surface-variant">Nenhum evento ainda.</p>
          ) : (
            <ol className="relative space-y-3 border-l border-outline-variant pl-5">
              {(detail?.events ?? []).map((e) => {
                const meta = getTriggerEventMeta(e.event_type);
                return (
                  <li key={e.id} className="relative">
                    <div
                      className={`absolute -left-[1.65rem] flex h-6 w-6 items-center justify-center rounded-full border-2 border-surface ${
                        meta?.tone.bg ?? "bg-surface-container"
                      }`}
                    >
                      <span
                        className={`material-symbols-outlined ${
                          meta?.tone.text ?? "text-on-surface-variant"
                        }`}
                        style={{ fontSize: "13px" }}
                      >
                        {meta?.icon ?? "event"}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-on-surface">
                      {meta?.label ?? e.event_type}
                    </p>
                    <p className="font-mono text-[10px] text-on-surface-variant/70">
                      {e.event_type}
                    </p>
                    <p className="mt-0.5 text-xs text-on-surface-variant">
                      {formatDateTime(e.received_at)}
                    </p>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      </div>
    </Drawer>
  );
}
