"use client";

import type { UnmappedProduct } from "../types";

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

interface Props {
  items: UnmappedProduct[];
  loading: boolean;
  onResolve: (item: UnmappedProduct) => void;
}

export function UnmappedTable({ items, loading, onResolve }: Props) {
  return (
    <div className="overflow-hidden rounded-lg border border-outline-variant bg-surface-container-low">
      <table className="w-full text-sm">
        <thead className="bg-surface-container">
          <tr>
            {["Produto (Hubla)", "ID Hubla", "Leads afetados", "Visto em", ""].map(
              (h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-on-surface-variant"
                >
                  {h}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={5} className="px-4 py-10 text-center">
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
          ) : items.length === 0 ? (
            <tr>
              <td
                colSpan={5}
                className="px-4 py-16 text-center text-sm text-on-surface-variant"
              >
                <div className="flex flex-col items-center gap-2">
                  <span
                    className="material-symbols-outlined text-on-surface-variant/60"
                    style={{ fontSize: "40px" }}
                  >
                    task_alt
                  </span>
                  <span className="font-medium text-on-surface">
                    Nenhuma pendência 🎉
                  </span>
                  <span>
                    Todos os produtos recebidos da Hubla estão reconhecidos.
                  </span>
                </div>
              </td>
            </tr>
          ) : (
            items.map((item) => (
              <tr
                key={item.hubla_product_id}
                className="border-t border-outline-variant/50 transition-colors hover:bg-surface-container"
              >
                <td className="px-4 py-3 font-medium text-on-surface">
                  {item.product_name || (
                    <span className="text-on-surface-variant">Sem nome</span>
                  )}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-on-surface-variant">
                  {item.hubla_product_id}
                </td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center rounded-full border border-outline-variant bg-surface-container px-2.5 py-0.5 text-xs font-medium text-on-surface">
                    {item.affected_leads.toLocaleString("pt-BR")}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-on-surface-variant">
                  {item.first_seen && item.last_seen ? (
                    <span title={`Primeiro: ${formatDateTime(item.first_seen)}`}>
                      {formatDateTime(item.last_seen)}
                    </span>
                  ) : (
                    formatDateTime(item.last_seen)
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => onResolve(item)}
                    className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-on-primary transition-opacity hover:opacity-90"
                  >
                    <span
                      className="material-symbols-outlined"
                      style={{ fontSize: "16px" }}
                    >
                      link
                    </span>
                    Associar a produto
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
