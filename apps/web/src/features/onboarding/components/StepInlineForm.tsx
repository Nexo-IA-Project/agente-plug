"use client";

import { useEffect, useState } from "react";
import { listMetaTemplates } from "@/lib/api";
import { Collapse } from "@/shared/components/Collapse";
import type { MetaTemplate } from "@/features/templates/types";
import type {
  CreateStepInput,
  OnboardingStep,
  StepVariableBinding,
  UpdateStepInput,
} from "../types";
import { useMetaTemplateDetail } from "../hooks/useMetaTemplateDetail";
import { StepVariableEditor } from "./StepVariableEditor";
import { IPhonePreview } from "@/features/templates/components/IPhonePreview";
import { TimeInputGroup } from "./TimeInputGroup";

type StepMode = "template" | "text";

interface Props {
  step?: OnboardingStep;
  /** Mantido para compatibilidade com StepList; não é mais usado no form (server resolve posição). */
  nextPosition?: number;
  isFirstStep: boolean;
  defaultDelayMinutes: number;
  onSave: (dto: CreateStepInput | UpdateStepInput) => Promise<void>;
  onCancel: () => void;
}

function getTemplateBody(template: MetaTemplate | undefined): string | null {
  if (!template) return null;
  return template.components.find((c) => c.type === "BODY")?.text ?? null;
}

const inputCls = "field-input";
const labelCls = "field-label";

const EXIT_DURATION_MS = 320;

export function StepInlineForm({
  step,
  isFirstStep,
  defaultDelayMinutes,
  onSave,
  onCancel,
}: Props) {
  // Fade in/out controlado: visible começa false, vira true no mount.
  // Ao cancelar/salvar, exiting vira true e esperamos EXIT_DURATION_MS antes
  // de chamar o callback do pai (que vai unmontar o componente).
  const [visible, setVisible] = useState(false);
  const [exiting, setExiting] = useState(false);
  useEffect(() => {
    const raf = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  const handleCancelClick = () => {
    if (exiting) return;
    setExiting(true);
    setTimeout(onCancel, EXIT_DURATION_MS);
  };

  const [mode, setMode] = useState<StepMode>(
    step ? (step.message_text ? "text" : "template") : "template"
  );
  const [totalMinutes, setTotalMinutes] = useState<number>(
    step?.delay_from_previous_minutes ?? defaultDelayMinutes,
  );

  const [templates, setTemplates] = useState<MetaTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(step?.meta_template_name ?? "");
  const [templateVariables, setTemplateVariables] = useState<
    Record<string, StepVariableBinding>
  >(step?.template_variables ?? {});
  const [messageText, setMessageText] = useState(step?.message_text ?? "");
  const [saving, setSaving] = useState(false);

  const { template: detailedTemplate } = useMetaTemplateDetail(
    selectedTemplate || null,
  );

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
  const templateBody = getTemplateBody(currentTemplate);

  function onTemplateChange(name: string) {
    if (
      name !== selectedTemplate &&
      Object.keys(templateVariables).length > 0 &&
      !confirm("Trocar de template vai apagar as variáveis configuradas. Continuar?")
    ) {
      return;
    }
    setSelectedTemplate(name);
    setTemplateVariables({});
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      if (mode === "template") {
        const dto: UpdateStepInput = {
          delay_from_previous_minutes: totalMinutes,
          meta_template_name: selectedTemplate || null,
          template_variables: templateVariables,
          message_text: null,
        };
        await onSave(dto);
      } else {
        const dto: UpdateStepInput = {
          delay_from_previous_minutes: totalMinutes,
          meta_template_name: null,
          template_variables: {},
          message_text: messageText,
        };
        await onSave(dto);
      }
      // Sucesso — dispara fade-out antes do pai unmontar (esperamos via Promise)
      setExiting(true);
      await new Promise<void>((resolve) => setTimeout(resolve, EXIT_DURATION_MS));
    } catch {
      setExiting(false);
    } finally {
      setSaving(false);
    }
  }

  const isOpen = visible && !exiting;

  return (
    <Collapse open={isOpen} durationMs={480}>
      <div className="border border-primary/20 bg-surface-container p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-label-sm font-semibold text-on-surface">
          {step ? "Editar step" : "Novo step"}
        </p>
        <button
          type="button"
          onClick={handleCancelClick}
          className="p-1 text-on-surface-variant transition-colors hover:bg-surface-container-high"
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
          <div className="flex border border-outline-variant">
            {(["template", "text"] as StepMode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={[
                  "flex flex-1 items-center justify-center gap-2 py-3 text-sm font-medium transition-colors",
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
          <label className={labelCls}>
            {isFirstStep
              ? "Tempo de espera após o gatilho"
              : "Tempo de espera após a mensagem anterior"}
          </label>
          <TimeInputGroup
            totalMinutes={totalMinutes}
            onChange={setTotalMinutes}
            isFirstStep={isFirstStep}
          />
        </div>

        {/* Template mode */}
        <Collapse open={mode === "template"} durationMs={420}>
          <div className="space-y-4">
            <div>
              <label className={labelCls}>Template</label>
              {loadingTemplates ? (
                <div className="flex items-center gap-2 rounded-lg border border-outline bg-surface px-3 py-3 text-sm text-on-surface-variant">
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

            {/* Preview da mensagem no celular */}
            <Collapse open={!!detailedTemplate} durationMs={380}>
              {detailedTemplate && (
                <div className="mt-3 flex justify-center rounded-lg bg-surface-container-low py-4">
                  <IPhonePreview template={detailedTemplate} />
                </div>
              )}
            </Collapse>

            <Collapse open={!!currentTemplate} durationMs={380}>
              <div className="mt-3 space-y-2">
                <label className="block text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
                  Variáveis do template
                </label>
                <StepVariableEditor
                  templateBody={templateBody}
                  bindings={templateVariables}
                  onChange={setTemplateVariables}
                />
              </div>
            </Collapse>
          </div>
        </Collapse>

        {/* Text mode */}
        <Collapse open={mode === "text"} durationMs={420}>
          <div>
            <label className={labelCls}>Mensagem</label>
            <textarea
              value={messageText}
              onChange={(e) => setMessageText(e.target.value)}
              required={mode === "text"}
              rows={4}
              placeholder="Digite a mensagem que será enviada..."
              className="field-textarea"
            />
          </div>
        </Collapse>

        {/* Ações */}
        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={handleCancelClick}
            className="flex-1 border border-outline-variant bg-surface py-3 text-sm font-medium text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={saving}
            className="flex flex-1 items-center justify-center gap-2 bg-primary py-3 text-sm font-semibold text-on-primary transition-colors hover:bg-primary/90 disabled:opacity-50"
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
    </Collapse>
  );
}
