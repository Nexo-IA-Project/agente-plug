"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useConfirm } from "@/shared/components/confirm/ConfirmProvider";
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
  const confirm = useConfirm();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: step.id });

  async function handleDelete() {
    const ok = await confirm({
      title: "Excluir step",
      description: "Tem certeza que deseja excluir este step? Esta ação não pode ser desfeita.",
      confirmLabel: "Excluir",
      variant: "danger",
    });
    if (ok) await onDelete();
  }

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  const isTemplate = !!step.meta_template_name;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="group flex items-center gap-3 rounded-lg border border-outline-variant bg-surface-container-low px-4 py-3 transition-shadow hover:shadow-sm"
    >
      {/* Número do step — círculo com destaque */}
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary ring-1 ring-primary/20">
        {step.position}
      </div>

      {/* Conteúdo central */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span
            className={[
              "material-symbols-outlined",
              isTemplate ? "text-primary/70" : "text-on-surface-variant",
            ].join(" ")}
            style={{ fontSize: "14px" }}
          >
            {isTemplate ? "receipt_long" : "chat"}
          </span>
          <span
            className={[
              "truncate text-sm",
              isTemplate
                ? "font-mono font-medium text-on-surface"
                : "italic text-on-surface-variant",
            ].join(" ")}
          >
            {isTemplate
              ? step.meta_template_name
              : step.message_text
              ? step.message_text.length > 45
                ? step.message_text.slice(0, 45) + "…"
                : step.message_text
              : "Texto livre"}
          </span>
        </div>
      </div>

      {/* Delay badge */}
      <DelayBadge minutes={step.delay_from_purchase_minutes} />

      {/* Reordenar — setas + drag */}
      <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          type="button"
          onClick={onMoveUp}
          disabled={isFirst}
          className="rounded p-1 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-30"
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
          className="rounded p-1 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-30"
          aria-label="Mover para baixo"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
            keyboard_arrow_down
          </span>
        </button>
        <button
          {...attributes}
          {...listeners}
          className="cursor-grab rounded p-1 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"
          aria-label="Arrastar"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
            drag_indicator
          </span>
        </button>
      </div>

      {/* Ações */}
      <div className="flex shrink-0 gap-1">
        <button
          onClick={onEdit}
          className="rounded-md p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface"
          aria-label="Editar step"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
            edit
          </span>
        </button>
        <button
          onClick={() => void handleDelete()}
          className="rounded-md p-1.5 text-on-surface-variant transition-colors hover:bg-error-container hover:text-error"
          aria-label="Excluir step"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
            delete
          </span>
        </button>
      </div>
    </div>
  );
}
