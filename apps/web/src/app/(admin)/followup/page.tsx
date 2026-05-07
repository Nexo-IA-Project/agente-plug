"use client";

import { useState } from "react";
import { useFollowupFlows } from "@/features/followup/hooks/useFollowupFlows";
import { FlowCard } from "@/features/followup/components/FlowCard";
import { FlowFormModal } from "@/features/followup/components/FlowFormModal";
import { useToast } from "@/shared/hooks/useToast";
import type { CreateFlowDto, FollowupFlow, UpdateFlowDto } from "@/features/followup/types";

export default function FollowupPage() {
  const { flows, loading, error, create, update, remove } = useFollowupFlows();
  const [showCreate, setShowCreate] = useState(false);
  const [editingFlow, setEditingFlow] = useState<FollowupFlow | null>(null);
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
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-headline-sm font-bold text-on-surface">Follow-up Flows</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-label-md font-semibold text-on-primary hover:opacity-90"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
            add
          </span>
          Novo Flow
        </button>
      </div>

      {flows.length === 0 ? (
        <div className="rounded-xl border border-outline-variant bg-surface-container-low py-16 text-center text-on-surface-variant">
          Nenhum flow cadastrado. Crie o primeiro!
        </div>
      ) : (
        <div className="space-y-3">
          {flows.map((flow) => (
            <FlowCard
              key={flow.id}
              flow={flow}
              onEdit={() => setEditingFlow(flow)}
              onToggle={async (dto: UpdateFlowDto) => {
                try {
                  await update(flow.id, dto);
                  toast.success(dto.is_active ? "Flow ativado" : "Flow pausado");
                } catch {
                  toast.error("Erro ao atualizar flow");
                }
              }}
              onDelete={async () => {
                try {
                  await remove(flow.id);
                  toast.success("Flow excluído");
                } catch {
                  toast.error("Erro ao excluir flow");
                }
              }}
            />
          ))}
        </div>
      )}

      {showCreate && (
        <FlowFormModal
          onSave={async (dto: CreateFlowDto | UpdateFlowDto) => {
            try {
              await create(dto as CreateFlowDto);
              toast.success("Flow criado");
              setShowCreate(false);
            } catch {
              toast.error("Erro ao criar flow");
            }
          }}
          onClose={() => setShowCreate(false)}
        />
      )}

      {editingFlow && (
        <FlowFormModal
          flow={editingFlow}
          onSave={async (dto: CreateFlowDto | UpdateFlowDto) => {
            try {
              await update(editingFlow.id, dto as UpdateFlowDto);
              toast.success("Flow atualizado");
              setEditingFlow(null);
            } catch {
              toast.error("Erro ao atualizar flow");
            }
          }}
          onClose={() => setEditingFlow(null)}
        />
      )}
    </div>
  );
}
