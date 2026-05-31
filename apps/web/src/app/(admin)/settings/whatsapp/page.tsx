"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAccountSettings } from "@/lib/api";
import { InlineEditField } from "@/features/settings/components/InlineEditField";
import { useFieldSave } from "@/features/settings/hooks/useIntegrationForm";
import { RequirePermission } from "@/features/auth/components/RequirePermission";
import { usePermission } from "@/features/auth/hooks/usePermission";
import type { AccountSettings } from "@/features/settings/types";

const WhatsAppIcon = (
  <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true">
    <path d="M19.05 4.91A9.82 9.82 0 0 0 12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38a9.86 9.86 0 0 0 4.73 1.2h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01zm-7.01 15.24h-.01a8.2 8.2 0 0 1-4.18-1.15l-.3-.18-3.11.82.83-3.04-.2-.31a8.18 8.18 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.24-8.24 2.2 0 4.27.86 5.82 2.42a8.18 8.18 0 0 1 2.41 5.83c0 4.54-3.7 8.24-8.23 8.24zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.25-.64.81-.79.97-.14.17-.29.19-.54.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.01-.38.11-.51.11-.11.25-.29.37-.43.13-.14.17-.25.25-.41.08-.17.04-.31-.02-.43-.06-.12-.56-1.34-.76-1.84-.2-.48-.41-.42-.56-.43-.14-.01-.31-.01-.48-.01-.17 0-.43.06-.66.31-.23.25-.86.85-.86 2.07 0 1.22.89 2.4 1.01 2.56.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.68-1.18.21-.58.21-1.07.14-1.18-.06-.1-.22-.16-.47-.28z" />
  </svg>
);

interface FieldSpec {
  key: keyof AccountSettings;
  label: string;
  type?: "text" | "secret" | "url" | "number";
  placeholder?: string;
  description?: string;
}

const META_FIELDS: FieldSpec[] = [
  {
    key: "meta_api_key",
    label: "API Key",
    type: "secret",
    description: "Token de acesso à Meta Graph API",
  },
  {
    key: "meta_waba_id",
    label: "WABA ID",
    type: "text",
    placeholder: "123456789",
    description: "ID da conta WhatsApp Business",
  },
  {
    key: "meta_app_id",
    label: "App ID",
    type: "text",
    description: "ID do App Meta (upload de mídia)",
  },
  {
    key: "alert_whatsapp_target",
    label: "Número de alerta interno (WhatsApp)",
    type: "text",
    placeholder: "+55 34 9XXXX-XXXX",
    description: "Recebe avisos quando um produto não é reconhecido no onboarding",
  },
];

function MetaCard({ settings, onSaved }: { settings: AccountSettings; onSaved: (updated: AccountSettings) => void }) {
  const { saveField } = useFieldSave(onSaved);
  const canEdit = usePermission().can("settings.edit_credentials");

  return (
    <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-outline-variant/60 bg-surface-container-low dark:bg-surface-container px-5 py-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-container text-on-primary-container">
          <span
            className="material-symbols-outlined"
            style={{ fontSize: "20px", fontVariationSettings: "'FILL' 1" }}
          >
            phone_iphone
          </span>
        </div>
        <div>
          <p className="text-sm font-semibold text-on-surface">Meta / WhatsApp</p>
          <p className="text-xs text-on-surface-variant">API oficial do WhatsApp Business</p>
        </div>
      </div>

      {/* Fields */}
      <div className="flex flex-col gap-5 p-5">
        {META_FIELDS.map((field) => (
          <InlineEditField
            key={field.key}
            label={field.label}
            value={(settings[field.key] ?? "") as string | number}
            type={field.type}
            placeholder={field.placeholder}
            description={field.description}
            readOnly={!canEdit}
            onSave={(val) => saveField(field.key, val)}
          />
        ))}
      </div>
    </div>
  );
}

export default function WhatsAppSettingsPage() {
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
        <div className="space-y-8 p-6">
          {/* Page header */}
          <header className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
            <div className="flex items-center gap-5 px-7 py-6">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary-container text-on-primary-container">
                {WhatsAppIcon}
              </div>
              <div className="flex-1">
                <Link
                  href="/settings"
                  className="inline-flex items-center gap-1 text-xs font-medium text-on-surface-variant transition-colors hover:text-on-surface"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>arrow_back</span>
                  Integrações
                </Link>
                <h1 className="mt-1 text-2xl font-bold text-on-surface">WhatsApp</h1>
                <p className="mt-1 text-sm text-on-surface-variant">
                  Credenciais da API oficial do WhatsApp Business (Meta). Campos sensíveis são mascarados.
                </p>
              </div>
            </div>
          </header>

          <MetaCard settings={settings} onSaved={setSettings} />
        </div>
      )}
    </RequirePermission>
  );
}
