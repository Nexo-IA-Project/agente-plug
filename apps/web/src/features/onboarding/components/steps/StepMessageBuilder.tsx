"use client";

import { StepList } from "../StepList";
import { useOnboardingSteps } from "../../hooks/useOnboardingSteps";

interface StepMessageBuilderProps {
  flowId: string;
}

export function StepMessageBuilder({ flowId }: StepMessageBuilderProps) {
  const { steps, loading, create, update, remove, reorder } =
    useOnboardingSteps(flowId);

  if (loading) {
    return (
      <div className="text-sm text-on-surface-variant">
        Carregando mensagens...
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-on-surface">
          Mensagens da sequência
        </h3>
        <p className="mt-1 text-xs text-on-surface-variant">
          Adicione as mensagens que serão enviadas após o evento gatilho.
          Arraste para reordenar.
        </p>
      </div>
      <StepList
        steps={steps}
        onCreate={create}
        onUpdate={update}
        onDelete={remove}
        onReorder={reorder}
      />
    </div>
  );
}
