"use client";

import { useEffect, useState } from "react";
import { downloadLeadsCsv, listLeads } from "@/lib/api";
import { LeadDrawer } from "@/features/leads/components/LeadDrawer";
import { getLeadStatusBadge } from "@/features/leads/lib/statusBadges";
import { useToast } from "@/shared/hooks/useToast";
import { useProducts } from "@/features/products/hooks/useProducts";
import { getTriggerEventMeta } from "@/features/onboarding/lib/triggerEvents";
import type { Lead, LeadFilters } from "@/features/leads/types";

const STATUS_OPTIONS = [
  { value: "", label: "Todos os status" },
  { value: "active", label: "Ativado" },
  { value: "inactive", label: "Inativo" },
  { value: "abandoned", label: "Abandonado" },
  { value: "refunded", label: "Reembolsado" },
  { value: "cancelled", label: "Cancelado" },
];

function formatCents(c: number | null): string {
  if (c == null) return "—";
  return `R$ ${(c / 100).toFixed(2).replace(".", ",")}`;
}

function formatDateTime(d: string): string {
  return new Date(d).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function toIsoStartOfDay(dateStr: string): string | undefined {
  if (!dateStr) return undefined;
  return new Date(dateStr + "T00:00:00").toISOString();
}

function toIsoEndOfDay(dateStr: string): string | undefined {
  if (!dateStr) return undefined;
  return new Date(dateStr + "T23:59:59.999").toISOString();
}

export default function LeadsPage() {
  const toast = useToast();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<LeadFilters>({ page: 1, page_size: 25 });
  const [utmInput, setUtmInput] = useState("");
  const [dateFromInput, setDateFromInput] = useState("");
  const [dateToInput, setDateToInput] = useState("");
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  const { products, loading: productsLoading } = useProducts();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listLeads(filters)
      .then((res) => {
        if (cancelled) return;
        setLeads(res.items);
        setTotal(res.total);
      })
      .catch((e) => {
        if (cancelled) return;
        toast.error(e instanceof Error ? e.message : "Erro ao carregar leads");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // `toast` é intencionalmente omitido: useToast() retorna objeto novo a cada
    // render (sonner wrapper), incluí-lo causa loop infinito de useEffect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const updateFilter = (patch: Partial<LeadFilters>) => {
    setFilters((prev) => ({ ...prev, ...patch, page: 1 }));
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      await downloadLeadsCsv(filters);
      toast.success("CSV baixado");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao exportar CSV");
    } finally {
      setExporting(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / (filters.page_size ?? 25)));
  const currentPage = filters.page ?? 1;
  const hasActiveFilters = !!(
    filters.product_id ||
    filters.status ||
    filters.utm_source ||
    filters.date_from ||
    filters.date_to
  );

  const clearFilters = () => {
    setUtmInput("");
    setDateFromInput("");
    setDateToInput("");
    setFilters({ page: 1, page_size: 25 });
  };

  return (
    <div className="space-y-5 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-h2 font-semibold text-on-surface">Leads</h1>
          <p className="mt-1 text-sm text-on-surface-variant">
            {total > 0
              ? `${total.toLocaleString("pt-BR")} lead${total === 1 ? "" : "s"} registrado${total === 1 ? "" : "s"}`
              : "Nenhum lead ainda"}
          </p>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting || total === 0}
          className="flex items-center gap-2 rounded-lg border border-outline-variant px-4 py-2.5 text-sm font-medium text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span
            className={`material-symbols-outlined ${exporting ? "animate-spin" : ""}`}
            style={{ fontSize: "18px" }}
          >
            {exporting ? "progress_activity" : "download"}
          </span>
          {exporting ? "Exportando..." : "Exportar CSV"}
        </button>
      </div>

      {/* Filtros */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-outline-variant bg-surface-container-low p-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
          Filtros
        </span>

        {/* Produto */}
        <select
          value={filters.product_id ?? ""}
          onChange={(e) => updateFilter({ product_id: e.target.value || undefined })}
          disabled={productsLoading || products.length === 0}
          className="field-select !w-auto min-w-[180px] disabled:opacity-60"
        >
          <option value="">Todos os produtos</option>
          {products.map((p) => (
            <option key={p.id} value={p.hubla_id}>
              {p.name}
            </option>
          ))}
        </select>

        {/* Status */}
        <select
          value={filters.status ?? ""}
          onChange={(e) => updateFilter({ status: e.target.value || undefined })}
          className="field-select !w-auto min-w-[180px]"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        {/* Date range */}
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={dateFromInput}
            onChange={(e) => {
              setDateFromInput(e.target.value);
              updateFilter({ date_from: toIsoStartOfDay(e.target.value) });
            }}
            className="field-input !w-auto"
            title="Data de início"
          />
          <span className="text-on-surface-variant">—</span>
          <input
            type="date"
            value={dateToInput}
            onChange={(e) => {
              setDateToInput(e.target.value);
              updateFilter({ date_to: toIsoEndOfDay(e.target.value) });
            }}
            className="field-input !w-auto"
            title="Data de fim"
          />
        </div>

        {/* UTM source */}
        <input
          type="text"
          placeholder="Filtrar por UTM source..."
          value={utmInput}
          onChange={(e) => setUtmInput(e.target.value)}
          onBlur={() => updateFilter({ utm_source: utmInput || undefined })}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              updateFilter({ utm_source: utmInput || undefined });
            }
          }}
          className="field-input !w-56"
        />

        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="ml-auto text-xs text-primary hover:underline"
          >
            Limpar filtros
          </button>
        )}
      </div>

      {/* Tabela */}
      <div className="overflow-hidden rounded-lg border border-outline-variant bg-surface-container-low">
        <table className="w-full text-sm">
          <thead className="bg-surface-container">
            <tr>
              {[
                "Nome",
                "Telefone",
                "Produto",
                "Valor",
                "Status",
                "Evento",
                "UTM",
                "Último evento",
              ].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-on-surface-variant"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center">
                  <div className="inline-flex items-center gap-2 text-sm text-on-surface-variant">
                    <span
                      className="material-symbols-outlined animate-spin"
                      style={{ fontSize: "18px" }}
                    >
                      progress_activity
                    </span>
                    Carregando...
                  </div>
                </td>
              </tr>
            ) : leads.length === 0 ? (
              <tr>
                <td
                  colSpan={8}
                  className="px-4 py-10 text-center text-sm text-on-surface-variant"
                >
                  Nenhum lead encontrado com esses filtros.
                </td>
              </tr>
            ) : (
              leads.map((lead) => {
                const badge = getLeadStatusBadge(lead.subscription_status);
                const eventMeta = getTriggerEventMeta(lead.last_event_type);
                return (
                  <tr
                    key={lead.id}
                    onClick={() => {
                      setSelectedLead(lead);
                      setDrawerOpen(true);
                    }}
                    className="cursor-pointer border-t border-outline-variant/50 transition-colors hover:bg-surface-container"
                  >
                    <td className="px-4 py-3 font-medium text-on-surface">
                      {lead.payer_name || "—"}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-on-surface-variant">
                      {lead.payer_phone}
                    </td>
                    <td className="max-w-[180px] truncate px-4 py-3 text-on-surface-variant">
                      {lead.product_name}
                    </td>
                    <td className="px-4 py-3 text-on-surface">
                      {formatCents(lead.amount_total_cents)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${badge.className}`}
                      >
                        {badge.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {eventMeta ? (
                        <span
                          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-medium ${eventMeta.tone.bg} ${eventMeta.tone.text} ${eventMeta.tone.border}`}
                          title={eventMeta.description}
                        >
                          <span
                            className="material-symbols-outlined"
                            style={{ fontSize: "12px" }}
                          >
                            {eventMeta.icon}
                          </span>
                          {eventMeta.label}
                        </span>
                      ) : (
                        <span className="text-on-surface-variant">
                          {lead.last_event_type || "—"}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-on-surface-variant">
                      {lead.utm_source ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-on-surface-variant">
                      {formatDateTime(lead.last_event_at)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Paginação */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-on-surface-variant">
            Página {currentPage} de {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              disabled={currentPage <= 1}
              onClick={() =>
                setFilters((p) => ({ ...p, page: Math.max(1, (p.page ?? 1) - 1) }))
              }
              className="rounded-lg border border-outline-variant px-3 py-1.5 text-xs disabled:opacity-40"
            >
              Anterior
            </button>
            <button
              disabled={currentPage >= totalPages}
              onClick={() =>
                setFilters((p) => ({ ...p, page: (p.page ?? 1) + 1 }))
              }
              className="rounded-lg border border-outline-variant px-3 py-1.5 text-xs disabled:opacity-40"
            >
              Próxima
            </button>
          </div>
        </div>
      )}

      <LeadDrawer
        lead={selectedLead}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
