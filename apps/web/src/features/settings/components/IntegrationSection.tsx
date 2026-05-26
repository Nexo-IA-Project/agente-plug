"use client";

import { useIntegrationForm } from "@/features/settings/hooks/useIntegrationForm";
import type { AccountSettings } from "@/features/settings/types";

// ─── Types ────────────────────────────────────────────────────────────────────

interface FieldConfig {
  key: keyof AccountSettings;
  label: string;
  type: "text" | "secret" | "url" | "number";
  placeholder?: string;
  description?: string;
}

interface ServiceGroup {
  id: string;
  name: string;
  icon: string;
  description: string;
  fields: FieldConfig[];
}

// ─── Config ───────────────────────────────────────────────────────────────────

const SERVICES: ServiceGroup[] = [
  {
    id: "chatnexo",
    name: "ChatNexo",
    icon: "chat",
    description: "Plataforma de mensagens WhatsApp",
    fields: [
      { key: "chatnexo_base_url", label: "Base URL", type: "url", placeholder: "https://api.chatnexo.com.br" },
      { key: "chatnexo_api_key", label: "API Key (fallback)", type: "secret", description: "Chave de acesso à API usada quando nenhum atendente específico está configurado" },
    ],
  },
  {
    id: "hubla",
    name: "Hubla",
    icon: "payments",
    description: "Gateway de pagamentos e webhooks",
    fields: [
      { key: "hubla_webhook_secret", label: "Webhook Secret", type: "secret", description: "Segredo para validar eventos de compra" },
    ],
  },
  {
    id: "cademi",
    name: "Cademi",
    icon: "school",
    description: "Plataforma LMS de cursos",
    fields: [
      { key: "cademi_api_url", label: "API URL", type: "url", placeholder: "https://api.cademi.com.br" },
      { key: "cademi_api_key", label: "API Key", type: "secret" },
      { key: "cademi_max_retries", label: "Máx. Tentativas", type: "number", placeholder: "3" },
      { key: "cademi_retry_base_seconds", label: "Base de Retry (s)", type: "number", placeholder: "1.0" },
    ],
  },
  {
    id: "openai",
    name: "OpenAI",
    icon: "psychology",
    description: "Modelo de linguagem e embeddings",
    fields: [
      { key: "openai_api_key", label: "API Key", type: "secret", description: "Chave sk-proj-..." },
    ],
  },
  {
    id: "meta",
    name: "Meta / WhatsApp",
    icon: "phone_iphone",
    description: "API oficial do WhatsApp Business",
    fields: [
      { key: "meta_api_key", label: "API Key", type: "secret", description: "Token de acesso à Meta Graph API" },
      { key: "meta_waba_id", label: "WABA ID", type: "text", description: "ID da conta WhatsApp Business (ex: 123456789)" },
      { key: "meta_app_id", label: "App ID", type: "text", description: "ID do App Meta (necessário para upload de mídia em templates)" },
    ],
  },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function isConfigured(value: string | number): boolean {
  const str = String(value);
  if (str === "" || str === "0") return false;
  // Valor mascarado ("xxxxx****") indica que está cadastrado mas oculto.
  return str.includes("****") || !str.startsWith("****");
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface FieldRowProps {
  field: FieldConfig;
  currentValue: string | number;
  isEditing: boolean;
  editValue: string;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onChange: (value: string | number) => void;
}

function FieldRow({ field, currentValue, isEditing, editValue, onStartEdit, onCancelEdit, onChange }: FieldRowProps) {
  const configured = isConfigured(currentValue);
  const isSecret = field.type === "secret";
  const isNumber = field.type === "number";

  return (
    <div className="group px-5 py-3.5 transition-colors hover:bg-surface-container-high/40">
      <div className="flex items-center gap-4">
        {/* Status dot */}
        <span
          className={[
            "mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full transition-colors",
            configured ? "bg-green-400" : "bg-on-surface-variant/30",
          ].join(" ")}
        />

        {/* Label + description */}
        <div className="min-w-0 flex-1">
          <span className="text-body-sm font-medium text-on-surface">{field.label}</span>
          {field.description && (
            <p className="mt-0.5 text-xs text-on-surface-variant">{field.description}</p>
          )}
        </div>

        {/* Value / Input */}
        {isEditing ? (
          <div className="flex shrink-0 items-center gap-2">
            <input
              type={isSecret ? "password" : isNumber ? "number" : "text"}
              step={field.key === "cademi_retry_base_seconds" ? "0.1" : undefined}
              value={editValue}
              onChange={(e) => onChange(isNumber ? Number(e.target.value) : e.target.value)}
              placeholder={isSecret ? "Novo valor" : field.placeholder}
              className="w-52 rounded-lg border border-primary bg-surface-container px-3 py-1.5 text-body-sm text-on-surface ring-2 ring-primary/20 placeholder:text-on-surface-variant/40 focus:outline-none"
              autoFocus
            />
            <button
              type="button"
              onClick={onCancelEdit}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface"
              aria-label="Cancelar"
            >
              <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>close</span>
            </button>
          </div>
        ) : (
          <div className="flex shrink-0 items-center gap-3">
            <span className="max-w-[180px] truncate rounded-md bg-surface-container px-2.5 py-1 font-mono text-xs text-on-surface-variant">
              {isNumber ? String(currentValue) : (String(currentValue) || "—")}
            </span>
            <button
              type="button"
              onClick={onStartEdit}
              className="flex h-8 items-center gap-1.5 rounded-lg border border-outline-variant px-2.5 text-xs font-medium text-on-surface-variant opacity-0 transition-all group-hover:opacity-100 hover:border-primary/40 hover:text-primary"
              aria-label={`Editar ${field.label}`}
            >
              <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>edit</span>
              Editar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

interface ServiceCardProps {
  service: ServiceGroup;
  settings: AccountSettings;
  editing: Set<keyof AccountSettings>;
  values: Partial<AccountSettings>;
  onStartEdit: (key: keyof AccountSettings) => void;
  onCancelEdit: (key: keyof AccountSettings) => void;
  onChange: (key: keyof AccountSettings, value: string | number) => void;
}

function ServiceCard({ service, settings, editing, values, onStartEdit, onCancelEdit, onChange }: ServiceCardProps) {
  const configuredCount = service.fields.filter((f) => isConfigured(settings[f.key])).length;
  const allConfigured = configuredCount === service.fields.length;

  return (
    <div className="overflow-hidden rounded-2xl border border-outline-variant bg-surface-container-low transition-shadow hover:shadow-sm">
      {/* Card header */}
      <div className="flex items-center justify-between border-b border-outline-variant/60 bg-surface-container px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-container">
            <span className="material-symbols-outlined text-on-primary-container" style={{ fontSize: "20px", fontVariationSettings: "'FILL' 1" }}>
              {service.icon}
            </span>
          </div>
          <div>
            <p className="text-body-sm font-semibold text-on-surface">{service.name}</p>
            <p className="text-xs text-on-surface-variant">{service.description}</p>
          </div>
        </div>
        <div className={[
          "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
          allConfigured
            ? "bg-green-400/10 text-green-500 dark:text-green-400"
            : "bg-surface-container-high text-on-surface-variant",
        ].join(" ")}>
          <span className={["h-1.5 w-1.5 rounded-full", allConfigured ? "bg-green-400" : "bg-on-surface-variant/40"].join(" ")} />
          {configuredCount}/{service.fields.length}
        </div>
      </div>

      {/* Fields */}
      <div className="divide-y divide-outline-variant/40">
        {service.fields.map((field) => (
          <FieldRow
            key={field.key}
            field={field}
            currentValue={settings[field.key]}
            isEditing={editing.has(field.key)}
            editValue={String(values[field.key] ?? "")}
            onStartEdit={() => onStartEdit(field.key)}
            onCancelEdit={() => onCancelEdit(field.key)}
            onChange={(val) => onChange(field.key, val)}
          />
        ))}
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  initial: AccountSettings;
  onSaved: (updated: AccountSettings) => void;
}

export function IntegrationSection({ initial, onSaved }: Props) {
  const { editing, values, saving, hasChanges, startEdit, cancelEdit, setValue, discard, save } =
    useIntegrationForm(onSaved);

  return (
    <section>
      {/* Section header */}
      <div className="mb-4 flex items-center gap-3">
        <div className="h-5 w-1 rounded-full bg-primary" />
        <div>
          <h2 className="text-h2 font-sans font-semibold text-on-surface">Integrações</h2>
          <p className="mt-0.5 text-body-sm text-on-surface-variant">
            Credenciais de acesso aos serviços externos. Campos sensíveis são exibidos mascarados.
          </p>
        </div>
      </div>

      {/* Service cards grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {SERVICES.map((service) => (
          <ServiceCard
            key={service.id}
            service={service}
            settings={initial}
            editing={editing}
            values={values}
            onStartEdit={startEdit}
            onCancelEdit={cancelEdit}
            onChange={setValue}
          />
        ))}
      </div>

      {/* Save bar */}
      {hasChanges && (
        <div className="mt-4 flex items-center justify-between rounded-2xl border border-primary/20 bg-primary-container px-5 py-3">
          <p className="text-body-sm text-on-primary-container">
            {Object.keys(values).length} campo{Object.keys(values).length > 1 ? "s" : ""} com alteração pendente
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={discard}
              className="rounded-xl px-4 py-2 text-body-sm text-on-surface-variant transition-colors hover:bg-surface-container"
            >
              Descartar
            </button>
            <button
              type="button"
              onClick={save}
              disabled={saving}
              className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2 text-body-sm font-semibold text-on-primary transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {saving ? (
                <span className="material-symbols-outlined animate-spin" style={{ fontSize: "16px" }}>progress_activity</span>
              ) : (
                <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>save</span>
              )}
              {saving ? "Salvando…" : "Salvar alterações"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
