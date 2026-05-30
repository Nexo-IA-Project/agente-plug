"use client";

import { useEffect, useState } from "react";
import { getAccountSettings } from "@/lib/api";
import { IntegrationSection } from "@/features/settings/components/IntegrationSection";
import { ChatNexoSection } from "@/features/settings/components/ChatNexoSection";
import { RequirePermission } from "@/features/auth/components/RequirePermission";
import { usePermission } from "@/features/auth/hooks/usePermission";
import type { AccountSettings } from "@/features/settings/types";

export default function SettingsPage() {
  const { isAdmin } = usePermission();
  const [settings, setSettings] = useState<AccountSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAccountSettings()
      .then(setSettings)
      .catch(() => setError("Não foi possível carregar as configurações."));
  }, []);

  return (
    <RequirePermission perm="settings.view">
      {error ? (
        <div className="flex min-h-[200px] items-center justify-center">
          <div className="flex flex-col items-center gap-2 text-center">
            <span className="material-symbols-outlined text-error" style={{ fontSize: "32px" }}>error</span>
            <p className="text-sm font-medium text-error">{error}</p>
          </div>
        </div>
      ) : !settings ? (
        <div className="flex min-h-[200px] items-center justify-center">
          <div className="flex items-center gap-2 text-sm text-on-surface-variant">
            <span className="material-symbols-outlined animate-spin" style={{ fontSize: "20px" }}>progress_activity</span>
            Carregando configurações...
          </div>
        </div>
      ) : (
        <div className="space-y-10 p-6">
      {/* Page header */}
      <header className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
        <div className="flex items-center gap-5 px-7 py-6">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary-container">
            <span
              className="material-symbols-outlined text-on-primary-container"
              style={{ fontSize: "28px", fontVariationSettings: "'FILL' 1" }}
            >
              tune
            </span>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-on-surface">Configurações</h1>
              <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-primary">
                Integrações
              </span>
            </div>
            <p className="mt-1 text-sm text-on-surface-variant">
              Gerencie as integrações e os atendentes conectados ao agente de IA.
            </p>
          </div>
        </div>
      </header>

          {isAdmin && (
            <>
              {/* ChatNexo — conexão + atendentes */}
              <ChatNexoSection initial={settings} onSaved={setSettings} />

              {/* Outras integrações — Hubla + Meta */}
              <IntegrationSection initial={settings} onSaved={setSettings} />
            </>
          )}
        </div>
      )}
    </RequirePermission>
  );
}
