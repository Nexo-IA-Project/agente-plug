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
import { StepConnector } from "./StepConnector";
import type { CreateStepInput, OnboardingStep, UpdateStepInput } from "../types";

interface Props {
  steps: OnboardingStep[];
  triggerEventType: string;
  onReorder: (items: { id: string; position: number }[]) => Promise<void>;
  onCreate: (dto: CreateStepInput) => Promise<void>;
  onUpdate: (stepId: string, dto: UpdateStepInput) => Promise<void>;
  onDelete: (stepId: string) => Promise<void>;
}

export function StepList({
  steps,
  triggerEventType,
  onReorder,
  onCreate,
  onUpdate,
  onDelete,
}: Props) {
  const toast = useToast();
  const [expandedStepId, setExpandedStepId] = useState<string | null>(null);
  const [addingAfter, setAddingAfter] = useState<boolean>(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
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

  async function handleSaveExisting(stepId: string, dto: UpdateStepInput) {
    await onUpdate(stepId, dto);
    const idx = steps.findIndex((s) => s.id === stepId);
    const next = steps[idx + 1];
    if (next) {
      setExpandedStepId(next.id);
    } else {
      setExpandedStepId(null);
      setAddingAfter(true);
    }
  }

  async function handleSaveNew(dto: CreateStepInput) {
    await onCreate(dto);
    setAddingAfter(false);
  }

  // Auto-fill: o tempo default para um NOVO card é o tempo do step imediatamente anterior.
  function defaultDelayForNew(): number {
    if (steps.length === 0) return 0;
    return steps[steps.length - 1].delay_from_previous_minutes;
  }

  return (
    <div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={steps.map((s) => s.id)} strategy={verticalListSortingStrategy}>
          {steps.map((step, index) => (
            <div key={step.id}>
              {expandedStepId === step.id ? (
                <StepInlineForm
                  step={step}
                  isFirstStep={index === 0}
                  defaultDelayMinutes={step.delay_from_previous_minutes}
                  onSave={async (dto) => {
                    await handleSaveExisting(step.id, dto as UpdateStepInput);
                  }}
                  onCancel={() => setExpandedStepId(null)}
                />
              ) : (
                <StepItem
                  step={step}
                  triggerEventType={triggerEventType}
                  isFirst={index === 0}
                  isLast={index === steps.length - 1}
                  onEdit={() => {
                    setAddingAfter(false);
                    setExpandedStepId(step.id);
                  }}
                  onDelete={() => onDelete(step.id)}
                  onMoveUp={() => void handleMoveUp(index)}
                  onMoveDown={() => void handleMoveDown(index)}
                />
              )}
              {index < steps.length - 1 && <StepConnector />}
            </div>
          ))}
        </SortableContext>
      </DndContext>

      {/* Formulário inline de novo step */}
      {addingAfter ? (
        <>
          {steps.length > 0 && <StepConnector />}
          <StepInlineForm
            isFirstStep={steps.length === 0}
            defaultDelayMinutes={defaultDelayForNew()}
            onSave={async (dto) => {
              await handleSaveNew(dto as CreateStepInput);
            }}
            onCancel={() => setAddingAfter(false)}
          />
        </>
      ) : (
        <button
          type="button"
          onClick={() => {
            setExpandedStepId(null);
            setAddingAfter(true);
          }}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-outline-variant px-4 py-3 text-label-sm text-on-surface-variant transition-colors hover:border-primary hover:text-primary"
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
