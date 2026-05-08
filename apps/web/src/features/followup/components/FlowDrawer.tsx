"use client";

import { useEffect, useState } from "react";
import { useFollowupSteps } from "../hooks/useFollowupSteps";
import { StepList } from "./StepList";
import { useToast } from "@/shared/hooks/useToast";
import type { CreateFlowDto, FollowupFlow, UpdateFlowDto } from "../types";

interface Props {
  open: boolean;
  flow: FollowupFlow | null;
  onClose: () => void;
  onCreate: (dto: CreateFlowDto) => Promise<FollowupFlow>;
  onUpdate: (id: string, dto: UpdateFlowDto) => Promise<void>;
}

export function FlowDrawer({ open, flow, onClose, onCreate, onUpdate }: Props) {
  const toast = useToast();

  const [name, setName] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeFlow, setActiveFlow] = useState<FollowupFlow | null>(null);
  const [stepsExpanded, setStepsExpanded] = useState(false);

  const {
    steps,
    loading: stepsLoading,
    create: createStep,
    update: updateStep,
    remove: removeStep,
    reorder,
  } = useFollowupSteps(activeFlow?.id ?? "");

  useEffect(() => {
    if (open) {
      if (flow) {
        setName(flow.name);
        setTagsInput(flow.product_tags.join(", "));
        setIsActive(flow.is_active);
        setActiveFlow(flow);
        const t = setTimeout(() => setStepsExpanded(true), 100);
        return () => clearTimeout(t);
      } else {
        setName("");
        setTagsInput("");
        setIsActive(true);
        setActiveFlow(null);
        setStepsExpanded(false);
      }
    } else {
      // reset com delay para a animação de fechar terminar
      const t = setTimeout(() => {
        setStepsExpanded(false);
        setActiveFlow(null);
      }, 400);
      return () => clearTimeout(t);
    }
  }, [flow, open]);

  async function handleSaveFlow(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    const tags = tagsInput
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    try {
      if (activeFlow) {
        await onUpdate(activeFlow.id, { name, product_tags: tags, is_active: isActive });
        setActiveFlow((prev) =>
          prev ? { ...prev, name, product_tags: tags, is_active: isActive } : prev
        );
        toast.success("Flow atualizado");
      } else {
        const created = await onCreate({ name, product_tags: tags });
        setActiveFlow(created);
        toast.success("Flow criado");
        setTimeout(() => setStepsExpanded(true), 60);
      }
    } catch {
      toast.error("Erro ao salvar flow");
    } finally {
      setSaving(false);
    }
  }

  const inputCls =
    "w-full rounded-xl border border-outline bg-surface px-3 py-2.5 text-sm text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:ring-2 focus:ring-primary transition-shadow";
  const labelCls = "mb-1.5 block text-label-sm font-medium text-on-surface-variant";

  return (
    <>
      {/* Área de conteúdo centralizada (após sidebar) */}
      <div
        className="fixed z-40"
        style={{
          left: "240px",
          right: 0,
          top: 0,
          bottom: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          pointerEvents: open ? "auto" : "none",
        }}
      >
        {/* Overlay */}
        <div
          onClick={onClose}
          className="absolute inset-0 bg-scrim/60"
          style={{
            opacity: open ? 1 : 0,
            transition: "opacity 500ms ease",
          }}
        />

        {/* Modal — altura automática, cresce com o conteúdo */}
        <div
          className="relative z-50 flex flex-col bg-surface-container"
          style={{
            width: "620px",
            maxWidth: "calc(100% - 48px)",
            maxHeight: "88vh",
            borderRadius: "20px",
            boxShadow: "0 24px 80px rgba(0,0,0,0.5), 0 4px 16px rgba(0,0,0,0.3)",
            transformOrigin: "center center",
            transform: open ? "scale(1)" : "scale(0.78)",
            opacity: open ? 1 : 0,
            transition: "transform 600ms cubic-bezier(0.16, 1, 0.3, 1), opacity 480ms ease",
            overflow: "hidden",
          }}
        >
          {/* ── Header ── */}
          <div className="flex shrink-0 items-center justify-between border-b border-outline-variant/40 px-6 py-5">
            <div>
              <h2 className="text-title-md font-semibold text-on-surface">
                {activeFlow ? "Editar Flow" : "Novo Follow-up"}
              </h2>
              {activeFlow && stepsExpanded && (
                <p
                  className="mt-0.5 text-label-sm text-on-surface-variant"
                  style={{
                    opacity: stepsExpanded ? 1 : 0,
                    transition: "opacity 300ms ease 200ms",
                  }}
                >
                  {steps.length} step{steps.length !== 1 ? "s" : ""} configurado
                  {steps.length !== 1 ? "s" : ""}
                </p>
              )}
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container-high"
              aria-label="Fechar"
            >
              <span className="material-symbols-outlined" style={{ fontSize: "22px" }}>
                close
              </span>
            </button>
          </div>

          {/* ── Body com scroll interno ── */}
          <div className="overflow-y-auto" style={{ minHeight: 0 }}>
            <div className="px-6 py-6 space-y-6">

              {/* Formulário */}
              <form id="flow-form" onSubmit={handleSaveFlow} className="space-y-4">
                <div>
                  <label className={labelCls}>Nome do flow</label>
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    autoFocus
                    placeholder="Ex: Boas-vindas Premium"
                    className={inputCls}
                  />
                </div>

                <div>
                  <label className={labelCls}>Tags de produto</label>
                  <input
                    value={tagsInput}
                    onChange={(e) => setTagsInput(e.target.value)}
                    placeholder="premium, vip, curso"
                    className={inputCls}
                  />
                  <p className="mt-1.5 text-xs text-on-surface-variant/70">
                    Separe por vírgulas — o flow dispara quando a compra contém uma dessas tags.
                  </p>
                </div>

                {activeFlow && (
                  <div className="flex items-center justify-between rounded-xl border border-outline-variant bg-surface px-4 py-3">
                    <div>
                      <p className="text-sm font-medium text-on-surface">Status</p>
                      <p className="text-xs text-on-surface-variant">
                        {isActive ? "Ativo — disparando normalmente" : "Pausado — sem disparos"}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setIsActive(!isActive)}
                      className={`relative h-6 w-11 rounded-full transition-colors duration-200 ${
                        isActive ? "bg-primary" : "bg-outline-variant"
                      }`}
                    >
                      <span
                        className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-200 ${
                          isActive ? "translate-x-5" : "translate-x-0"
                        }`}
                      />
                    </button>
                  </div>
                )}
              </form>

              {/* Seção de steps — expande com grid-template-rows */}
              <div
                style={{
                  display: "grid",
                  gridTemplateRows: stepsExpanded ? "1fr" : "0fr",
                  transition: "grid-template-rows 540ms cubic-bezier(0.16, 1, 0.3, 1)",
                }}
              >
                <div style={{ overflow: "hidden" }}>
                  {/* Divisor */}
                  <div className="mb-5 flex items-center gap-4">
                    <div className="h-px flex-1 bg-outline-variant/40" />
                    <p className="text-label-xs font-semibold uppercase tracking-widest text-on-surface-variant/50">
                      Steps de disparo
                    </p>
                    <div className="h-px flex-1 bg-outline-variant/40" />
                  </div>

                  {activeFlow && (
                    stepsLoading ? (
                      <div className="flex items-center justify-center gap-2 py-8 text-on-surface-variant">
                        <span
                          className="material-symbols-outlined animate-spin"
                          style={{ fontSize: "20px" }}
                        >
                          progress_activity
                        </span>
                        <span className="text-sm">Carregando steps...</span>
                      </div>
                    ) : (
                      <StepList
                        steps={steps}
                        onReorder={async (items) => {
                          try { await reorder(items); }
                          catch { toast.error("Erro ao reordenar"); }
                        }}
                        onCreate={async (dto) => {
                          try {
                            await createStep(dto);
                            toast.success("Step adicionado");
                          } catch { toast.error("Erro ao adicionar step"); }
                        }}
                        onUpdate={async (stepId, dto) => {
                          try {
                            await updateStep(stepId, dto);
                            toast.success("Step atualizado");
                          } catch { toast.error("Erro ao atualizar step"); }
                        }}
                        onDelete={async (stepId) => {
                          try {
                            await removeStep(stepId);
                            toast.success("Step excluído");
                          } catch { toast.error("Erro ao excluir step"); }
                        }}
                      />
                    )
                  )}

                  {/* Espaço no final para o scroll não colar no footer */}
                  <div className="h-4" />
                </div>
              </div>

            </div>
          </div>

          {/* ── Footer fixo ── */}
          <div className="shrink-0 border-t border-outline-variant/40 px-6 py-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onClose}
                className="rounded-xl px-5 py-2.5 text-label-sm font-medium text-on-surface-variant transition-colors hover:bg-surface-container-high"
              >
                {activeFlow ? "Fechar" : "Cancelar"}
              </button>

              <button
                type="submit"
                form="flow-form"
                disabled={saving || !name.trim()}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-primary py-2.5 text-label-sm font-semibold text-on-primary transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {saving && (
                  <span
                    className="material-symbols-outlined animate-spin"
                    style={{ fontSize: "16px" }}
                  >
                    progress_activity
                  </span>
                )}
                {saving ? "Salvando..." : activeFlow ? "Salvar Alterações" : "Criar Flow"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
