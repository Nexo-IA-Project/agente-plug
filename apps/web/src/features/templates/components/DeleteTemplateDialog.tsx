"use client";

import { ConfirmDialog } from "@/shared/components/confirm/ConfirmDialog";
import type { MetaTemplate } from "../types";

export interface FlowUsage {
  id: string;
  name: string;
  step_position: number;
}

interface Props {
  template: MetaTemplate | null;
  conflictFlows?: FlowUsage[] | null;
  onConfirm: () => Promise<void> | void;
  onClose: () => void;
}

export function DeleteTemplateDialog({
  template,
  conflictFlows,
  onConfirm,
  onClose,
}: Props) {
  if (!template) return null;

  if (conflictFlows && conflictFlows.length > 0) {
    const flowNames = conflictFlows.map((f) => `"${f.name}" (passo ${f.step_position})`).join(", ");

    return (
      <ConfirmDialog
        open
        title="Template em uso"
        description={`Não é possível excluir "${template.name}". Ele é usado nos flows: ${flowNames}.`}
        confirmLabel="Entendi"
        cancelLabel="Fechar"
        variant="warning"
        onConfirm={onClose}
        onCancel={onClose}
      />
    );
  }

  return (
    <ConfirmDialog
      open
      title="Excluir template?"
      description={`Vamos excluir "${template.name}" da Meta, do nosso storage e do banco. Esta ação não pode ser desfeita.`}
      confirmLabel="Excluir"
      cancelLabel="Cancelar"
      variant="danger"
      onConfirm={onConfirm}
      onCancel={onClose}
    />
  );
}
