"use client";

import { useEffect, useState } from "react";
import { getAccountSettings } from "@/lib/api";
import { IntegrationSection } from "@/features/settings/components/IntegrationSection";
import type { AccountSettings } from "@/features/settings/types";

export default function SettingsPage() {
  const [settings, setSettings] = useState<AccountSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAccountSettings()
      .then(setSettings)
      .catch(() => setError("Não foi possível carregar as configurações."));
  }, []);

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center py-24">
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-error/30 bg-error-container px-8 py-6 text-center">
          <span className="material-symbols-outlined text-error" style={{ fontSize: "32px" }}>
            error_outline
          </span>
          <p className="text-body-base text-on-surface font-medium">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-1 rounded-lg bg-primary px-4 py-2 text-label-caps font-sans font-semibold uppercase tracking-wider text-on-primary transition-opacity hover:opacity-90"
          >
            Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="flex flex-1 items-center justify-center py-24">
        <div className="flex flex-col items-center gap-4">
          <span
            className="material-symbols-outlined animate-spin text-primary"
            style={{ fontSize: "36px" }}
          >
            progress_activity
          </span>
          <p className="text-body-sm text-on-surface-variant">Carregando configurações…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 pb-12">
      {/* Page header */}
      <div className="flex items-end justify-between">
        <div>
          <p className="text-label-caps font-sans uppercase tracking-wider text-on-surface-variant">
            Sistema
          </p>
          <h1 className="mt-1 text-h1 font-sans font-bold text-on-background">Configurações</h1>
          <p className="mt-1 text-body-base text-on-surface-variant">
            Credenciais de integração com serviços externos. As alterações têm efeito imediato.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-xl border border-outline-variant bg-surface-container px-4 py-2">
          <span
            className="inline-block h-2 w-2 rounded-full bg-green-400"
          />
          <span className="text-label-caps font-sans uppercase tracking-wider text-on-surface-variant">
            Agente ativo
          </span>
        </div>
      </div>

      {/* Sections */}
      <IntegrationSection initial={settings} onSaved={setSettings} />
    </div>
  );
}
