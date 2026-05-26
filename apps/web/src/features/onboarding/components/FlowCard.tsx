"use client";

import { useConfirm } from "@/shared/components/confirm/ConfirmProvider";
import { getTriggerEventMeta } from "../lib/triggerEvents";
import type { OnboardingFlow } from "../types";

interface Props {
  flow: OnboardingFlow;
  onEdit: () => void;
  onToggle: () => void;
  onDelete: () => void;
}

export function FlowCard({ flow, onEdit, onToggle, onDelete }: Props) {
  const confirm = useConfirm();

  async function handleDelete() {
    const ok = await confirm({
      title: "Excluir flow",
      description: `Tem certeza que deseja excluir o flow "${flow.name}"? Esta ação não pode ser desfeita.`,
      confirmLabel: "Excluir",
      variant: "danger",
    });
    if (ok) onDelete();
  }

  const stepsCount = flow.steps_count;
  const triggerMeta = getTriggerEventMeta(flow.trigger_event_type);

  return (
    <article
      className={`group relative flex items-center gap-4 rounded-2xl border bg-surface-container-low px-5 py-4 transition-shadow hover:shadow-md ${
        flow.is_active
          ? "border-outline-variant/60"
          : "border-outline-variant/30 opacity-70"
      }`}
    >
      {/* Status bar lateral */}
      <div
        className={`absolute left-0 top-3 bottom-3 w-[3px] rounded-r-full transition-colors ${
          flow.is_active ? "bg-success" : "bg-outline-variant"
        }`}
      />

      {/* Info principal */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-body-md font-semibold text-on-surface">{flow.name}</span>
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-label-xs font-medium ${
              flow.is_active
                ? "bg-success/10 text-success"
                : "bg-outline-variant/20 text-on-surface-variant"
            }`}
          >
            {flow.is_active ? "Ativo" : "Pausado"}
          </span>
          {triggerMeta && (
            <span
              className={[
                "ml-auto inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-label-xs font-medium",
                triggerMeta.tone.bg,
                triggerMeta.tone.border,
                triggerMeta.tone.text,
              ].join(" ")}
              title={triggerMeta.technical}
            >
              <span
                className="material-symbols-outlined"
                style={{ fontSize: "14px" }}
              >
                {triggerMeta.icon}
              </span>
              {triggerMeta.pillLabel}
            </span>
          )}
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-label-sm text-on-surface-variant">
          <span
            className="inline-flex items-center gap-1 rounded-full bg-primary-container px-2 py-0.5 text-label-xs font-medium text-on-primary-container"
            title={flow.product.hubla_id}
          >
            <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
              inventory_2
            </span>
            {flow.product.name}
          </span>
          <span className="flex items-center gap-1">
            <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
              bolt
            </span>
            {stepsCount} step{stepsCount === 1 ? "" : "s"}
          </span>
        </div>
      </div>

      {/* Ações */}
      <div className="flex shrink-0 items-center gap-1">
        <button
          onClick={onEdit}
          className="flex items-center gap-1.5 rounded-lg bg-primary/10 px-3 py-1.5 text-label-sm font-medium text-primary transition-colors hover:bg-primary/20"
          aria-label="Editar"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "15px" }}>
            settings
          </span>
          Configurar
        </button>
        <button
          onClick={onToggle}
          className="rounded-lg px-3 py-1.5 text-label-sm text-on-surface-variant transition-colors hover:bg-surface-container-high"
          aria-label="Ativar/Pausar"
        >
          {flow.is_active ? "Pausar" : "Ativar"}
        </button>
        <button
          onClick={handleDelete}
          className="rounded-lg p-1.5 text-on-surface-variant/50 transition-colors hover:bg-error-container hover:text-error"
          aria-label="Excluir"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
            delete
          </span>
        </button>
      </div>
    </article>
  );
}
