"use client";

import { useEffect, useState } from "react";
import { getAccountSettings } from "@/lib/api";
import { IntegrationSection } from "@/features/settings/components/IntegrationSection";
import { ChatNexoAgentsSection } from "@/features/settings/components/ChatNexoAgentsSection";
import { BehaviorSection } from "@/features/settings/components/BehaviorSection";
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
      <div className="flex min-h-[200px] items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-center">
          <span className="material-symbols-outlined text-error" style={{ fontSize: "32px" }}>error</span>
          <p className="text-sm font-medium text-error">{error}</p>
        </div>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="flex min-h-[200px] items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-on-surface-variant">
          <span className="material-symbols-outlined animate-spin" style={{ fontSize: "20px" }}>progress_activity</span>
          Carregando configurações...
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-12 p-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-on-surface">Configurações</h1>
        <p className="mt-1 text-sm text-on-surface-variant">
          Gerencie as integrações e o comportamento do agente de IA.
        </p>
      </div>

      {/* Integrations */}
      <IntegrationSection initial={settings} onSaved={setSettings} />

      {/* ChatNexo agents */}
      <ChatNexoAgentsSection />

      {/* Behavior */}
      {settings && <BehaviorSection initial={settings} onSaved={setSettings} />}
    </div>
  );
}
