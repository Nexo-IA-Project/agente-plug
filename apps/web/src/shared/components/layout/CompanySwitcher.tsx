"use client";

import { useEffect, useRef, useState } from "react";
import { getMyMemberships, type MyMembership } from "@/lib/api";
import { switchAccount, setToken } from "@/lib/auth";
import { useToast } from "@/shared/hooks/useToast";

/**
 * Seletor de empresa (tenant) na TopBar. Quando a identidade tem mais de um
 * vínculo, vira um dropdown discreto que permite alternar de conta sem logout.
 * Com vínculo único, exibe apenas o nome da empresa atual.
 */
export function CompanySwitcher() {
  const [memberships, setMemberships] = useState<MyMembership[] | null>(null);
  const [open, setOpen] = useState(false);
  const [switching, setSwitching] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const toast = useToast();

  useEffect(() => {
    let alive = true;
    getMyMemberships()
      .then((m) => alive && setMemberships(m))
      .catch(() => alive && setMemberships([]));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onClick);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!memberships || memberships.length === 0) return null;

  const current = memberships.find((m) => m.is_current) ?? memberships[0];
  const multi = memberships.length > 1;

  async function handleSwitch(m: MyMembership) {
    if (m.is_current || switching) {
      setOpen(false);
      return;
    }
    setSwitching(m.account_id);
    try {
      const token = await switchAccount(m.account_id);
      setToken(token);
      window.location.reload();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Falha ao trocar de empresa",
      );
      setSwitching(null);
    }
  }

  // Vínculo único: rótulo estático e discreto.
  if (!multi) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-outline-variant bg-surface-container px-3 py-1.5">
        <span
          className="material-symbols-outlined text-on-surface-variant"
          style={{ fontSize: 18 }}
        >
          apartment
        </span>
        <span className="max-w-[180px] truncate text-body-sm font-medium text-on-surface">
          {current.account_name}
        </span>
      </div>
    );
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 transition-colors ${
          open
            ? "border-primary bg-surface-container-high"
            : "border-outline-variant bg-surface-container hover:bg-surface-container-high"
        }`}
      >
        <span
          className="material-symbols-outlined text-on-surface-variant"
          style={{ fontSize: 18 }}
        >
          apartment
        </span>
        <span className="max-w-[160px] truncate text-body-sm font-medium text-on-surface">
          {current.account_name}
        </span>
        <span
          className={`material-symbols-outlined text-on-surface-variant transition-transform ${
            open ? "rotate-180" : ""
          }`}
          style={{ fontSize: 18 }}
        >
          expand_more
        </span>
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute left-0 top-full z-50 mt-2 w-72 origin-top overflow-hidden rounded-xl border border-outline-variant bg-surface-container shadow-2xl"
          style={{ animation: "cs-pop 0.15s cubic-bezier(.22,1,.36,1)" }}
        >
          <style>{`
            @keyframes cs-pop {
              from { opacity: 0; transform: translateY(-6px) scale(0.98); }
              to   { opacity: 1; transform: translateY(0) scale(1); }
            }
          `}</style>
          <div className="border-b border-outline-variant px-3 py-2">
            <span className="text-label-sm uppercase tracking-wide text-on-surface-variant">
              Trocar de empresa
            </span>
          </div>
          <ul className="max-h-80 overflow-auto py-1">
            {memberships.map((m) => {
              const isSwitching = switching === m.account_id;
              return (
                <li key={m.account_id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={m.is_current}
                    disabled={!!switching}
                    onClick={() => handleSwitch(m)}
                    className={`flex w-full items-center gap-2 px-3 py-2.5 text-left transition-colors disabled:opacity-60 ${
                      m.is_current
                        ? "bg-primary-container/60"
                        : "hover:bg-surface-container-high"
                    }`}
                  >
                    <span
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                        m.is_current
                          ? "bg-primary text-on-primary"
                          : "bg-surface-container-highest text-on-surface-variant"
                      }`}
                    >
                      <span
                        className="material-symbols-outlined"
                        style={{ fontSize: 18 }}
                      >
                        business
                      </span>
                    </span>
                    <div className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-body-sm font-medium text-on-surface">
                        {m.account_name}
                      </span>
                      <span className="mt-0.5 flex items-center gap-1.5">
                        <span className="text-label-sm text-on-surface-variant">
                          {m.role === "admin" ? "Admin" : "Operador"}
                        </span>
                        {m.is_owner && (
                          <span className="inline-flex items-center gap-0.5 text-label-sm font-medium text-warning">
                            <span
                              className="material-symbols-outlined"
                              style={{ fontSize: 12 }}
                            >
                              shield
                            </span>
                            Owner
                          </span>
                        )}
                      </span>
                    </div>
                    <span className="shrink-0">
                      {isSwitching ? (
                        <span
                          className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-on-surface-variant border-t-transparent"
                          aria-label="Trocando"
                        />
                      ) : m.is_current ? (
                        <span
                          className="material-symbols-outlined text-primary"
                          style={{ fontSize: 18 }}
                        >
                          check
                        </span>
                      ) : null}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
