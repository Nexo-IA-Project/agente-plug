"use client";

import { useBehaviorForm } from "@/features/settings/hooks/useBehaviorForm";
import type { AccountSettings } from "@/features/settings/types";

// ─── Types ────────────────────────────────────────────────────────────────────

interface FieldConfig {
  key: keyof AccountSettings;
  label: string;
  description: string;
  unit: string;
  icon: string;
  min?: number;
  max?: number;
  step?: number;
}

interface ParamGroup {
  id: string;
  title: string;
  description: string;
  icon: string;
  fields: FieldConfig[];
}

// ─── Config ───────────────────────────────────────────────────────────────────

const GROUPS: ParamGroup[] = [
  {
    id: "timeouts",
    title: "Timeouts e Limiares",
    description: "Controle de inatividade e confiança do agente",
    icon: "timer",
    fields: [
      {
        key: "idle_ping_minutes",
        label: "Ping de inatividade",
        description: "Minutos sem atividade para enviar ping",
        unit: "min",
        icon: "notifications_paused",
        min: 1,
      },
      {
        key: "idle_close_minutes",
        label: "Fechar conversa inativa",
        description: "Minutos para encerrar conversa",
        unit: "min",
        icon: "cancel",
        min: 1,
      },
      {
        key: "intent_confidence_threshold",
        label: "Limiar de confiança",
        description: "Abaixo disso, escala para humano",
        unit: "",
        icon: "psychology",
        min: 0,
        max: 1,
        step: 0.05,
      },
      {
        key: "message_buffer_wait_seconds",
        label: "Buffer de mensagens",
        description: "Aguardar mais msgs antes de processar",
        unit: "s",
        icon: "hourglass_empty",
        min: 0,
      },
      {
        key: "refund_deadline_days",
        label: "Prazo de reembolso",
        description: "Dias CDC para oferecer reembolso",
        unit: "dias",
        icon: "policy",
        min: 1,
      },
      {
        key: "ai_memory_messages",
        label: "Memória da IA",
        description: "Últimas N mensagens usadas como contexto (5–100)",
        unit: "msgs",
        icon: "memory",
        min: 5,
        max: 100,
      },
    ],
  },
  {
    id: "followups",
    title: "Follow-ups de Jornada",
    description: "Intervalos de envio de mensagens pós-compra",
    icon: "route",
    fields: [
      {
        key: "welcome_d1_delay_hours",
        label: "Boas-vindas D+1",
        description: "Horas após compra para lembrete inicial",
        unit: "h",
        icon: "waving_hand",
        min: 1,
      },
      {
        key: "loja_express_d1_delay_hours",
        label: "Loja Express D+1",
        description: "Follow-up no primeiro dia",
        unit: "h",
        icon: "looks_one",
        min: 1,
      },
      {
        key: "loja_express_d3_delay_hours",
        label: "Loja Express D+3",
        description: "Follow-up no terceiro dia",
        unit: "h",
        icon: "looks_3",
        min: 1,
      },
      {
        key: "loja_express_d5_delay_hours",
        label: "Loja Express D+5",
        description: "Follow-up no quinto dia",
        unit: "h",
        icon: "looks_5",
        min: 1,
      },
      {
        key: "loja_express_d7_delay_hours",
        label: "Loja Express D+7",
        description: "Alerta crítico — sétimo dia",
        unit: "h",
        icon: "warning",
        min: 1,
      },
    ],
  },
];

// ─── Sub-components ───────────────────────────────────────────────────────────

interface ParamCardProps {
  field: FieldConfig;
  value: number;
  onChange: (key: keyof AccountSettings, value: number) => void;
  isDirty: boolean;
}

