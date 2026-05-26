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
import { useToast } from "@/shared/hooks/useToast";
import { StepItem } from "./StepItem";
import { StepInlineForm } from "./StepInlineForm";
import type { CreateStepInput, OnboardingStep, UpdateStepInput } from "../types";

interface Props {
  steps: OnboardingStep[];
  onReorder: (items: { id: string; position: number }[]) => Promise<void>;
  onCreate: (dto: CreateStepInput) => Promise<void>;
  onUpdate: (stepId: string, dto: UpdateStepInput) => Promise<void>;
  onDelete: (stepId: string) => Promise<void>;
}

export function StepList({ steps, onReorder, onCreate, onUpdate, onDelete }: Props) {
  const toast = useToast();
  const [editingStep, setEditingStep] = useState<OnboardingStep | null>(null);
  const [addingStep, setAddingStep] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  async function reorderAndToast(reordered: OnboardingStep[]) {
    try {
      await onReorder(reordered.map((s, i) => ({ id: s.id, position: i + 1 })));
      toast.success("Ordem das mensagens atualizada");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao reordenar");
    }
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = steps.findIndex((s) => s.id === active.id);
    const newIndex = steps.findIndex((s) => s.id === over.id);
    await reorderAndToast(arrayMove(steps, oldIndex, newIndex));
  }

  async function handleMoveUp(index: number) {
    if (index === 0) return;
    const reordered = [...steps];
    [reordered[index - 1], reordered[index]] = [reordered[index], reordered[index - 1]];
    await reorderAndToast(reordered);
  }

  async function handleMoveDown(index: number) {
    if (index === steps.length - 1) return;
    const reordered = [...steps];
    [reordered[index], reordered[index + 1]] = [reordered[index + 1], reordered[index]];
    await reorderAndToast(reordered);
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
                  await onUpdate(step.id, dto as UpdateStepInput);
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
            await onCreate(dto as CreateStepInput);
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
          Adicionar mensagem
        </button>
      )}
    </div>
  );
}
