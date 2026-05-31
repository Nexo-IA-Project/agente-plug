"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import type { AccountOption } from "@/lib/auth";

interface Props {
  open: boolean;
  accounts: AccountOption[];
  /** Disparado ao escolher uma conta. Retorna a Promise para gerenciar loading. */
  onSelect: (account: AccountOption) => Promise<void>;
  onClose: () => void;
}

/**
 * Modal de escolha de conta exibido após login quando a identidade tem
 * vínculo com mais de um tenant. Scale-from-center + reveal escalonado dos
 * cards, 100% sobre tokens semânticos do design system NexoIA.
 */
export function AccountChooserModal({ open, accounts, onSelect, onClose }: Props) {
  const [mounted, setMounted] = useState(false);
  const [pendingId, setPendingId] = useState<string | null>(null);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !pendingId) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose, pendingId]);

  if (!mounted) return null;

  async function handlePick(account: AccountOption) {
    if (pendingId) return;
    setPendingId(account.account_id);
    try {
      await onSelect(account);
    } finally {
      setPendingId(null);
    }
  }

  const overlay = (
    <>
      <style>{`
        @keyframes acm-card-in {
          from { opacity: 0; transform: translateY(10px) scale(0.98); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes acm-spin { to { transform: rotate(360deg); } }
        .acm-card { animation: acm-card-in 0.4s cubic-bezier(.22,1,.36,1) both; }
        .acm-spin {
          display: inline-block; width: 16px; height: 16px;
          border: 2px solid currentColor; border-top-color: transparent;
          border-radius: 50%; animation: acm-spin 0.6s linear infinite;
        }
      `}</style>

      <div
        aria-hidden
        onClick={() => !pendingId && onClose()}
        className={`fixed inset-0 z-[80] bg-black/50 backdrop-blur-sm transition-opacity duration-200 ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-label="Escolher empresa"
        className={`pointer-events-none fixed inset-0 z-[90] flex items-center justify-center p-4 transition-opacity duration-200 ${
          open ? "opacity-100" : "opacity-0"
        }`}
      >
        <div
          onClick={(e) => e.stopPropagation()}
          className={`pointer-events-auto w-full max-w-md overflow-hidden rounded-2xl border border-outline-variant bg-surface-container shadow-2xl transition-transform duration-200 ${
            open ? "scale-100" : "scale-95"
          }`}
        >
          <header className="flex items-start gap-3 border-b border-outline-variant px-6 py-5">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-container text-on-primary-container">
              <span className="material-symbols-outlined" style={{ fontSize: 22 }}>
                apartment
              </span>
            </span>
            <div className="flex flex-col">
              <h2 className="text-lg font-semibold text-on-surface">Escolha a empresa</h2>
              <p className="text-body-sm text-on-surface-variant">
                Seu acesso está vinculado a {accounts.length} empresas. Selecione
                para continuar.
              </p>
            </div>
          </header>

          <div className="flex max-h-[60vh] flex-col gap-2 overflow-auto px-4 py-4">
            {accounts.map((acc, i) => {
              const isPending = pendingId === acc.account_id;
              return (
                <button
                  key={acc.account_id}
                  type="button"
                  disabled={!!pendingId}
                  onClick={() => handlePick(acc)}
                  style={{ animationDelay: `${i * 60}ms` }}
                  className="acm-card group relative flex items-center gap-3 overflow-hidden rounded-xl border border-outline-variant bg-surface-container-low px-4 py-3 text-left transition-all hover:border-primary hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {/* Barra de acento à esquerda no hover */}
                  <span className="absolute inset-y-0 left-0 w-1 origin-top scale-y-0 bg-primary transition-transform duration-200 group-hover:scale-y-100" />

                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface-container-highest text-on-surface-variant transition-colors group-hover:bg-primary group-hover:text-on-primary">
                    <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
                      business
                    </span>
                  </span>

                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-body-md font-medium text-on-surface">
                      {acc.account_name}
                    </span>
                    <span className="mt-1 flex flex-wrap items-center gap-1.5">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-label-sm ${
                          acc.role === "admin"
                            ? "bg-primary-container text-on-primary-container"
                            : "bg-secondary-container text-on-secondary-container"
                        }`}
                      >
                        {acc.role === "admin" ? "Admin" : "Operador"}
                      </span>
                      {acc.is_owner && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-warning/15 px-2 py-0.5 text-label-sm font-medium text-warning">
                          <span
                            className="material-symbols-outlined"
                            style={{ fontSize: 13 }}
                          >
                            shield
                          </span>
                          Owner
                        </span>
                      )}
                    </span>
                  </div>

                  <span className="shrink-0 text-on-surface-variant transition-colors group-hover:text-primary">
                    {isPending ? (
                      <span className="acm-spin" aria-label="Entrando" />
                    ) : (
                      <span
                        className="material-symbols-outlined"
                        style={{ fontSize: 20 }}
                      >
                        arrow_forward
                      </span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );

  return createPortal(overlay, document.body);
}
