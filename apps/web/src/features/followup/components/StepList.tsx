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
import { StepInlineForm } from "./StepInlineForm";
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
    await onReorder(reordered.map((s, i) => ({ id: s.id, position: i + 1 })));
  }

  async function handleMoveUp(index: number) {
    if (index === 0) return;
    const reordered = [...steps];
    [reordered[index - 1], reordered[index]] = [reordered[index], reordered[index - 1]];
    await onReorder(reordered.map((s, i) => ({ id: s.id, position: i + 1 })));
  }

  async function handleMoveDown(index: number) {
    if (index === steps.length - 1) return;
    const reordered = [...steps];
    [reordered[index], reordered[index + 1]] = [reordered[index + 1], reordered[index]];
    await onReorder(reordered.map((s, i) => ({ id: s.id, position: i + 1 })));
  }

  return (
    <div className="space-y-2">
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={steps.map((s) => s.id)} strategy={verticalListSortingStrategy}>
          {steps.map((step, index) =>
            editingStep?.id === step.id ? (
              <StepInlineForm
                key={step.id}
                step={step}
                nextPosition={step.position}
                onSave={async (dto) => {
                  await onUpdate(step.id, dto as UpdateStepDto);
                  setEditingStep(null);
                }}
                onCancel={() => setEditingStep(null)}
              />
            ) : (
              <StepItem
                key={step.id}
                step={step}
                isFirst={index === 0}
                isLast={index === steps.length - 1}
                onEdit={() => {
                  setAddingStep(false);
                  setEditingStep(step);
                }}
                onDelete={() => onDelete(step.id)}
                onMoveUp={() => void handleMoveUp(index)}
                onMoveDown={() => void handleMoveDown(index)}
              />
            )
          )}
        </SortableContext>
      </DndContext>

      {/* Formulário inline de novo step */}
      {addingStep ? (
        <StepInlineForm
          nextPosition={steps.length + 1}
          onSave={async (dto) => {
            await onCreate(dto as CreateStepDto);
            setAddingStep(false);
          }}
          onCancel={() => setAddingStep(false)}
        />
      ) : (
        <button
          onClick={() => {
            setEditingStep(null);
            setAddingStep(true);
          }}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-outline-variant px-4 py-3 text-label-sm text-on-surface-variant transition-colors hover:border-primary hover:text-primary"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
            add
          </span>
          Adicionar Step
        </button>
      )}
    </div>
  );
}
