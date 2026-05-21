"use client";

import { useState } from "react";
import { useFollowupFlows } from "@/features/followup/hooks/useFollowupFlows";
import { FlowCard } from "@/features/followup/components/FlowCard";
import { FlowDrawer } from "@/features/followup/components/FlowDrawer";
import { useToast } from "@/shared/hooks/useToast";
import type { CreateFlowInput, FollowupFlow, UpdateFlowInput } from "@/features/followup/types";

export default function FollowupPage() {
  const { flows, loading, error, create, update, remove } = useFollowupFlows();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingFlow, setEditingFlow] = useState<FollowupFlow | null>(null);
  const toast = useToast();

  function openCreate() {
    setEditingFlow(null);
    setDrawerOpen(true);
  }

  function openEdit(flow: FollowupFlow) {
    setEditingFlow(flow);
    setDrawerOpen(true);
  }

  function closeDrawer() {
    setDrawerOpen(false);
  }

  if (loading)
    return (
      <div className="flex h-full items-center justify-center gap-2 text-on-surface-variant">
        <span className="material-symbols-outlined animate-spin" style={{ fontSize: "20px" }}>
          progress_activity
        </span>
        <span className="text-sm">Carregando...</span>
      </div>
    );

  if (error)
    return (
      <div className="flex h-full items-center justify-center p-6 text-error">{error}</div>
    );

  return (
    <div
      className="-mx-6 -my-6 flex flex-col bg-surface-container-lowest"
      style={{ height: "calc(100vh - 64px)" }}
    >
      <div className="flex shrink-0 items-center justify-between border-b border-outline-variant/40 px-8 py-5">
        <div>
          <h1 className="text-headline-sm font-bold text-on-surface">Follow-up Flows</h1>
          <p className="mt-0.5 text-label-sm text-on-surface-variant">
            {flows.length === 0
              ? "Nenhum flow cadastrado"
              : `${flows.length} flow${flows.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-label-md font-semibold text-on-primary transition-opacity hover:opacity-90"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
            add
          </span>
          Novo Flow
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6">
        {flows.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-container-high">
              <span
                className="material-symbols-outlined text-on-surface-variant"
                style={{ fontSize: "32px" }}
              >
                bolt
              </span>
            </div>
            <div>
              <p className="text-body-lg font-semibold text-on-surface">Nenhum flow ainda</p>
              <p className="mt-1 text-body-sm text-on-surface-variant">
                Crie seu primeiro follow-up para começar a engajar clientes
              </p>
            </div>
            <button
              onClick={openCreate}
              className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-label-md font-semibold text-on-primary hover:opacity-90"
            >
              <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
                add
              </span>
              Criar primeiro flow
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {flows.map((flow) => (
              <FlowCard
                key={flow.id}
                flow={flow}
                onEdit={() => openEdit(flow)}
                onToggle={async () => {
                  try {
                    await update(flow.id, { is_active: !flow.is_active });
                    toast.success(flow.is_active ? "Flow pausado" : "Flow ativado");
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
      </div>

      <FlowDrawer
        open={drawerOpen}
        flow={editingFlow}
        onClose={closeDrawer}
        onCreate={async (dto: CreateFlowInput) => {
          const created = await create(dto);
          return created;
        }}
        onUpdate={async (id: string, dto: UpdateFlowInput) => {
          await update(id, dto);
        }}
      />
    </div>
  );
}
