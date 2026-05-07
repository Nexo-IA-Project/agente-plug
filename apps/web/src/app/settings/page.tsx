"use client";

import { useEffect, useState } from "react";
import { getAccountSettings } from "@/lib/api";
import { IntegrationSection } from "@/features/settings/components/IntegrationSection";
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
      <div className="flex flex-1 items-center justify-center py-16">
        <div className="rounded-xl border border-error bg-error-container p-6 text-on-error-container">
          <span className="material-symbols-outlined text-error" style={{ fontSize: "24px" }}>error</span>
          <p className="mt-2 text-body-base">{error}</p>
        </div>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="flex flex-1 items-center justify-center py-16">
        <span className="material-symbols-outlined animate-spin text-on-surface-variant" style={{ fontSize: "32px" }}>
          progress_activity
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-h1 font-sans font-bold text-on-background">Configurações</h1>
        <p className="mt-1 text-body-base text-on-surface-variant">
          Credenciais de integração e parâmetros do agente. As alterações têm efeito imediato.
        </p>
      </div>
      <IntegrationSection initial={settings} onSaved={setSettings} />
      <BehaviorSection initial={settings} onSaved={setSettings} />
    </div>
  );
}
