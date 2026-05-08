"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { DelayBadge } from "./DelayBadge";
import type { FollowupStep } from "../types";

interface Props {
  step: FollowupStep;
  isFirst: boolean;
  isLast: boolean;
  onEdit: () => void;
  onDelete: () => Promise<void>;
  onMoveUp: () => void;
  onMoveDown: () => void;
}

export function StepItem({ step, isFirst, isLast, onEdit, onDelete, onMoveUp, onMoveDown }: Props) {
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
      {/* Drag handle */}
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

      {/* Up/Down buttons */}
      <div className="flex flex-col gap-0.5">
        <button
          type="button"
          onClick={onMoveUp}
          disabled={isFirst}
          className="rounded p-0.5 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-30"
          aria-label="Mover para cima"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
            keyboard_arrow_up
          </span>
        </button>
        <button
          type="button"
          onClick={onMoveDown}
          disabled={isLast}
          className="rounded p-0.5 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-30"
          aria-label="Mover para baixo"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
            keyboard_arrow_down
          </span>
        </button>
      </div>

      {/* Position */}
      <span className="w-6 text-center font-mono text-label-sm text-on-surface-variant">
        {step.position}
      </span>

      {/* Delay badge */}
      <DelayBadge hours={step.delay_from_purchase_hours} />

      {/* Label */}
      <div className="min-w-0 flex-1">
        {step.meta_template_name ? (
          <div className="flex items-center gap-1.5">
            <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: "14px" }}>
              receipt_long
            </span>
            <span className="truncate font-mono text-body-sm text-on-surface">
              {step.meta_template_name}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: "14px" }}>
              chat
            </span>
            <span className="truncate text-body-sm text-on-surface-variant italic">
              {step.message_text
                ? step.message_text.length > 40
                  ? step.message_text.slice(0, 40) + "…"
                  : step.message_text
                : "Texto livre"}
            </span>
          </div>
        )}
      </div>

      {/* Actions */}
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
