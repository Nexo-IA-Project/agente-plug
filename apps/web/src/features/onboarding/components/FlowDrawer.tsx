"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
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

interface FlowFormData {
  product_id: string;
  name: string;
  trigger_event_type: string;
  is_active: boolean;
}

export function FlowDrawer({ open, flow, onClose, onCreate, onUpdate }: Props) {
  const toast = useToast();
  const { products, loading: productsLoading } = useProducts();
  const [saving, setSaving] = useState(false);
  const [activeFlow, setActiveFlow] = useState<OnboardingFlow | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors, isValid },
  } = useForm<FlowFormData>({
    mode: "onChange",
    defaultValues: {
      product_id: "",
      name: "",
      trigger_event_type: "subscription.activated",
      is_active: true,
    },
  });

  const productId = watch("product_id");
  const triggerEventType = watch("trigger_event_type");
  const isActive = watch("is_active");
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
        reset({
          product_id: flow.product.id,
          name: flow.name,
          trigger_event_type: flow.trigger_event_type ?? "subscription.activated",
          is_active: flow.is_active,
        });
        setActiveFlow(flow);
      } else {
        reset({
          product_id: "",
          name: "",
          trigger_event_type: "subscription.activated",
          is_active: true,
        });
        setActiveFlow(null);
      }
    } else {
      const t = setTimeout(() => {
        setActiveFlow(null);
      }, 350);
      return () => clearTimeout(t);
    }
  }, [flow, open, reset]);

  // Ao criar: preenche o nome automaticamente ao escolher o produto
  useEffect(() => {
    if (!isEditing && selectedProduct) {
      setValue("name", `Produto: ${selectedProduct.name}`, { shouldValidate: true });
    }
  }, [productId, isEditing, selectedProduct, setValue]);

  async function onSubmit(data: FlowFormData) {
    setSaving(true);
    try {
      if (activeFlow) {
        await onUpdate(activeFlow.id, {
          name: data.name.trim(),
          product_id: data.product_id,
          is_active: data.is_active,
          trigger_event_type: data.trigger_event_type,
        });
        setActiveFlow((prev) =>
          prev
            ? {
                ...prev,
                name: data.name.trim(),
                is_active: data.is_active,
                product:
                  products.find((p) => p.id === data.product_id) ?? prev.product,
              }
            : prev
        );
        toast.success("Fluxo de onboarding atualizado.");
      } else {
        const created = await onCreate({
          name: data.name.trim(),
          product_id: data.product_id,
          is_active: data.is_active,
          trigger_event_type: data.trigger_event_type,
        });
        setActiveFlow(created);
        toast.success("Fluxo de onboarding criado.");
      }
      onClose();
    } catch {
      toast.error("Erro ao salvar fluxo.");
    } finally {
      setSaving(false);
    }
  }

  const noProducts = !productsLoading && products.length === 0;
  const showFormFields = isEditing || !!productId;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={
        activeFlow
          ? `Onboarding — ${selectedProduct?.name ?? activeFlow.product?.name ?? "Produto"}`
          : "Novo fluxo de onboarding"
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
              disabled={saving || !isValid || noProducts}
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
              {saving
                ? "Salvando..."
                : activeFlow
                ? "Salvar alterações"
                : "Criar fluxo"}
            </button>
          </div>
        ) : null
      }
    >
      <form
        id="flow-form"
        onSubmit={handleSubmit(onSubmit)}
        noValidate
        className="flex flex-col gap-5"
      >
        {/* Seleção de produto */}
        <div className="flex flex-col gap-2">
          <span className="text-xs font-medium text-on-surface-variant uppercase tracking-wide">
            Produto
          </span>
          {productsLoading ? (
            <div className="flex items-center gap-2 rounded-lg border border-outline-variant bg-surface px-3 py-3 text-sm text-on-surface-variant">
              <span
                className="material-symbols-outlined animate-spin"
                style={{ fontSize: "16px" }}
              >
                progress_activity
              </span>
              Carregando produtos...
            </div>
          ) : (
            <select
              {...register("product_id", { required: "Selecione um produto." })}
              disabled={noProducts || isEditing}
              aria-invalid={errors.product_id ? "true" : "false"}
              className={[
                "field-select disabled:opacity-60",
                errors.product_id && "border-error",
              ]
                .filter(Boolean)
                .join(" ")}
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
          {errors.product_id && (
            <span className="flex items-center gap-1 text-xs text-error">
              <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
                error
              </span>
              {errors.product_id.message}
            </span>
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
              O fluxo será disparado quando uma compra desse produto for registrada.
            </span>
          )}
        </div>

        {/* Campos revelados após escolher o produto */}
        {showFormFields && (
          <div key={productId} className="animate-fade-in flex flex-col gap-5">
            {/* Nome do fluxo */}
            <div className="flex flex-col gap-2">
              <span className="text-xs font-medium text-on-surface-variant uppercase tracking-wide">
                Nome do fluxo
              </span>
              <input
                type="text"
                placeholder="Nome do fluxo"
                readOnly={!isEditing}
                aria-invalid={errors.name ? "true" : "false"}
                {...register("name", {
                  required: "Nome é obrigatório.",
                  maxLength: { value: 120, message: "Máximo de 120 caracteres." },
                  validate: (v) =>
                    v.trim().length > 0 || "Nome não pode estar vazio.",
                })}
                className={[
                  "field-input",
                  !isEditing && "cursor-default bg-surface-container text-on-surface-variant",
                  errors.name && "border-error",
                ]
                  .filter(Boolean)
                  .join(" ")}
              />
              {errors.name ? (
                <span className="flex items-center gap-1 text-xs text-error">
                  <span
                    className="material-symbols-outlined"
                    style={{ fontSize: "14px" }}
                  >
                    error
                  </span>
                  {errors.name.message}
                </span>
              ) : !isEditing ? (
                <span className="text-xs text-on-surface-variant/70">
                  Nome gerado automaticamente a partir do produto selecionado.
                </span>
              ) : null}
            </div>

            {/* Evento disparador */}
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
                        value={event.value}
                        checked={selected}
                        {...register("trigger_event_type", {
                          required: "Selecione um evento disparador.",
                        })}
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
                  {...register("is_active")}
                  className="sr-only"
                />
                <div
                  className={[
                    "flex h-5 w-5 items-center justify-center rounded transition-colors",
                    isActive ? "bg-primary" : "border border-outline bg-surface",
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
              <span className="text-sm">Carregando mensagens...</span>
            </div>
          ) : (
            <StepList
              steps={steps}
              onReorder={async (items) => {
                try {
                  await reorder(items);
                } catch {
                  toast.error("Erro ao reordenar.");
                }
              }}
              onCreate={async (dto) => {
                try {
                  await createStep(dto);
                  toast.success("Mensagem adicionada.");
                } catch {
                  toast.error("Erro ao adicionar mensagem.");
                }
              }}
              onUpdate={async (stepId, dto) => {
                try {
                  await updateStep(stepId, dto);
                  toast.success("Mensagem atualizada.");
                } catch {
                  toast.error("Erro ao atualizar mensagem.");
                }
              }}
              onDelete={async (stepId) => {
                try {
                  await removeStep(stepId);
                  toast.success("Mensagem excluída.");
                } catch {
                  toast.error("Erro ao excluir mensagem.");
                }
              }}
            />
          )}
        </section>
      )}
    </Drawer>
  );
}
