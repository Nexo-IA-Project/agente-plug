"use client";

import Link from "next/link";
import { use } from "react";
import { useOnboardingSteps } from "@/features/onboarding/hooks/useOnboardingSteps";
import { StepList } from "@/features/onboarding/components/StepList";
import { useToast } from "@/shared/hooks/useToast";

export default function OnboardingFlowDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { steps, loading, error, create, update, remove, reorder } = useOnboardingSteps(id);
  const toast = useToast();

  if (loading)
    return (
      <div className="flex h-full items-center justify-center text-on-surface-variant">
        Carregando...
      </div>
    );
  if (error) return <div className="p-6 text-error">{error}</div>;

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-center gap-3">
        <Link href="/onboarding" className="text-on-surface-variant hover:text-on-surface">
          <span className="material-symbols-outlined" style={{ fontSize: "22px" }}>
            arrow_back
          </span>
        </Link>
        <h1 className="text-headline-sm font-bold text-on-surface">Steps do Flow</h1>
      </div>

      <StepList
        steps={steps}
        onReorder={async (items) => {
          try {
            await reorder(items);
            toast.success("Ordem atualizada");
          } catch {
            toast.error("Erro ao reordenar");
          }
        }}
        onCreate={async (dto) => {
          try {
            await create(dto);
            toast.success("Step adicionado");
          } catch {
            toast.error("Erro ao adicionar step");
          }
        }}
        onUpdate={async (stepId, dto) => {
          try {
            await update(stepId, dto);
            toast.success("Step atualizado");
          } catch {
            toast.error("Erro ao atualizar step");
          }
        }}
        onDelete={async (stepId) => {
          try {
            await remove(stepId);
            toast.success("Step excluído");
          } catch {
            toast.error("Erro ao excluir step");
          }
        }}
      />
    </div>
  );
}
