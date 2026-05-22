"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Drawer } from "@/shared/components/Drawer";
import { useProducts } from "@/features/courses/hooks/useCourses";
import { useFollowupSteps } from "../hooks/useFollowupSteps";
import { StepList } from "./StepList";
import { useToast } from "@/shared/hooks/useToast";
import type { CreateFlowInput, FollowupFlow, UpdateFlowInput } from "../types";

interface Props {
  open: boolean;
  flow: FollowupFlow | null;
  onClose: () => void;
  onCreate: (dto: CreateFlowInput) => Promise<FollowupFlow>;
  onUpdate: (id: string, dto: UpdateFlowInput) => Promise<void>;
}

export function FlowDrawer({ open, flow, onClose, onCreate, onUpdate }: Props) {
  const toast = useToast();
  const { products: courses, loading: coursesLoading } = useProducts();

  const [name, setName] = useState("");
  const [courseId, setCourseId] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeFlow, setActiveFlow] = useState<FollowupFlow | null>(null);

  const isEditing = activeFlow !== null;
  const selectedCourse = courses.find((c) => c.id === courseId);

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
        setCourseId(flow.product.id);
        setIsActive(flow.is_active);
        setActiveFlow(flow);
      } else {
        setName("");
        setCourseId("");
        setIsActive(true);
        setActiveFlow(null);
      }
    } else {
      const t = setTimeout(() => {
        setActiveFlow(null);
      }, 350);
      return () => clearTimeout(t);
    }
  }, [flow, open]);

  // Ao criar: preenche o nome automaticamente ao escolher o produto
  useEffect(() => {
    if (!isEditing && selectedCourse) {
      setName(`Produto: ${selectedCourse.name}`);
    }
  }, [courseId, isEditing]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!courseId) {
      toast.error("Selecione um produto");
      return;
    }
    setSaving(true);
    try {
      if (activeFlow) {
        await onUpdate(activeFlow.id, {
          name,
          product_id: courseId,
          is_active: isActive,
        });
        setActiveFlow((prev) =>
          prev
            ? {
                ...prev,
                name,
                is_active: isActive,
                product: courses.find((c) => c.id === courseId) ?? prev.product,
              }
            : prev
        );
        toast.success("Flow atualizado");
      } else {
        const created = await onCreate({
          name,
          product_id: courseId,
          is_active: isActive,
        });
        setActiveFlow(created);
        toast.success("Flow criado");
      }
    } catch {
      toast.error("Erro ao salvar flow");
    } finally {
      setSaving(false);
    }
  }

  const noCourses = !coursesLoading && courses.length === 0;
  // No modo criar, só mostra o restante do form após escolher o produto
  const showFormFields = isEditing || !!courseId;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={activeFlow ? `Editar — ${activeFlow.name}` : "Novo follow-up"}
      footer={
        showFormFields ? (
          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2.5 text-sm text-on-surface-variant hover:bg-surface-container-high transition-colors"
            >
              {activeFlow ? "Fechar" : "Cancelar"}
            </button>
            <button
              type="submit"
              form="flow-form"
              disabled={saving || !name.trim() || !courseId || noCourses}
              className="flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-on-primary disabled:opacity-50 transition-colors"
            >
              {saving && (
                <span
                  className="material-symbols-outlined animate-spin"
                  style={{ fontSize: "16px" }}
                >
                  progress_activity
                </span>
              )}
              {saving ? "Salvando..." : activeFlow ? "Salvar alterações" : "Criar flow"}
            </button>
          </div>
        ) : null
      }
    >
      <form id="flow-form" onSubmit={handleSubmit} className="flex flex-col gap-5">
        {/* Seleção de produto — aparece sempre primeiro */}
        <div className="flex flex-col gap-2">
          <span className="text-xs font-medium text-on-surface-variant uppercase tracking-wide">
            Produto
          </span>
          {coursesLoading ? (
            <div className="flex items-center gap-2 rounded-lg border border-outline-variant bg-surface px-3 py-3 text-sm text-on-surface-variant">
              <span className="material-symbols-outlined animate-spin" style={{ fontSize: "16px" }}>
                progress_activity
              </span>
              Carregando produtos...
            </div>
          ) : (
            <select
              value={courseId}
              onChange={(e) => setCourseId(e.target.value)}
              required
              disabled={noCourses || isEditing}
              className="field-select disabled:opacity-60"
            >
              <option value="" disabled>
                Selecione um produto
              </option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
          {noCourses && (
            <p className="text-xs text-on-surface-variant">
              Nenhum produto cadastrado.{" "}
              <Link
                href="/courses"
                className="text-primary underline-offset-2 hover:underline"
              >
                Cadastre primeiro
              </Link>
              .
            </p>
          )}
          {!noCourses && courseId && (
            <span className="animate-fade-in text-xs text-on-surface-variant">
              O flow será disparado quando uma compra desse produto for registrada.
            </span>
          )}
        </div>

        {/* Campos revelados após escolher o produto */}
        {showFormFields && (
          <div key={courseId} className="animate-fade-in flex flex-col gap-5">
            {/* Nome do flow — pré-preenchido e bloqueado no modo criar */}
            <div className="flex flex-col gap-2">
              <span className="text-xs font-medium text-on-surface-variant uppercase tracking-wide">
                Nome do flow
              </span>
              <input
                type="text"
                value={name}
                onChange={(e) => isEditing && setName(e.target.value)}
                readOnly={!isEditing}
                required
                placeholder="Nome do flow"
                className={[
                  "field-input",
                  !isEditing && "cursor-default bg-surface-container text-on-surface-variant",
                ]
                  .filter(Boolean)
                  .join(" ")}
              />
              {!isEditing && (
                <span className="text-xs text-on-surface-variant/70">
                  Nome gerado automaticamente a partir do produto selecionado.
                </span>
              )}
            </div>

            {/* Checkbox ativo */}
            <label className="flex cursor-pointer items-center gap-3">
              <div className="relative">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="sr-only"
                />
                <div
                  className={[
                    "flex h-5 w-5 items-center justify-center rounded transition-colors",
                    isActive
                      ? "bg-primary"
                      : "border border-outline bg-surface",
                  ].join(" ")}
                >
                  {isActive && (
                    <span
                      className="material-symbols-outlined text-on-primary"
                      style={{ fontSize: "14px", fontVariationSettings: "'FILL' 1" }}
                    >
                      check
                    </span>
                  )}
                </div>
              </div>
              <span className="text-sm text-on-surface">
                Ativo — disparando normalmente
              </span>
            </label>
          </div>
        )}
      </form>

      {activeFlow && (
        <section className="mt-8">
          <div className="mb-5 flex items-center gap-4">
            <div className="h-px flex-1 bg-outline-variant/40" />
            <p className="text-xs font-semibold uppercase tracking-widest text-on-surface-variant/60">
              Steps de disparo
            </p>
            <div className="h-px flex-1 bg-outline-variant/40" />
          </div>

          {stepsLoading ? (
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
                try {
                  await reorder(items);
                } catch {
                  toast.error("Erro ao reordenar");
                }
              }}
              onCreate={async (dto) => {
                try {
                  await createStep(dto);
                  toast.success("Step adicionado");
                } catch {
                  toast.error("Erro ao adicionar step");
                }
              }}
              onUpdate={async (stepId, dto) => {
                try {
                  await updateStep(stepId, dto);
                  toast.success("Step atualizado");
                } catch {
                  toast.error("Erro ao atualizar step");
                }
              }}
              onDelete={async (stepId) => {
                try {
                  await removeStep(stepId);
                  toast.success("Step excluído");
                } catch {
                  toast.error("Erro ao excluir step");
                }
              }}
            />
          )}
        </section>
      )}
    </Drawer>
  );
}
