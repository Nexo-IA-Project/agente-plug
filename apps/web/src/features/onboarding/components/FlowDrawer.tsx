"use client";

import { useEffect, useMemo, useState } from "react";
import { Drawer } from "@/shared/components/Drawer";
import { useProducts } from "@/features/products/hooks/useProducts";
import { useToast } from "@/shared/hooks/useToast";
import type {
  CreateFlowInput,
  OnboardingFlow,
  UpdateFlowInput,
} from "../types";
import type { HublaEventType } from "../lib/triggerEvents";
import type { StepDescriptor, StepIndex } from "./steps/StepRail";
import { StepProductPicker } from "./steps/StepProductPicker";
import { StepEventPicker } from "./steps/StepEventPicker";
import { StepMessageBuilder } from "./steps/StepMessageBuilder";

interface Props {
  open: boolean;
  flow: OnboardingFlow | null;
  onClose: () => void;
  onCreate: (dto: CreateFlowInput) => Promise<OnboardingFlow>;
  onUpdate: (id: string, dto: UpdateFlowInput) => Promise<void>;
}

interface StepperState {
  current: StepIndex;
  direction: "forward" | "backward";
  productId: string;
  triggerEventType: HublaEventType;
  isActive: boolean;
  flowId: string | null;
}

const INITIAL_STATE: StepperState = {
  current: 1,
  direction: "forward",
  productId: "",
  triggerEventType: "subscription.activated",
  isActive: true,
  flowId: null,
};

