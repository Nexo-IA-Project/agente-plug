"use client";

import { useCallback, useEffect, useState } from "react";
import { listAuditEvents } from "@/lib/api";
import { RequirePermission } from "@/features/auth/components/RequirePermission";
import { AccessTable } from "@/features/audit/components/AccessTable";
import type { AuditEventItem } from "@/features/audit/types";

export default function AcessoPage() {
  const [items, setItems] = useState<AuditEventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const PAGE_SIZE = 25;

  const load = useCallback(async (p: number) => {
    setIsLoading(true);
    try {
      const res = await listAuditEvents({ resource_type: "auth", page: p, page_size: PAGE_SIZE });
      setItems(res.items);
      setTotal(res.total);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { load(page); }, [page, load]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <RequirePermission perm="audit.view">
      <div className="space-y-6 p-6">
        <header className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
          <div className="flex items-center gap-5 px-7 py-6">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary-container">
              <span
                className="material-symbols-outlined text-on-primary-container"
                style={{ fontSize: "28px", fontVariationSettings: "'FILL' 1" }}
              >
                manage_accounts
              </span>
            </div>
            <div className="flex-1">
              <p className="text-xs font-medium text-on-surface-variant">Administração</p>
              <h1 className="mt-0.5 text-2xl font-bold text-on-surface">Histórico de Acesso</h1>
              <p className="mt-1 text-sm text-on-surface-variant">
                Registros de login e logout com IP, localização e dispositivo.
              </p>
            </div>
            {total > 0 && (
              <div className="shrink-0 rounded-xl bg-surface-container-high px-4 py-2 text-center">
                <div className="text-2xl font-bold text-on-surface">{total.toLocaleString("pt-BR")}</div>
                <div className="text-xs text-on-surface-variant">acessos</div>
              </div>
            )}
          </div>
        </header>

        <AccessTable items={items} isLoading={isLoading} />

        {!isLoading && totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-on-surface-variant">
              <span className="font-medium text-on-surface">{total.toLocaleString("pt-BR")}</span> registros
            </p>
            <div className="flex items-center gap-2">
              <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="flex h-9 w-9 items-center justify-center rounded-xl border border-outline-variant text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:opacity-40">
                <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>chevron_left</span>
              </button>
              <span className="min-w-[80px] text-center text-sm text-on-surface">{page} / {totalPages}</span>
              <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="flex h-9 w-9 items-center justify-center rounded-xl border border-outline-variant text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:opacity-40">
                <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>chevron_right</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </RequirePermission>
  );
}
