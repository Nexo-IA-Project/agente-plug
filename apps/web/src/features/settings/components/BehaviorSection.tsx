"use client";

import { useState } from "react";
import { updateAccountSettings } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import type { AccountSettings, AccountSettingsPatch } from "@/features/settings/types";

interface FieldConfig {
  key: keyof AccountSettings;
  label: string;
  description: string;
  min?: number;
  max?: number;
  step?: number;
}

const FIELDS: FieldConfig[] = [
  { key: "idle_ping_minutes", label: "Ping de inatividade (min)", description: "Minutos sem atividade para enviar ping ao contato", min: 1 },
  { key: "idle_close_minutes", label: "Fechar conversa inativa (min)", description: "Minutos sem atividade para encerrar a conversa", min: 1 },
  { key: "intent_confidence_threshold", label: "Limiar de confiança do agente", description: "Valor entre 0 e 1. Abaixo disso, o agente escala para humano", min: 0, max: 1, step: 0.05 },
  { key: "message_buffer_wait_seconds", label: "Buffer de mensagens (s)", description: "Segundos para aguardar mais mensagens antes de processar", min: 0 },
  { key: "refund_deadline_days", label: "Prazo de reembolso (dias)", description: "Dias dentro do prazo CDC para oferecer reembolso", min: 1 },
  { key: "welcome_d1_delay_hours", label: "Follow-up D+1 de boas-vindas (h)", description: "Horas após a compra para enviar o lembrete de boas-vindas", min: 1 },
  { key: "loja_express_d1_delay_hours", label: "Loja Express D+1 (h)", description: "Horas após compra para o follow-up D+1", min: 1 },
  { key: "loja_express_d3_delay_hours", label: "Loja Express D+3 (h)", description: "Horas após compra para o follow-up D+3", min: 1 },
  { key: "loja_express_d5_delay_hours", label: "Loja Express D+5 (h)", description: "Horas após compra para o follow-up D+5", min: 1 },
  { key: "loja_express_d7_delay_hours", label: "Loja Express D+7 (h)", description: "Horas após compra para o follow-up D+7 (alerta crítico)", min: 1 },
];

interface Props {
  initial: AccountSettings;
  onSaved: (updated: AccountSettings) => void;
}

export function BehaviorSection({ initial, onSaved }: Props) {
  const toast = useToast();
  const [values, setValues] = useState<Partial<AccountSettings>>({});
  const [saving, setSaving] = useState(false);

  const hasChanges = Object.keys(values).length > 0;

  function handleChange(key: keyof AccountSettings, value: number) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    if (!hasChanges) return;
    setSaving(true);
    try {
      const patch: AccountSettingsPatch = { ...values };
      const updated = await updateAccountSettings(patch);
      onSaved(updated);
      setValues({});
      toast.success("Comportamento do agente salvo com sucesso.");
    } catch {
      toast.error("Erro ao salvar configurações.");
    } finally {
      setSaving(false);
    }
  }

  function currentValue(key: keyof AccountSettings): number {
    return (values[key] as number | undefined) ?? (initial[key] as number);
  }

  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-low p-6">
      <h2 className="text-h2 font-sans font-semibold text-on-surface mb-1">Comportamento do Agente</h2>
      <p className="text-body-sm text-on-surface-variant mb-6">
        Parâmetros que controlam timeouts, limiares e intervalos de follow-up.
      </p>
      <div className="space-y-5">
        {FIELDS.map((field) => (
          <div key={field.key} className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between">
              <label className="text-label-sm font-sans text-on-surface">{field.label}</label>
              <span className="font-mono text-primary text-sm">{currentValue(field.key)}</span>
            </div>
            <input
              type="number"
              min={field.min}
              max={field.max}
              step={field.step ?? 1}
              value={currentValue(field.key)}
              onChange={(e) => handleChange(field.key, Number(e.target.value))}
              className="w-full rounded-lg border border-outline bg-surface-container px-3 py-2 text-body-sm text-on-surface focus:border-primary focus:outline-none"
            />
            <p className="text-xs text-on-surface-variant">{field.description}</p>
          </div>
        ))}
      </div>
      <div className="mt-6 flex justify-end">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !hasChanges}
          className="flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-label-sm font-sans font-semibold text-on-primary hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {saving ? (
            <><span className="material-symbols-outlined animate-spin" style={{ fontSize: "16px" }}>progress_activity</span>Salvando...</>
          ) : (
            <><span className="material-symbols-outlined" style={{ fontSize: "16px" }}>save</span>Salvar Comportamento</>
          )}
        </button>
      </div>
    </div>
  );
}
