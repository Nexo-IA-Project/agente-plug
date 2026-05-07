"use client";

import { useState } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { StepItem } from "./StepItem";
import { StepFormModal } from "./StepFormModal";
import type { CreateStepDto, FollowupStep, UpdateStepDto } from "../types";

interface Props {
  steps: FollowupStep[];
  onReorder: (items: { id: string; position: number }[]) => Promise<void>;
  onCreate: (dto: CreateStepDto) => Promise<void>;
  onUpdate: (stepId: string, dto: UpdateStepDto) => Promise<void>;
  onDelete: (stepId: string) => Promise<void>;
}

export function StepList({ steps, onReorder, onCreate, onUpdate, onDelete }: Props) {
  const [editingStep, setEditingStep] = useState<FollowupStep | null>(null);
  const [addingStep, setAddingStep] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = steps.findIndex((s) => s.id === active.id);
    const newIndex = steps.findIndex((s) => s.id === over.id);
    const reordered = arrayMove(steps, oldIndex, newIndex);
    const items = reordered.map((s, i) => ({ id: s.id, position: i + 1 }));
    await onReorder(items);
  }

  return (
    <div className="space-y-2">
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={steps.map((s) => s.id)} strategy={verticalListSortingStrategy}>
          {steps.map((step) => (
            <StepItem
              key={step.id}
              step={step}
              onEdit={() => setEditingStep(step)}
              onDelete={() => onDelete(step.id)}
            />
          ))}
        </SortableContext>
      </DndContext>

      <button
        onClick={() => setAddingStep(true)}
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-outline-variant px-4 py-3 text-label-md text-on-surface-variant hover:border-primary hover:text-primary"
      >
        <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
          add
        </span>
        Adicionar Step
      </button>

      {addingStep && (
        <StepFormModal
          nextPosition={steps.length + 1}
          onSave={async (dto) => {
            await onCreate(dto as CreateStepDto);
          }}
          onClose={() => setAddingStep(false)}
        />
      )}

      {editingStep && (
        <StepFormModal
          step={editingStep}
          nextPosition={editingStep.position}
          onSave={async (dto) => {
            await onUpdate(editingStep.id, dto as UpdateStepDto);
          }}
          onClose={() => setEditingStep(null)}
        />
      )}
    </div>
  );
}
