"use client";

import { useEffect, useState } from "react";
import { listMetaTemplates } from "@/lib/api";
import type { MetaTemplate, TemplateComponent } from "@/features/templates/types";
import type { CreateStepDto, FollowupStep, UpdateStepDto } from "../types";

type StepMode = "template" | "text";
type DelayUnit = "minutos" | "horas" | "dias";

interface Props {
  step?: FollowupStep;
  nextPosition: number;
  onSave: (dto: CreateStepDto | UpdateStepDto) => Promise<void>;
  onCancel: () => void;
}

const LEAD_FIELDS = [
  { label: "Nome do contato", value: "{{contact.name}}" },
  { label: "Telefone", value: "{{contact.phone}}" },
  { label: "E-mail", value: "{{contact.email}}" },
];

function extractVariables(components: TemplateComponent[]): string[] {
  const body = components.find((c) => c.type === "BODY");
  if (!body?.text) return [];
  const matches = [...body.text.matchAll(/\{\{(\d+)\}\}/g)];
  return [...new Set(matches.map((m) => m[1]))].sort((a, b) => Number(a) - Number(b));
}

function hoursToDisplay(hours: number): { value: number; unit: DelayUnit } {
  if (hours === 0) return { value: 0, unit: "horas" };
  if (hours % 24 === 0) return { value: hours / 24, unit: "dias" };
  if (hours < 1) return { value: Math.round(hours * 60), unit: "minutos" };
  return { value: hours, unit: "horas" };
}

function toHours(value: number, unit: DelayUnit): number {
  if (unit === "minutos") return value / 60;
  if (unit === "horas") return value;
  return value * 24;
}

const inputCls =
  "w-full rounded-xl border border-outline bg-surface px-3 py-2.5 text-sm text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:ring-2 focus:ring-primary transition-shadow";
const labelCls = "mb-1.5 block text-label-sm font-medium text-on-surface-variant";

