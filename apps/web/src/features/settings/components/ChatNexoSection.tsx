"use client";

import { InlineEditField } from "@/features/settings/components/InlineEditField";
import { ChatNexoAgentsCard } from "@/features/settings/components/ChatNexoAgentsSection";
import { useFieldSave } from "@/features/settings/hooks/useIntegrationForm";
import type { AccountSettings } from "@/features/settings/types";

interface Props {
  initial: AccountSettings;
  onSaved: (updated: AccountSettings) => void;
}

interface FieldSpec {
  key: keyof AccountSettings;
  label: string;
  type?: "text" | "secret" | "url" | "number";
  placeholder?: string;
  description?: string;
}

const CONNECTION_FIELDS: FieldSpec[] = [
  {
    key: "chatnexo_base_url",
    label: "Base URL",
    type: "url",
    placeholder: "https://api.chatnexo.com.br",
  },
  {
    key: "chatnexo_api_key",
    label: "API Key (fallback)",
    type: "secret",
    description: "Usada quando nenhum atendente está configurado",
  },
  {
    key: "chatnexo_account_id",
    label: "Account ID",
    type: "number",
    description: "ID da conta no ChatNexo (troca de conta sem deploy)",
  },
  {
    key: "chatnexo_inbox_id",
    label: "Inbox ID",
    type: "number",
    description: "ID da inbox dentro da conta",
  },
];

function ConnectionCard({ settings, onSaved }: Props & { settings: AccountSettings }) {
  const { saveField } = useFieldSave(onSaved);

  return (
    <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-outline-variant/60 bg-surface-container-low dark:bg-surface-container px-5 py-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-container">
          <span
            className="material-symbols-outlined text-on-primary-container"
            style={{ fontSize: "20px", fontVariationSettings: "'FILL' 1" }}
          >
            chat
          </span>
        </div>
        <div>
          <p className="text-sm font-semibold text-on-surface">Conexão</p>
          <p className="text-xs text-on-surface-variant">Plataforma de mensagens WhatsApp</p>
        </div>
      </div>

      {/* Fields */}
      <div className="flex flex-col gap-5 p-5">
        {CONNECTION_FIELDS.map((field) => (
          <InlineEditField
            key={field.key}
            label={field.label}
            value={settings[field.key] ?? ""}
            type={field.type}
            placeholder={field.placeholder}
            description={field.description}
            onSave={(val) => saveField(field.key, val)}
          />
        ))}
      </div>
    </div>
  );
}

export function ChatNexoSection({ initial, onSaved }: Props) {
  return (
    <section>
      <div className="mb-6 flex items-center gap-3">
        <div className="h-5 w-1 rounded-full bg-primary" />
        <div>
          <h2 className="text-lg font-semibold text-on-surface">ChatNexo</h2>
          <p className="mt-0.5 text-sm text-on-surface-variant">
            Conexão com a plataforma de mensagens e atendentes que enviam o onboarding.
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <ConnectionCard initial={initial} settings={initial} onSaved={onSaved} />
        <ChatNexoAgentsCard />
      </div>
    </section>
  );
}
