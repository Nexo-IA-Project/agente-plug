"use client";

import { useState } from "react";
import type { CreateStepDto, FollowupStep, UpdateStepDto } from "../types";

interface Props {
  step?: FollowupStep;
  nextPosition: number;
  onSave: (dto: CreateStepDto | UpdateStepDto) => Promise<void>;
  onClose: () => void;
}

export function StepFormModal({ step, nextPosition, onSave, onClose }: Props) {
  const [delay, setDelay] = useState(step?.delay_from_purchase_hours ?? 0);
  const [templateName, setTemplateName] = useState(step?.meta_template_name ?? "");
  const [position, setPosition] = useState(step?.position ?? nextPosition);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave({
        position,
        delay_from_purchase_hours: delay,
        meta_template_name: templateName,
        template_variables: step?.template_variables ?? {},
      });
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-scrim/60">
      <div className="w-full max-w-md rounded-2xl bg-surface-container-low p-6 shadow-xl">
        <h2 className="mb-4 text-title-md font-semibold text-on-surface">
          {step ? "Editar Step" : "Novo Step"}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-label-sm text-on-surface-variant mb-1">
              Nome do template Meta
            </label>
            <input
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              required
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="ex: mv_boas_vindas"
            />
          </div>
          <div>
            <label className="block text-label-sm text-on-surface-variant mb-1">
              Delay após a compra (horas)
            </label>
            <input
              type="number"
              min={0}
              value={delay}
              onChange={(e) => setDelay(Number(e.target.value))}
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <p className="mt-1 text-label-sm text-on-surface-variant">
              0h = imediato, 24h = dia 1, 48h = dia 2...
            </p>
          </div>
          <div>
            <label className="block text-label-sm text-on-surface-variant mb-1">Posição</label>
            <input
              type="number"
              min={1}
              value={position}
              onChange={(e) => setPosition(Number(e.target.value))}
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-label-md text-on-surface-variant hover:bg-surface-container-high"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-primary px-4 py-2 text-label-md font-semibold text-on-primary disabled:opacity-50"
            >
              {saving ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
