"use client";

import { HublaWebhookCard } from "./HublaWebhookCard";
import { InlineEditField } from "@/features/settings/components/InlineEditField";
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
  step?: number;
}

interface SectionSpec {
  id: string;
  title: string;
  subtitle: string;
  icon: string;
  fields: FieldSpec[];
}

const SECTIONS: SectionSpec[] = [
  {
    id: "chatnexo",
    title: "ChatNexo",
    subtitle: "Plataforma de mensagens WhatsApp",
    icon: "chat",
    fields: [
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
    ],
  },
  {
    id: "hubla",
    title: "Hubla",
    subtitle: "Gateway de pagamentos e webhooks",
    icon: "payments",
    fields: [
      {
        key: "hubla_webhook_secret",
        label: "Webhook Secret",
        type: "secret",
        description: "Valida eventos de compra recebidos",
      },
    ],
  },
  {
    id: "meta",
    title: "Meta / WhatsApp",
    subtitle: "API oficial do WhatsApp Business",
    icon: "phone_iphone",
    fields: [
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
    ],
  },
];

function SectionCard({ section, settings, onSaved }: {
  section: SectionSpec;
  settings: AccountSettings;
  onSaved: (updated: AccountSettings) => void;
}) {
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
            {section.icon}
          </span>
        </div>
        <div>
          <p className="text-sm font-semibold text-on-surface">{section.title}</p>
          <p className="text-xs text-on-surface-variant">{section.subtitle}</p>
        </div>
      </div>

      {/* Fields */}
      <div className="flex flex-col gap-5 p-5">
        {section.fields.map((field) => (
          <InlineEditField
            key={field.key}
            label={field.label}
            value={settings[field.key] ?? ""}
            type={field.type}
            placeholder={field.placeholder}
            description={field.description}
            step={field.step}
            onSave={(val) => saveField(field.key, val)}
          />
        ))}
        {section.id === "hubla" && <HublaWebhookCard />}
      </div>
    </div>
  );
}

export function IntegrationSection({ initial, onSaved }: Props) {
  return (
    <section>
      <div className="mb-6 flex items-center gap-3">
        <div className="h-5 w-1 rounded-full bg-primary" />
        <div>
          <h2 className="text-lg font-semibold text-on-surface">Integrações</h2>
          <p className="mt-0.5 text-sm text-on-surface-variant">
            Credenciais de acesso aos serviços externos. Campos sensíveis são exibidos mascarados.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {SECTIONS.map((section) => (
          <SectionCard
            key={section.id}
            section={section}
            settings={initial}
            onSaved={onSaved}
          />
        ))}
      </div>
    </section>
  );
}
