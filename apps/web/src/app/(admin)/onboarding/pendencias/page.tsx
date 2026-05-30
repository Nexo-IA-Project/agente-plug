"use client";

import { useCallback, useEffect, useState } from "react";
import { listUnmapped } from "@/lib/api";
import { UnmappedTable } from "@/features/unmapped/components/UnmappedTable";
import { ResolveDrawer } from "@/features/unmapped/components/ResolveDrawer";
import { useToast } from "@/shared/hooks/useToast";
import type { UnmappedProduct } from "@/features/unmapped/types";
import { RequirePermission } from "@/features/auth/components/RequirePermission";

export default function PendenciasPage() {
  const toast = useToast();
  const [items, setItems] = useState<UnmappedProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<UnmappedProduct | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    listUnmapped()
      .then((res) => setItems(res))
      .catch((e) =>
        toast.error(e instanceof Error ? e.message : "Erro ao carregar pendências"),
      )
      .finally(() => setLoading(false));
    // toast intencionalmente omitido (novo objeto a cada render)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openResolve = (item: UnmappedProduct) => {
    setSelected(item);
    setDrawerOpen(true);
  };

  return (
    <RequirePermission perm="onboarding.view">
    <div className="space-y-5 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-h2 font-semibold text-on-surface">Pendências</h1>
          <p className="mt-1 text-sm text-on-surface-variant">
            Produtos recebidos da Hubla que ainda não foram reconhecidos. Associe
            cada um a um produto do catálogo e reprocesse os leads afetados.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 rounded-lg border border-outline-variant px-4 py-2.5 text-sm font-medium text-on-surface transition-colors hover:bg-surface-container disabled:opacity-50"
        >
          <span
            className={`material-symbols-outlined ${loading ? "animate-spin" : ""}`}
            style={{ fontSize: "18px" }}
          >
            {loading ? "progress_activity" : "refresh"}
          </span>
          Atualizar
        </button>
      </header>

      <UnmappedTable items={items} loading={loading} onResolve={openResolve} />

      <ResolveDrawer
        open={drawerOpen}
        item={selected}
        onClose={() => setDrawerOpen(false)}
        onResolved={load}
      />
    </div>
    </RequirePermission>
  );
}
