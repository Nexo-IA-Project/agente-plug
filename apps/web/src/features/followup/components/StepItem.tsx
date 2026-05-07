"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { DelayBadge } from "./DelayBadge";
import type { FollowupStep } from "../types";

interface Props {
  step: FollowupStep;
  onEdit: () => void;
  onDelete: () => Promise<void>;
}

export function StepItem({ step, onEdit, onDelete }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: step.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-3 rounded-xl border border-outline-variant bg-surface-container-low px-4 py-3"
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab text-on-surface-variant hover:text-on-surface"
        aria-label="Arrastar"
      >
        <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>
          drag_indicator
        </span>
      </button>
      <span className="w-6 text-center text-label-sm font-mono text-on-surface-variant">
        {step.position}
      </span>
      <DelayBadge hours={step.delay_from_purchase_hours} />
      <span className="flex-1 text-body-sm font-mono text-on-surface">
        {step.meta_template_name}
      </span>
      <div className="flex gap-2">
        <button
          onClick={onEdit}
          className="rounded-lg p-1.5 text-on-surface-variant hover:bg-surface-container-high"
          aria-label="Editar step"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
            edit
          </span>
        </button>
        <button
          onClick={() => {
            if (confirm("Excluir este step?")) void onDelete();
          }}
          className="rounded-lg p-1.5 text-error hover:bg-error-container"
          aria-label="Excluir step"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
            delete
          </span>
        </button>
      </div>
    </div>
  );
}
