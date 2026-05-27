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
import {
  StepRail,
  type StepIndex,
  type StepDescriptor,
} from "./steps/StepRail";
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
        current: 1,
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
      <div className="flex gap-6">
        {/* Rail lateral */}
        <div className="shrink-0">
          <StepRail
            steps={stepDescriptors}
            onNavigate={(idx) => {
              if (canNavigateTo(idx)) goTo(idx);
            }}
          />
        </div>

        {/* Painel do step ativo com animação */}
        <div className="min-w-0 flex-1">
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
              <StepMessageBuilder flowId={state.flowId} />
            )}
          </div>
        </div>
      </div>
    </Drawer>
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