export function StepInlineForm({ step, nextPosition, onSave, onCancel }: Props) {
  // Fade in ao montar
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const raf = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  const initialDisplay = hoursToDisplay(step?.delay_from_purchase_hours ?? 0);
  const [mode, setMode] = useState<StepMode>(
    step ? (step.message_text ? "text" : "template") : "template"
  );
  const [delayValue, setDelayValue] = useState(initialDisplay.value);
  const [delayUnit, setDelayUnit] = useState<DelayUnit>(initialDisplay.unit);
  const [position, setPosition] = useState(step?.position ?? nextPosition);

  const [templates, setTemplates] = useState<MetaTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(step?.meta_template_name ?? "");
  const [variables, setVariables] = useState<Record<string, string>>(
    step?.template_variables ?? {}
  );
  const [varLeadMode, setVarLeadMode] = useState<Record<string, boolean>>({});
  const [messageText, setMessageText] = useState(step?.message_text ?? "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (mode === "template") {
      setLoadingTemplates(true);
      listMetaTemplates()
        .then(setTemplates)
        .catch(() => {})
        .finally(() => setLoadingTemplates(false));
    }
  }, [mode]);

  const currentTemplate = templates.find((t) => t.name === selectedTemplate);
  const templateVars = currentTemplate ? extractVariables(currentTemplate.components) : [];

  function onTemplateChange(name: string) {
    setSelectedTemplate(name);
    setVariables({});
    setVarLeadMode({});
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    const hours = toHours(delayValue, delayUnit);
    try {
      if (mode === "template") {
        await onSave({
          position,
          delay_from_purchase_hours: hours,
          meta_template_name: selectedTemplate || null,
          template_variables: variables,
          message_text: null,
        });
      } else {
        await onSave({
          position,
          delay_from_purchase_hours: hours,
          meta_template_name: null,
          template_variables: {},
          message_text: messageText,
        });
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="rounded-2xl border border-primary/20 bg-surface-container p-5 shadow-sm"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(10px)",
        transition: "opacity 320ms ease, transform 320ms ease",
      }}
    >
      <div className="mb-4 flex items-center justify-between">
        <p className="text-label-sm font-semibold text-on-surface">
          {step ? "Editar step" : "Novo step"}
        </p>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg p-1 text-on-surface-variant hover:bg-surface-container-high"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
            close
          </span>
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Tipo de mensagem */}
        <div>
          <label className={labelCls}>Tipo de mensagem</label>
          <div className="flex overflow-hidden rounded-xl border border-outline-variant">
            {(["template", "text"] as StepMode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={[
                  "flex flex-1 items-center justify-center gap-2 py-2.5 text-sm font-medium transition-colors",
                  mode === m
                    ? "bg-primary text-on-primary"
                    : "bg-surface text-on-surface-variant hover:bg-surface-container",
                ].join(" ")}
              >
                <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                  {m === "template" ? "receipt_long" : "chat"}
                </span>
                {m === "template" ? "Template Meta" : "Texto livre"}
              </button>
            ))}
          </div>
        </div>

        {/* Timing */}
        <div>
          <label className={labelCls}>Enviar após a compra</label>
          <div className="flex gap-2">
            <input
              type="number"
              min={0}
              value={delayValue}
              onChange={(e) => setDelayValue(Number(e.target.value))}
              className="w-24 rounded-xl border border-outline bg-surface px-3 py-2.5 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <select
              value={delayUnit}
              onChange={(e) => setDelayUnit(e.target.value as DelayUnit)}
              className="flex-1 rounded-xl border border-outline bg-surface px-3 py-2.5 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="minutos">Minutos</option>
              <option value="horas">Horas</option>
              <option value="dias">Dias</option>
            </select>
          </div>
          <p className="mt-1 text-xs text-on-surface-variant">
            {delayValue === 0 && delayUnit === "horas"
              ? "Imediato — dispara assim que a compra é registrada"
              : `${toHours(delayValue, delayUnit)} hora(s) após a compra`}
          </p>
        </div>

        {/* Posição */}
        <div>
          <label className={labelCls}>Posição na sequência</label>
          <input
            type="number"
            min={1}
            value={position}
            onChange={(e) => setPosition(Number(e.target.value))}
            className={inputCls}
          />
        </div>

        {/* Template mode */}
        {mode === "template" && (
          <div className="space-y-4">
            <div>
              <label className={labelCls}>Template</label>
              {loadingTemplates ? (
                <div className="flex items-center gap-2 rounded-xl border border-outline bg-surface px-3 py-2.5 text-sm text-on-surface-variant">
                  <span
                    className="material-symbols-outlined animate-spin"
                    style={{ fontSize: "16px" }}
                  >
                    progress_activity
                  </span>
                  Carregando templates...
                </div>
              ) : (
                <select
                  value={selectedTemplate}
                  onChange={(e) => onTemplateChange(e.target.value)}
                  className={inputCls}
                >
                  <option value="">— Selecionar template —</option>
                  {templates
                    .filter((t) => t.status === "APPROVED")
                    .map((t) => (
                      <option key={t.id} value={t.name}>
                        {t.name}
                      </option>
                    ))}
                </select>
              )}
            </div>

            {currentTemplate && (
              <div className="rounded-xl border border-outline-variant bg-surface-container-high p-3 text-xs text-on-surface-variant">
                {currentTemplate.components.find((c) => c.type === "BODY")?.text ?? ""}
              </div>
            )}

            {templateVars.length > 0 && (
              <div className="space-y-3">
                <label className="block text-label-sm font-medium text-on-surface">
                  Variáveis do template
                </label>
                {templateVars.map((varN) => (
                  <div key={varN}>
                    <div className="mb-1.5 flex items-center justify-between">
                      <span className="rounded bg-surface-container px-1.5 py-0.5 font-mono text-xs text-primary">
                        {`{{${varN}}}`}
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          setVarLeadMode((m) => ({ ...m, [varN]: !m[varN] }))
                        }
                        className="text-xs text-on-surface-variant underline-offset-2 hover:text-primary hover:underline"
                      >
                        {varLeadMode[varN] ? "Digitar valor" : "Usar campo do lead"}
                      </button>
                    </div>
                    {varLeadMode[varN] ? (
                      <select
                        value={variables[varN] ?? ""}
                        onChange={(e) =>
                          setVariables((v) => ({ ...v, [varN]: e.target.value }))
                        }
                        className={inputCls}
                      >
                        <option value="">— Selecionar campo —</option>
                        {LEAD_FIELDS.map((f) => (
                          <option key={f.value} value={f.value}>
                            {f.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        value={variables[varN] ?? ""}
                        onChange={(e) =>
                          setVariables((v) => ({ ...v, [varN]: e.target.value }))
                        }
                        placeholder={`Valor para {{${varN}}}`}
                        className={inputCls}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Text mode */}
        {mode === "text" && (
          <div>
            <label className={labelCls}>Mensagem</label>
            <textarea
              value={messageText}
              onChange={(e) => setMessageText(e.target.value)}
              required={mode === "text"}
              rows={4}
              placeholder="Digite a mensagem que será enviada..."
              className={inputCls}
            />
          </div>
        )}

        {/* Ações */}
        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 rounded-xl py-2.5 text-label-sm text-on-surface-variant hover:bg-surface-container-high"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={saving}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-primary py-2.5 text-label-sm font-semibold text-on-primary disabled:opacity-50"
          >
            {saving && (
              <span
                className="material-symbols-outlined animate-spin"
                style={{ fontSize: "15px" }}
              >
                progress_activity
              </span>
            )}
            {saving ? "Salvando..." : step ? "Salvar" : "Adicionar"}
          </button>
        </div>
      </form>
    </div>
  );
}
