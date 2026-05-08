"use client";

import type { FollowupFlow } from "../types";

interface Props {
  flow: FollowupFlow;
  stepCount: number;
  position: number;
  onEdit: () => void;
  onToggle: () => void;
  onDelete: () => void;
}

export function FlowCard({ flow, stepCount, position, onEdit, onToggle, onDelete }: Props) {
  return (
    <div
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

      {/* Posição */}
      <span className="w-6 shrink-0 text-center font-mono text-label-sm text-on-surface-variant/50">
        {position}
      </span>

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
        </div>
        <div className="mt-0.5 flex items-center gap-3 text-label-sm text-on-surface-variant">
          <span className="flex items-center gap-1">
            <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
              bolt
            </span>
            {stepCount} step{stepCount !== 1 ? "s" : ""}
          </span>
          {flow.product_tags.length > 0 && (
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
                label
              </span>
              {flow.product_tags.join(", ")}
            </span>
          )}
        </div>
      </div>

      {/* Ações */}
      <div className="flex shrink-0 items-center gap-1">
        <button
          onClick={onEdit}
          className="flex items-center gap-1.5 rounded-lg bg-primary/10 px-3 py-1.5 text-label-sm font-medium text-primary transition-colors hover:bg-primary/20"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "15px" }}>
            settings
          </span>
          Configurar
        </button>
        <button
          onClick={onToggle}
          className="rounded-lg px-3 py-1.5 text-label-sm text-on-surface-variant transition-colors hover:bg-surface-container-high"
        >
          {flow.is_active ? "Pausar" : "Ativar"}
        </button>
        <button
          onClick={() => {
            if (confirm(`Excluir o flow "${flow.name}"?`)) onDelete();
          }}
          className="rounded-lg p-1.5 text-on-surface-variant/50 transition-colors hover:bg-error-container hover:text-error"
          aria-label="Excluir"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
            delete
          </span>
        </button>
      </div>
    </div>
  );
}
