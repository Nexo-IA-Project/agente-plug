"use client";

import { useState } from "react";
import type { CreateFlowDto, FollowupFlow, UpdateFlowDto } from "../types";

interface Props {
  flow?: FollowupFlow;
  onSave: (dto: CreateFlowDto | UpdateFlowDto) => Promise<void>;
  onClose: () => void;
}

export function FlowFormModal({ flow, onSave, onClose }: Props) {
  const [name, setName] = useState(flow?.name ?? "");
  const [tagsRaw, setTagsRaw] = useState((flow?.product_tags ?? []).join(", "));
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const product_tags = tagsRaw
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      await onSave({ name, product_tags });
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-scrim/60">
      <div className="w-full max-w-md rounded-2xl bg-surface-container-low p-6 shadow-xl">
        <h2 className="mb-4 text-title-md font-semibold text-on-surface">
          {flow ? "Editar Flow" : "Novo Flow"}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-label-sm text-on-surface-variant mb-1">Nome</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="ex: Máquina de Vendas"
            />
          </div>
          <div>
            <label className="block text-label-sm text-on-surface-variant mb-1">
              Tags de produto (separadas por vírgula)
            </label>
            <input
              value={tagsRaw}
              onChange={(e) => setTagsRaw(e.target.value)}
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="ex: maquina_de_vendas, mv_curso"
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
