"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import {
  type AgentItem,
  listChatnexoAgents,
  createChatnexoAgent,
  deleteChatnexoAgent,
} from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";

interface AgentFormData {
  name: string;
  api_key: string;
}

function AgentListItem({
  agent,
  onDeleted,
}: {
  agent: AgentItem;
  onDeleted: (id: string) => void;
}) {
  const toast = useToast();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      await deleteChatnexoAgent(agent.id);
      toast.success(`Atendente "${agent.name}" removido.`);
      onDeleted(agent.id);
    } catch {
      toast.error("Erro ao remover atendente.");
      setDeleting(false);
      setConfirming(false);
    }
  }

  return (
    <div className="group flex items-center justify-between gap-3 rounded-xl border border-outline-variant bg-surface-container px-4 py-3 transition-colors hover:bg-surface-container-high/50">
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-sm font-semibold text-on-surface truncate">{agent.name}</span>
        <span className="font-mono text-xs text-on-surface-variant">{agent.api_key_masked}</span>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {confirming ? (
          <>
            <span className="text-xs text-on-surface-variant">Remover?</span>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="flex items-center gap-1 rounded-lg bg-error px-3 py-1.5 text-xs font-semibold text-on-error transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {deleting ? (
                <span className="material-symbols-outlined animate-spin" style={{ fontSize: "13px" }}>progress_activity</span>
              ) : null}
              Sim
            </button>
            <button
              onClick={() => setConfirming(false)}
              disabled={deleting}
              className="rounded-lg border border-outline-variant px-3 py-1.5 text-xs font-medium text-on-surface-variant transition-colors hover:bg-surface-container disabled:opacity-50"
            >
              Não
            </button>
          </>
        ) : (
          <button
            onClick={() => setConfirming(true)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant opacity-0 transition-all group-hover:opacity-100 hover:bg-error/10 hover:text-error"
            title="Remover atendente"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>delete</span>
          </button>
        )}
      </div>
    </div>
  );
}

export function ChatNexoAgentsCard() {
  const toast = useToast();
  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
    reset,
  } = useForm<AgentFormData>({
    mode: "onChange",
    defaultValues: { name: "", api_key: "" },
  });

  useEffect(() => {
    listChatnexoAgents()
      .then(setAgents)
      .catch(() => toast.error("Erro ao carregar atendentes."))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onSubmit(data: AgentFormData) {
    setSaving(true);
    try {
      const agent = await createChatnexoAgent({
        name: data.name.trim(),
        api_key: data.api_key.trim(),
      });
      setAgents((prev) => [...prev, agent]);
      reset();
      toast.success(`Atendente "${agent.name}" adicionado.`);
    } catch {
      toast.error("Erro ao adicionar atendente.");
    } finally {
      setSaving(false);
    }
  }

  function handleDeleted(id: string) {
    setAgents((prev) => prev.filter((a) => a.id !== id));
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
      {/* Card header */}
      <div className="flex items-center gap-3 border-b border-outline-variant/60 bg-surface-container-low dark:bg-surface-container px-5 py-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-container">
          <span
            className="material-symbols-outlined text-on-primary-container"
            style={{ fontSize: "20px", fontVariationSettings: "'FILL' 1" }}
          >
            support_agent
          </span>
        </div>
        <div>
          <p className="text-sm font-semibold text-on-surface">Atendentes</p>
          <p className="text-xs text-on-surface-variant">
            Cada atendente usa uma chave própria; o sistema escolhe aleatoriamente ao enviar onboarding
          </p>
        </div>
      </div>

      {/* Agents list */}
        <div className="p-5">
          {loading ? (
            <div className="flex items-center gap-2 py-4 text-sm text-on-surface-variant">
              <span className="material-symbols-outlined animate-spin" style={{ fontSize: "18px" }}>progress_activity</span>
              Carregando atendentes...
            </div>
          ) : agents.length === 0 ? (
            <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-outline-variant py-8 text-center">
              <span className="material-symbols-outlined text-on-surface-variant/40" style={{ fontSize: "32px" }}>person_off</span>
              <p className="text-sm font-medium text-on-surface-variant">Nenhum atendente cadastrado</p>
              <p className="text-xs text-on-surface-variant/60">
                Usando a chave de fallback configurada em ChatNexo &gt; API Key
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {agents.map((agent) => (
                <AgentListItem key={agent.id} agent={agent} onDeleted={handleDeleted} />
              ))}
            </div>
          )}
        </div>

        {/* Add agent form */}
        <form
          onSubmit={handleSubmit(onSubmit)}
          noValidate
          className="border-t border-outline-variant/60 bg-white dark:bg-surface-container px-5 py-4"
        >
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
            Adicionar atendente
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
            <div className="flex flex-col gap-1.5 flex-1">
              <label htmlFor="agent-name" className="text-xs font-medium text-on-surface-variant">
                Nome
              </label>
              <input
                id="agent-name"
                type="text"
                placeholder="Ex: Sofia"
                aria-invalid={errors.name ? "true" : "false"}
                {...register("name", {
                  required: "Nome é obrigatório.",
                  maxLength: { value: 120, message: "Máximo de 120 caracteres." },
                  validate: (v) => v.trim().length > 0 || "Nome não pode estar vazio.",
                })}
                className={[
                  "w-full rounded-xl border px-4 py-3 text-sm text-on-surface placeholder:text-on-surface-variant/40 transition-colors focus:outline-none focus:ring-2",
                  errors.name
                    ? "border-error bg-error/5 focus:border-error focus:ring-error/20"
                    : "border-outline-variant bg-surface-container-low focus:border-primary focus:ring-primary/20",
                ].join(" ")}
              />
              {errors.name && (
                <span className="flex items-center gap-1 text-xs text-error">
                  <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>error</span>
                  {errors.name.message}
                </span>
              )}
            </div>
            <div className="flex flex-col gap-1.5 flex-1">
              <label htmlFor="agent-api-key" className="text-xs font-medium text-on-surface-variant">
                API Key
              </label>
              <input
                id="agent-api-key"
                type="password"
                placeholder="nxia_..."
                aria-invalid={errors.api_key ? "true" : "false"}
                {...register("api_key", {
                  required: "API Key é obrigatória.",
                  minLength: { value: 8, message: "Mínimo de 8 caracteres." },
                  validate: (v) => v.trim().length > 0 || "API Key não pode estar vazia.",
                })}
                className={[
                  "w-full rounded-xl border px-4 py-3 text-sm text-on-surface placeholder:text-on-surface-variant/40 transition-colors focus:outline-none focus:ring-2",
                  errors.api_key
                    ? "border-error bg-error/5 focus:border-error focus:ring-error/20"
                    : "border-outline-variant bg-surface-container-low focus:border-primary focus:ring-primary/20",
                ].join(" ")}
              />
              {errors.api_key && (
                <span className="flex items-center gap-1 text-xs text-error">
                  <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>error</span>
                  {errors.api_key.message}
                </span>
              )}
            </div>
            <div className="flex sm:pt-[26px]">
              <button
                type="submit"
                disabled={saving || !isValid}
                className="flex items-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-on-primary transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {saving ? (
                  <span className="material-symbols-outlined animate-spin" style={{ fontSize: "16px" }}>progress_activity</span>
                ) : (
                  <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>add</span>
                )}
                Adicionar
              </button>
            </div>
          </div>
        </form>
    </div>
  );
}
