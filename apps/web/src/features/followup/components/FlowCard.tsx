"use client";

import Link from "next/link";
import type { FollowupFlow, UpdateFlowDto } from "../types";

interface Props {
  flow: FollowupFlow;
  onEdit: () => void;
  onToggle: (dto: UpdateFlowDto) => Promise<void>;
  onDelete: () => Promise<void>;
}

export function FlowCard({ flow, onEdit, onToggle, onDelete }: Props) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-outline-variant bg-surface-container-low px-5 py-4">
      <div className="flex items-center gap-3">
        <span
          className={`h-2.5 w-2.5 rounded-full ${flow.is_active ? "bg-success" : "bg-on-surface-variant"}`}
        />
        <div>
          <Link
            href={`/followup/${flow.id}`}
            className="text-body-md font-semibold text-on-surface hover:text-primary"
          >
            {flow.name}
          </Link>
          <p className="text-label-sm text-on-surface-variant">
            Tags: {flow.product_tags.join(", ") || "—"}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onEdit}
          className="rounded-lg px-3 py-1.5 text-label-sm text-on-surface-variant hover:bg-surface-container-high"
        >
          Editar
        </button>
        <button
          onClick={() => onToggle({ is_active: !flow.is_active })}
          className="rounded-lg px-3 py-1.5 text-label-sm text-on-surface-variant hover:bg-surface-container-high"
        >
          {flow.is_active ? "Pausar" : "Ativar"}
        </button>
        <button
          onClick={() => {
            if (confirm(`Excluir flow "${flow.name}"?`)) void onDelete();
          }}
          className="rounded-lg px-3 py-1.5 text-label-sm text-error hover:bg-error-container"
        >
          Excluir
        </button>
      </div>
    </div>
  );
}
