"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Drawer } from "@/shared/components/Drawer";
import { useProducts } from "@/features/products/hooks/useProducts";
import { useOnboardingSteps } from "../hooks/useOnboardingSteps";
import { StepList } from "./StepList";
import { useToast } from "@/shared/hooks/useToast";
import type { CreateFlowInput, OnboardingFlow, UpdateFlowInput } from "../types";
import { TRIGGER_EVENTS } from "../lib/triggerEvents";

interface Props {
  open: boolean;
  flow: OnboardingFlow | null;
  onClose: () => void;
  onCreate: (dto: CreateFlowInput) => Promise<OnboardingFlow>;
  onUpdate: (id: string, dto: UpdateFlowInput) => Promise<void>;
}

export function FlowDrawer({ open, flow, onClose, onCreate, onUpdate }: Props) {
  const toast = useToast();
  const { products, loading: productsLoading } = useProducts();

  const [name, setName] = useState("");
  const [productId, setProductId] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [triggerEventType, setTriggerEventType] = useState(
    flow?.trigger_event_type ?? "subscription.activated"
  );
  const [saving, setSaving] = useState(false);
  const [activeFlow, setActiveFlow] = useState<OnboardingFlow | null>(null);

  const isEditing = activeFlow !== null;
  const selectedProduct = products.find((p) => p.id === productId);

  const {
    steps,
    loading: stepsLoading,
    create: createStep,
    update: updateStep,
    remove: removeStep,
    reorder,
  } = useOnboardingSteps(activeFlow?.id ?? "");

  useEffect(() => {
    if (open) {
      if (flow) {
        setName(flow.name);
        setProductId(flow.product.id);
        setIsActive(flow.is_active);
        setTriggerEventType(flow.trigger_event_type ?? "subscription.activated");
        setActiveFlow(flow);
      } else {
        setName("");
        setProductId("");
        setIsActive(true);
        setTriggerEventType("subscription.activated");
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
    if (!isEditing && selectedProduct) {
      setName(`Produto: ${selectedProduct.name}`);
    }
  }, [productId, isEditing]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!productId) {
      toast.error("Selecione um produto");
      return;
    }
    setSaving(true);
    try {
      if (activeFlow) {
        await onUpdate(activeFlow.id, {
          name,
          product_id: productId,
          is_active: isActive,
          trigger_event_type: triggerEventType,
        });
        setActiveFlow((prev) =>
          prev
            ? {
                ...prev,
                name,
                is_active: isActive,
                product: products.find((p) => p.id === productId) ?? prev.product,
              }
            : prev
        );
        toast.success("Flow atualizado");
      } else {
        const created = await onCreate({
          name,
          product_id: productId,
          is_active: isActive,
          trigger_event_type: triggerEventType,
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

  const noProducts = !productsLoading && products.length === 0;
  // No modo criar, só mostra o restante do form após escolher o produto
  const showFormFields = isEditing || !!productId;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={
        activeFlow
          ? `Follow-up — ${selectedProduct?.name ?? activeFlow.product?.name ?? "Produto"}`
          : "Novo follow-up"
      }
      footer={
        showFormFields ? (
          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="border border-outline-variant bg-surface px-4 py-2.5 text-sm font-medium text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface"
            >
              {activeFlow ? "Fechar" : "Cancelar"}
            </button>
            <button
              type="submit"
              form="flow-form"
              disabled={saving || !name.trim() || !productId || noProducts}
              className="flex items-center gap-2 bg-primary px-5 py-2.5 text-sm font-semibold text-on-primary transition-colors hover:bg-primary/90 disabled:opacity-50"
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
          {productsLoading ? (
            <div className="flex items-center gap-2 rounded-lg border border-outline-variant bg-surface px-3 py-3 text-sm text-on-surface-variant">
              <span className="material-symbols-outlined animate-spin" style={{ fontSize: "16px" }}>
                progress_activity
              </span>
              Carregando produtos...
            </div>
          ) : (
            <select
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              required
              disabled={noProducts || isEditing}
              className="field-select disabled:opacity-60"
            >
              <option value="" disabled>
                Selecione um produto
              </option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          )}
          {noProducts && (
            <p className="text-xs text-on-surface-variant">
              Nenhum produto cadastrado.{" "}
              <Link
                href="/products"
                className="text-primary underline-offset-2 hover:underline"
              >
                Cadastre primeiro
              </Link>
              .
            </p>
          )}
          {!noProducts && productId && (
            <span className="animate-fade-in text-xs text-on-surface-variant">
              O flow será disparado quando uma compra desse produto for registrada.
            </span>
          )}
        </div>

        {/* Campos revelados após escolher o produto */}
        {showFormFields && (
          <div key={productId} className="animate-fade-in flex flex-col gap-5">
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

            {/* Evento disparador — radio-grid colorido por semântica do funil */}
            <fieldset className="animate-fade-in flex flex-col">
              <legend className="mb-4 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-on-surface-variant">
                <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
                  bolt
                </span>
                Evento disparador
              </legend>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {TRIGGER_EVENTS.map((event) => {
                  const selected = triggerEventType === event.value;
                  return (
                    <label
                      key={event.value}
                      className={[
                        "group relative flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-all duration-200",
                        selected
                          ? `${event.tone.bgActive} ${event.tone.border} ring-2 ${event.tone.ring}`
                          : "border-outline-variant bg-surface-container-low hover:border-outline hover:bg-surface-container",
                      ].join(" ")}
                    >
                      <input
                        type="radio"
                        name="trigger_event_type"
                        value={event.value}
                        checked={selected}
                        onChange={() => setTriggerEventType(event.value)}
                        className="sr-only"
                      />
                      <div
                        className={[
                          "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                          event.tone.bg,
                        ].join(" ")}
                      >
                        <span
                          className={["material-symbols-outlined", event.tone.text].join(" ")}
                          style={{ fontSize: "20px" }}
                        >
                          {event.icon}
                        </span>
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-semibold text-on-surface">
                            {event.label}
                          </span>
                          {selected && (
                            <span
                              className={["material-symbols-outlined", event.tone.text].join(" ")}
                              style={{
                                fontSize: "15px",
                                fontVariationSettings: "'FILL' 1",
                              }}
                            >
                              check_circle
                            </span>
                          )}
                        </div>
                        <code className="mt-0.5 block font-mono text-[10px] tracking-tight text-on-surface-variant/70">
                          {event.technical}
                        </code>
                        <p className="mt-1 text-xs leading-snug text-on-surface-variant">
                          {event.description}
                        </p>
                      </div>
                    </label>
                  );
                })}
              </div>
            </fieldset>

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
              Mensagens da sequência
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
