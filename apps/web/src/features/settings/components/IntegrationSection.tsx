"use client";

import { useState } from "react";
import { updateAccountSettings } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import type { AccountSettings, AccountSettingsPatch } from "@/features/settings/types";

interface FieldConfig {
  key: keyof AccountSettings;
  label: string;
  type: "text" | "secret" | "url" | "number";
  placeholder?: string;
}

const FIELDS: FieldConfig[] = [
  { key: "chatnexo_base_url", label: "ChatNexo URL", type: "url", placeholder: "http://..." },
  { key: "chatnexo_api_key", label: "ChatNexo API Key", type: "secret" },
  { key: "hubla_webhook_secret", label: "Hubla Webhook Secret", type: "secret" },
  { key: "cademi_api_url", label: "Cademi API URL", type: "url", placeholder: "http://..." },
  { key: "cademi_api_key", label: "Cademi API Key", type: "secret" },
  { key: "cademi_max_retries", label: "Cademi Max Retries", type: "number" },
  { key: "cademi_retry_base_seconds", label: "Cademi Retry Base (s)", type: "number" },
  { key: "openai_api_key", label: "OpenAI API Key", type: "secret" },
  { key: "meta_api_key", label: "Meta API Key", type: "secret" },
];

interface Props {
  initial: AccountSettings;
  onSaved: (updated: AccountSettings) => void;
}

export function IntegrationSection({ initial, onSaved }: Props) {
  const toast = useToast();
  const [editing, setEditing] = useState<Set<keyof AccountSettings>>(new Set());
  const [values, setValues] = useState<Partial<AccountSettings>>({});
  const [saving, setSaving] = useState(false);

  function startEdit(key: keyof AccountSettings) {
    setEditing((prev) => new Set([...prev, key]));
    setValues((prev) => ({ ...prev, [key]: "" }));
  }

  function cancelEdit(key: keyof AccountSettings) {
    setEditing((prev) => {
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
    setValues((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  function handleChange(key: keyof AccountSettings, value: string | number) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    if (Object.keys(values).length === 0) return;
    setSaving(true);
    try {
      const patch: AccountSettingsPatch = { ...values };
      const updated = await updateAccountSettings(patch);
      onSaved(updated);
      setEditing(new Set());
      setValues({});
      toast.success("Integrações salvas com sucesso.");
    } catch {
      toast.error("Erro ao salvar configurações.");
    } finally {
      setSaving(false);
    }
  }

  function displayValue(field: FieldConfig): string {
    return String(initial[field.key]);
  }

  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-low p-6">
      <h2 className="text-h2 font-sans font-semibold text-on-surface mb-1">Integrações</h2>
      <p className="text-body-sm text-on-surface-variant mb-6">
        Credenciais de acesso aos serviços externos. Campos de chave exibem valor mascarado.
      </p>
      <div className="space-y-4">
        {FIELDS.map((field) => {
          const isEditing = editing.has(field.key);
          const isSecret = field.type === "secret";
          return (
            <div key={field.key} className="flex flex-col gap-1">
              <label className="text-label-sm font-sans text-on-surface-variant">{field.label}</label>
              <div className="flex gap-2">
                {isEditing ? (
                  <>
                    <input
                      type={isSecret ? "password" : field.type === "number" ? "number" : "text"}
                      step={field.key === "cademi_retry_base_seconds" ? "0.1" : undefined}
                      value={String(values[field.key] ?? "")}
                      onChange={(e) =>
                        handleChange(field.key, field.type === "number" ? Number(e.target.value) : e.target.value)
                      }
                      placeholder={isSecret ? "Digite o novo valor" : field.placeholder}
                      className="flex-1 rounded-lg border border-outline bg-surface-container px-3 py-2 text-body-sm text-on-surface placeholder:text-on-surface-variant/50 focus:border-primary focus:outline-none"
                      autoFocus
                    />
                    <button
                      type="button"
                      onClick={() => cancelEdit(field.key)}
                      className="rounded-lg border border-outline-variant px-3 py-2 text-label-sm text-on-surface-variant hover:bg-surface-container transition-colors"
                    >
                      Cancelar
                    </button>
                  </>
                ) : (
                  <>
                    <div className="flex-1 rounded-lg border border-outline-variant bg-surface-container px-3 py-2 text-body-sm text-on-surface-variant font-mono">
                      {displayValue(field)}
                    </div>
                    <button
                      type="button"
                      onClick={() => startEdit(field.key)}
                      className="flex items-center gap-1.5 rounded-lg border border-outline-variant px-3 py-2 text-label-sm text-on-surface hover:bg-surface-container transition-colors"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>edit</span>
                      Editar
                    </button>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {editing.size > 0 && (
        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-label-sm font-sans font-semibold text-on-primary hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {saving ? (
              <><span className="material-symbols-outlined animate-spin" style={{ fontSize: "16px" }}>progress_activity</span>Salvando...</>
            ) : (
              <><span className="material-symbols-outlined" style={{ fontSize: "16px" }}>save</span>Salvar Integrações</>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
