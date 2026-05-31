"use client";

import { useCallback, useEffect, useState } from "react";
import { listAuditEvents } from "@/lib/api";
import { RequirePermission } from "@/features/auth/components/RequirePermission";
import { AuditTable } from "@/features/audit/components/AuditTable";
import type { AuditEventItem, AuditFilters } from "@/features/audit/types";

const ACTION_OPTIONS = [
  "Login", "Logout", "Criou usuário", "Editou usuário", "Excluiu usuário",
  "Resetou senha de usuário", "Alterou própria senha", "Alterou avatar",
  "Editou perfil próprio", "Criou produto", "Editou produto", "Excluiu produto",
  "Enviou documento KB", "Excluiu documento KB", "Criou flow de follow-up",
  "Editou flow de follow-up", "Excluiu flow de follow-up", "Adicionou step ao flow",
  "Editou step do flow", "Excluiu step do flow", "Reordenou steps do flow",
  "Criou template Meta", "Excluiu template Meta", "Editou configurações",
  "Editou configuração SMTP", "Criou token de API", "Revogou token de API",
  "Criou perfil", "Editou perfil", "Excluiu perfil",
  "Reprocessou job DLQ", "Reprocessou todos os jobs DLQ", "Excluiu job DLQ",
];

export default function AuditoriaPage() {
  const [items, setItems] = useState<AuditEventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState<AuditFilters>({ page_size: 25 });

  const load = useCallback(async (f: AuditFilters, p: number) => {
    setIsLoading(true);
    try {
      const res = await listAuditEvents({ ...f, page: p });
      setItems(res.items);
      setTotal(res.total);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load(filters, page);
  }, [filters, page, load]);

  const totalPages = Math.ceil(total / (filters.page_size ?? 25));
  const hasActiveFilters = !!(filters.action || filters.date_from || filters.date_to);

  return (
    <RequirePermission perm="audit.view">
      <div className="space-y-6 p-6">
        {/* Page header */}
        <header className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
          <div className="flex items-center gap-5 px-7 py-6">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-secondary-container">
              <span
                className="material-symbols-outlined text-on-secondary-container"
                style={{ fontSize: "28px", fontVariationSettings: "'FILL' 1" }}
              >
                policy
              </span>
            </div>
            <div className="flex-1">
              <p className="text-xs font-medium text-on-surface-variant">Administração</p>
              <h1 className="mt-0.5 text-2xl font-bold text-on-surface">Auditoria</h1>
              <p className="mt-1 text-sm text-on-surface-variant">
                Registro de todas as ações realizadas no painel.
              </p>
            </div>
            {total > 0 && (
              <div className="shrink-0 rounded-xl bg-surface-container-high px-4 py-2 text-center">
                <div className="text-2xl font-bold text-on-surface">{total.toLocaleString("pt-BR")}</div>
                <div className="text-xs text-on-surface-variant">eventos</div>
              </div>
            )}
          </div>
        </header>

        {/* Filtros */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Ação</label>
            <select
              className="min-w-[180px] rounded-xl border border-outline-variant bg-white dark:bg-surface-container px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              value={filters.action ?? ""}
              onChange={(e) => {
                setPage(1);
                setFilters((f) => ({ ...f, action: e.target.value || undefined }));
              }}
            >
              <option value="">Todas as ações</option>
              {ACTION_OPTIONS.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">De</label>
            <input
              type="datetime-local"
              className="rounded-xl border border-outline-variant bg-white dark:bg-surface-container px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              value={filters.date_from ?? ""}
              onChange={(e) => {
                setPage(1);
                setFilters((f) => ({ ...f, date_from: e.target.value || undefined }));
              }}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Até</label>
            <input
              type="datetime-local"
              className="rounded-xl border border-outline-variant bg-white dark:bg-surface-container px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              value={filters.date_to ?? ""}
              onChange={(e) => {
                setPage(1);
                setFilters((f) => ({ ...f, date_to: e.target.value || undefined }));
              }}
            />
          </div>

          {hasActiveFilters && (
            <button
              onClick={() => { setPage(1); setFilters({ page_size: 25 }); }}
              className="flex items-center gap-1.5 rounded-xl border border-outline-variant px-3 py-2 text-sm text-on-surface-variant transition-colors hover:bg-surface-container-high"
            >
              <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>close</span>
              Limpar filtros
            </button>
          )}
        </div>

        {/* Tabela */}
        <AuditTable items={items} isLoading={isLoading} />

        {/* Paginação */}
        {!isLoading && totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-on-surface-variant">
              <span className="font-medium text-on-surface">{total.toLocaleString("pt-BR")}</span> registro{total !== 1 ? "s" : ""}
            </p>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="flex h-9 w-9 items-center justify-center rounded-xl border border-outline-variant text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-40"
              >
                <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>chevron_left</span>
              </button>
              <span className="min-w-[80px] text-center text-sm text-on-surface">
                {page} / {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="flex h-9 w-9 items-center justify-center rounded-xl border border-outline-variant text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-40"
              >
                <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>chevron_right</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </RequirePermission>
  );
}
