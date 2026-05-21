"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Drawer } from "@/shared/components/Drawer";
import { useCourses } from "@/features/courses/hooks/useCourses";
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
  const { courses, loading: coursesLoading } = useCourses();

  const [name, setName] = useState("");
  const [courseId, setCourseId] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeFlow, setActiveFlow] = useState<FollowupFlow | null>(null);

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
        setCourseId(flow.course.id);
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!courseId) {
      toast.error("Selecione um curso");
      return;
    }
    setSaving(true);
    try {
      if (activeFlow) {
        await onUpdate(activeFlow.id, {
          name,
          course_id: courseId,
          is_active: isActive,
        });
        setActiveFlow((prev) =>
          prev
            ? {
                ...prev,
                name,
                is_active: isActive,
                course:
                  courses.find((c) => c.id === courseId) ?? prev.course,
              }
            : prev
        );
        toast.success("Flow atualizado");
      } else {
        const created = await onCreate({
          name,
          course_id: courseId,
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

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={activeFlow ? `Editar — ${activeFlow.name}` : "Novo follow-up"}
      footer={
        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-4 py-2 text-on-surface-variant hover:bg-surface-container-high"
          >
            {activeFlow ? "Fechar" : "Cancelar"}
          </button>
          <button
            type="submit"
            form="flow-form"
            disabled={saving || !name.trim() || !courseId || noCourses}
            className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-on-primary disabled:opacity-50"
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
      }
    >
      <form id="flow-form" onSubmit={handleSubmit} className="flex flex-col gap-6">
        <label className="flex flex-col gap-2">
          <span className="text-sm font-medium text-on-surface">Nome do flow</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
            placeholder="Ex: Boas-vindas Premium"
            className="rounded-md border border-outline-variant bg-surface px-3 py-2 text-on-surface"
          />
        </label>

        <label className="flex flex-col gap-2">
          <span className="text-sm font-medium text-on-surface">Curso</span>
          {coursesLoading ? (
            <div className="flex items-center gap-2 rounded-md border border-outline-variant bg-surface px-3 py-2 text-sm text-on-surface-variant">
              <span
                className="material-symbols-outlined animate-spin"
                style={{ fontSize: "16px" }}
              >
                progress_activity
              </span>
              Carregando cursos...
            </div>
          ) : (
            <select
              value={courseId}
              onChange={(e) => setCourseId(e.target.value)}
              required
              disabled={noCourses}
              className="rounded-md border border-outline-variant bg-surface px-3 py-2 text-on-surface disabled:opacity-50"
            >
              <option value="" disabled>
                Selecione um curso
              </option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.hubla_id})
                </option>
              ))}
            </select>
          )}
          {noCourses && (
            <p className="text-xs text-on-surface-variant">
              Nenhum curso cadastrado.{" "}
              <Link
                href="/courses"
                className="text-primary underline-offset-2 hover:underline"
              >
                Cadastre primeiro
              </Link>
              .
            </p>
          )}
          {!noCourses && (
            <span className="text-xs text-on-surface-variant">
              O flow será disparado quando uma compra desse curso for registrada.
            </span>
          )}
        </label>

        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="h-4 w-4"
          />
          <span className="text-sm text-on-surface">
            Ativo — disparando normalmente
          </span>
        </label>
      </form>

      {activeFlow && (
        <section className="mt-8">
          <div className="mb-4 flex items-center gap-4">
            <div className="h-px flex-1 bg-outline-variant/40" />
            <p className="text-label-xs font-semibold uppercase tracking-widest text-on-surface-variant/60">
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