function ParamCard({ field, value, onChange, isDirty }: ParamCardProps) {
  return (
    <div
      className={[
        "flex flex-col gap-3 rounded-2xl border p-4 transition-all",
        isDirty
          ? "border-primary/40 bg-primary-container/30 shadow-sm"
          : "border-outline-variant bg-surface-container-low hover:border-outline hover:bg-surface-container",
      ].join(" ")}
    >
      {/* Icon + label row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={["material-symbols-outlined", isDirty ? "text-primary" : "text-on-surface-variant"].join(" ")}
            style={{ fontSize: "18px", fontVariationSettings: "'FILL' 1" }}
          >
            {field.icon}
          </span>
          <span className="text-xs font-medium text-on-surface">{field.label}</span>
        </div>
        {/* Current value chip */}
        <span className={["rounded-lg px-2 py-0.5 font-mono text-sm font-semibold", isDirty ? "text-primary" : "text-on-surface"].join(" ")}>
          {field.step && field.step < 1 ? value.toFixed(2) : value}
          {field.unit && <span className="ml-0.5 text-xs font-normal text-on-surface-variant">{field.unit}</span>}
        </span>
      </div>

      {/* Input */}
      <input
        type="number"
        min={field.min}
        max={field.max}
        step={field.step ?? 1}
        value={value}
        onChange={(e) => onChange(field.key, Number(e.target.value))}
        className={[
          "w-full rounded-xl border px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2",
          isDirty
            ? "border-primary/40 bg-surface-container ring-primary/20"
            : "border-outline-variant bg-surface-container focus:border-primary focus:ring-primary/20",
        ].join(" ")}
      />

      {/* Description */}
      <p className="text-xs leading-relaxed text-on-surface-variant">{field.description}</p>
    </div>
  );
}

interface GroupCardProps {
  group: ParamGroup;
  settings: AccountSettings;
  values: Partial<AccountSettings>;
  onChange: (key: keyof AccountSettings, value: number) => void;
}

function GroupCard({ group, settings, values, onChange }: GroupCardProps) {
  const dirtyCount = group.fields.filter((f) => f.key in values).length;

  return (
    <div className="overflow-hidden rounded-2xl border border-outline-variant bg-surface-container-low">
      {/* Group header */}
      <div className="flex items-center justify-between border-b border-outline-variant/60 bg-surface-container px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-container">
            <span
              className="material-symbols-outlined text-on-primary-container"
              style={{ fontSize: "20px", fontVariationSettings: "'FILL' 1" }}
            >
              {group.icon}
            </span>
          </div>
          <div>
            <p className="text-body-sm font-semibold text-on-surface">{group.title}</p>
            <p className="text-xs text-on-surface-variant">{group.description}</p>
          </div>
        </div>
        {dirtyCount > 0 && (
          <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
            {dirtyCount} alterado{dirtyCount > 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Param grid */}
      <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
        {group.fields.map((field) => (
          <ParamCard
            key={field.key}
            field={field}
            value={(values[field.key] as number | undefined) ?? (settings[field.key] as number)}
            onChange={onChange}
            isDirty={field.key in values}
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

export function BehaviorSection({ initial, onSaved }: Props) {
  const { values, saving, hasChanges, setValue, discard, save } = useBehaviorForm(onSaved);

  return (
    <section>
      {/* Section header */}
      <div className="mb-4 flex items-center gap-3">
        <div className="h-5 w-1 rounded-full bg-secondary" />
        <div>
          <h2 className="text-h2 font-sans font-semibold text-on-surface">Comportamento do Agente</h2>
          <p className="mt-0.5 text-body-sm text-on-surface-variant">
            Parâmetros que controlam timeouts, limiares de decisão e intervalos de follow-up.
          </p>
        </div>
      </div>

      {/* Groups */}
      <div className="flex flex-col gap-4">
        {GROUPS.map((group) => (
          <GroupCard
            key={group.id}
            group={group}
            settings={initial}
            values={values}
            onChange={setValue}
          />
        ))}
      </div>

      {/* Save bar */}
      {hasChanges && (
        <div className="mt-4 flex items-center justify-between rounded-2xl border border-secondary/20 bg-secondary-container px-5 py-3">
          <p className="text-body-sm text-on-surface">
            {Object.keys(values).length} parâmetro{Object.keys(values).length > 1 ? "s" : ""} com alteração pendente
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
              {saving ? "Salvando…" : "Salvar parâmetros"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