export function FlowDrawer({
  open,
  flow,
  onClose,
  onCreate,
  onUpdate,
}: Props) {
  const toast = useToast();
  const { products, loading: productsLoading } = useProducts();
  const [saving, setSaving] = useState(false);
  const [state, setState] = useState<StepperState>(INITIAL_STATE);

  const isEditing = !!flow;
  const product = useMemo(
    () => products.find((p) => p.id === state.productId),
    [products, state.productId],
  );

  // Hidrata o state ao abrir
  useEffect(() => {
    if (!open) return;
    if (flow) {
      setState({
        current: 3, // editar abre direto no passo 3 (Mensagens)
        direction: "forward",
        productId: flow.product.id,
        triggerEventType:
          (flow.trigger_event_type as HublaEventType) ?? "subscription.activated",
        isActive: flow.is_active,
        flowId: flow.id,
      });
    } else {
      setState(INITIAL_STATE);
    }
  }, [flow, open]);

  function goTo(target: StepIndex) {
    setState((prev) => ({
      ...prev,
      direction: target > prev.current ? "forward" : "backward",
      current: target,
    }));
  }

  function canNavigateTo(target: StepIndex): boolean {
    if (isEditing) return true;
    if (target === 1) return true;
    if (target === 2) return !!state.productId;
    if (target === 3) return !!state.flowId;
    return false;
  }

  async function saveStep1AndAdvance() {
    if (!state.productId) {
      toast.error("Selecione um produto antes de continuar");
      return;
    }
    if (isEditing && state.flowId) {
      try {
        setSaving(true);
        await onUpdate(state.flowId, {
          product_id: state.productId,
          trigger_event_type: state.triggerEventType,
          is_active: state.isActive,
          name: `Produto: ${product?.name ?? ""}`,
        });
        toast.success("Flow atualizado");
      } catch (err) {
        toast.error(`Erro: ${(err as Error).message}`);
        return;
      } finally {
        setSaving(false);
      }
    }
    goTo(2);
  }

  async function saveStep2AndAdvance() {
    if (!product) {
      toast.error("Produto não encontrado");
      return;
    }
    try {
      setSaving(true);
      if (state.flowId) {
        await onUpdate(state.flowId, {
          product_id: state.productId,
          trigger_event_type: state.triggerEventType,
          is_active: state.isActive,
          name: `Produto: ${product.name}`,
        });
        toast.success("Flow atualizado");
        if (isEditing) {
          // editar: fechar imediatamente, conforme spec do item 4
          onClose();
          return;
        }
      } else {
        const created = await onCreate({
          product_id: state.productId,
          trigger_event_type: state.triggerEventType,
          is_active: state.isActive,
          name: `Produto: ${product.name}`,
        });
        setState((prev) => ({ ...prev, flowId: created.id }));
        toast.success("Flow criado — agora configure as mensagens");
      }
      goTo(3);
    } catch (err) {
      toast.error(`Erro ao salvar: ${(err as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  function finish() {
    onClose();
  }

  const stepDescriptors: StepDescriptor[] = [
    {
      index: 1,
      label: "Produto",
      hint: product?.name,
      status:
        state.current === 1
          ? "current"
          : state.productId
            ? "done"
            : "pending",
    },
    {
      index: 2,
      label: "Evento gatilho",
      hint: state.flowId ? state.triggerEventType : undefined,
      status:
        state.current === 2
          ? "current"
          : state.flowId
            ? "done"
            : !canNavigateTo(2)
              ? "locked"
              : "pending",
    },
    {
      index: 3,
      label: "Mensagens",
      status:
        state.current === 3
          ? "current"
          : !canNavigateTo(3)
            ? "locked"
            : "pending",
    },
  ];

  const title = isEditing ? "Editar flow" : "Novo fluxo de onboarding";

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <StepFooter
          current={state.current}
          saving={saving}
          isEditing={isEditing}
          canAdvance={
            state.current === 1 ? !!state.productId : state.current === 2
          }
          onBack={() => goTo((state.current - 1) as StepIndex)}
          onForward={async () => {
            if (state.current === 1) await saveStep1AndAdvance();
            else if (state.current === 2) await saveStep2AndAdvance();
            else finish();
          }}
        />
      }
    >
      <div className="-mx-6 -my-6 flex min-h-full">
        {/* Sidebar — navegação por step */}
        <aside className="w-[260px] shrink-0 border-r border-outline-variant bg-surface-container-low px-4 py-6">
          <div className="mb-5 px-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
              Configurando flow
            </p>
            <p className="mt-1 text-sm font-semibold text-on-surface">
              {isEditing ? "Editar fluxo" : "Novo fluxo de onboarding"}
            </p>
          </div>
          <SidebarSteps
            steps={stepDescriptors}
            onNavigate={(idx) => {
              if (canNavigateTo(idx)) goTo(idx);
            }}
          />
        </aside>

        {/* Conteúdo — fundo branco com padding */}
        <div className="min-w-0 flex-1 overflow-auto bg-surface px-8 py-7">
          <div
            key={state.current}
            className={
              state.direction === "forward"
                ? "onboarding-step-forward"
                : "onboarding-step-backward"
            }
          >
            {state.current === 1 && (
              <StepProductPicker
                products={products}
                loading={productsLoading}
                selectedProductId={state.productId}
                onSelect={(productId) =>
                  setState((prev) => ({ ...prev, productId }))
                }
                disabled={isEditing}
              />
            )}
            {state.current === 2 && (
              <StepEventPicker
                selectedEventType={state.triggerEventType}
                onSelect={(triggerEventType) =>
                  setState((prev) => ({ ...prev, triggerEventType }))
                }
                isActive={state.isActive}
                onToggleActive={(isActive) =>
                  setState((prev) => ({ ...prev, isActive }))
                }
              />
            )}
            {state.current === 3 && state.flowId && (
              <StepMessageBuilder
                flowId={state.flowId}
                triggerEventType={state.triggerEventType}
              />
            )}
          </div>
        </div>
      </div>
    </Drawer>
  );
}

function SidebarSteps({
  steps,
  onNavigate,
}: {
  steps: StepDescriptor[];
  onNavigate: (idx: StepIndex) => void;
}) {
  return (
    <ol className="flex flex-col gap-1">
      {steps.map((step) => {
        const locked = step.status === "locked";
        const current = step.status === "current";
        const done = step.status === "done";
        const baseRow =
          "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors";
        const rowState = locked
          ? "cursor-not-allowed text-on-surface-variant opacity-60"
          : current
            ? "bg-primary/10 text-primary"
            : done
              ? "text-emerald-700 hover:bg-emerald-500/10 dark:text-emerald-300"
              : "text-on-surface-variant hover:bg-surface-container-high";
        const circleState = current
          ? "bg-primary text-on-primary ring-2 ring-primary/30"
          : done
            ? "bg-emerald-500 text-white"
            : locked
              ? "border border-outline-variant bg-surface text-on-surface-variant"
              : "border border-outline-variant bg-surface text-on-surface-variant";
        return (
          <li key={step.index}>
            <button
              type="button"
              onClick={() => onNavigate(step.index)}
              disabled={locked}
              aria-current={current ? "step" : undefined}
              className={`${baseRow} ${rowState}`}
            >
              <div
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${circleState}`}
              >
                {done ? (
                  <span className="material-symbols-outlined text-sm">
                    check
                  </span>
                ) : (
                  step.index
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p
                  className={`text-sm ${current ? "font-semibold" : "font-medium"}`}
                >
                  {step.label}
                </p>
                {step.hint && (
                  <p className="truncate text-[11px] text-on-surface-variant">
                    {step.hint}
                  </p>
                )}
              </div>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function StepFooter({
  current,
  saving,
  isEditing,
  canAdvance,
  onBack,
  onForward,
}: {
  current: StepIndex;
  saving: boolean;
  isEditing: boolean;
  canAdvance: boolean;
  onBack: () => void;
  onForward: () => Promise<void> | void;
}) {
  const forwardLabel =
    current === 3
      ? "Concluir"
      : current === 2
        ? isEditing
          ? "Salvar alterações"
          : "Salvar e continuar"
        : isEditing
          ? "Salvar e continuar"
          : "Próximo";
  return (
    <div className="flex items-center justify-between">
      <button
        type="button"
        onClick={onBack}
        disabled={current === 1 || saving}
        className="rounded-md px-4 py-2 text-sm text-on-surface-variant hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-40"
      >
        Voltar
      </button>
      <button
        type="button"
        onClick={() => void onForward()}
        disabled={(!canAdvance && current !== 3) || saving}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-on-primary shadow-sm hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {saving ? "Salvando..." : forwardLabel}
      </button>
    </div>
  );
}
