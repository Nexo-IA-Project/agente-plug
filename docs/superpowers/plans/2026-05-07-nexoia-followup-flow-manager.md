# Follow-up Flow Manager UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar as telas do painel admin para criar, visualizar, editar, reordenar e deletar flows e steps de follow-up, consumindo a API do Plano C.

**Architecture:** Feature module `src/features/followup/` seguindo o padrão NexoIA (types + hooks + components). Drag-and-drop via `@dnd-kit/core`. Páginas no App Router `/followup` e `/followup/[id]`.

**Tech Stack:** Next.js 15, TypeScript, Tailwind CSS, design system NexoIA, @dnd-kit/core, sonner (toast)

---

## File Map

### Criar
```
apps/web/src/features/followup/types.ts
apps/web/src/features/followup/hooks/useFollowupFlows.ts
apps/web/src/features/followup/hooks/useFollowupSteps.ts
apps/web/src/features/followup/components/DelayBadge.tsx
apps/web/src/features/followup/components/FlowCard.tsx
apps/web/src/features/followup/components/FlowFormModal.tsx
apps/web/src/features/followup/components/StepItem.tsx
apps/web/src/features/followup/components/StepFormModal.tsx
apps/web/src/features/followup/components/StepList.tsx
apps/web/src/app/(admin)/followup/page.tsx
apps/web/src/app/(admin)/followup/[id]/page.tsx
```

### Modificar
```
apps/web/src/lib/api.ts                              + funções de follow-up
apps/web/src/shared/components/layout/Sidebar.tsx   + item "Follow-up"
apps/web/package.json                               + @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
```

---

### Task 1: Dependências e tipos base

**Files:**
- Modify: `apps/web/package.json`
- Create: `apps/web/src/features/followup/types.ts`

- [ ] **Step 1: Instalar @dnd-kit**

```bash
cd apps/web && npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
```
Esperado: `added X packages`

- [ ] **Step 2: Criar tipos**

```typescript
// apps/web/src/features/followup/types.ts
export interface FollowupFlow {
  id: string;
  account_id: string;
  name: string;
  product_tags: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FollowupStep {
  id: string;
  flow_id: string;
  position: number;
  delay_from_purchase_hours: number;
  meta_template_name: string;
  template_variables: Record<string, string>;
  created_at: string;
}

export interface CreateFlowDto {
  name: string;
  product_tags: string[];
}

export interface UpdateFlowDto {
  name?: string;
  product_tags?: string[];
  is_active?: boolean;
}

export interface CreateStepDto {
  position: number;
  delay_from_purchase_hours: number;
  meta_template_name: string;
  template_variables: Record<string, string>;
}

export interface UpdateStepDto {
  position?: number;
  delay_from_purchase_hours?: number;
  meta_template_name?: string;
  template_variables?: Record<string, string>;
}

export interface ReorderItem {
  id: string;
  position: number;
}
```

- [ ] **Step 3: Commit**

```bash
cd apps/web && git add package.json package-lock.json src/features/followup/types.ts
git commit -m "feat(followup-ui): instalar dnd-kit e criar tipos"
```

---

### Task 2: Funções de API

**Files:**
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1: Adicionar funções de follow-up em `api.ts`**

Ao final de `apps/web/src/lib/api.ts`, adicionar:

```typescript
// ─── Follow-up Flows ─────────────────────────────────────────────────────────

import type {
  CreateFlowDto,
  CreateStepDto,
  FollowupFlow,
  FollowupStep,
  ReorderItem,
  UpdateFlowDto,
  UpdateStepDto,
} from "@/features/followup/types";

export async function listFollowupFlows(): Promise<FollowupFlow[]> {
  return apiFetch("/admin/followup/flows");
}

export async function createFollowupFlow(dto: CreateFlowDto): Promise<FollowupFlow> {
  return apiFetch("/admin/followup/flows", { method: "POST", body: JSON.stringify(dto) });
}

export async function updateFollowupFlow(id: string, dto: UpdateFlowDto): Promise<FollowupFlow> {
  return apiFetch(`/admin/followup/flows/${id}`, { method: "PUT", body: JSON.stringify(dto) });
}

export async function deleteFollowupFlow(id: string): Promise<void> {
  await apiFetch(`/admin/followup/flows/${id}`, { method: "DELETE" });
}

export async function listFollowupSteps(flowId: string): Promise<FollowupStep[]> {
  return apiFetch(`/admin/followup/flows/${flowId}/steps`);
}

export async function createFollowupStep(flowId: string, dto: CreateStepDto): Promise<FollowupStep> {
  return apiFetch(`/admin/followup/flows/${flowId}/steps`, {
    method: "POST",
    body: JSON.stringify(dto),
  });
}

export async function updateFollowupStep(
  flowId: string,
  stepId: string,
  dto: UpdateStepDto
): Promise<FollowupStep> {
  return apiFetch(`/admin/followup/flows/${flowId}/steps/${stepId}`, {
    method: "PUT",
    body: JSON.stringify(dto),
  });
}

export async function deleteFollowupStep(flowId: string, stepId: string): Promise<void> {
  await apiFetch(`/admin/followup/flows/${flowId}/steps/${stepId}`, { method: "DELETE" });
}

export async function reorderFollowupSteps(
  flowId: string,
  items: ReorderItem[]
): Promise<void> {
  await apiFetch(`/admin/followup/flows/${flowId}/steps/reorder`, {
    method: "PATCH",
    body: JSON.stringify({ steps: items }),
  });
}
```

**Nota:** Verificar que `apiFetch` já existe em `api.ts` e aceita esses parâmetros. Se a função base tiver nome diferente, ajustar de acordo.

- [ ] **Step 2: Verificar que o TypeScript compila**

```bash
cd apps/web && npm run build 2>&1 | head -30
```
Esperado: sem erros de tipo

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/lib/api.ts
git commit -m "feat(followup-ui): adicionar funções de API de follow-up"
```

---

### Task 3: Hooks

**Files:**
- Create: `apps/web/src/features/followup/hooks/useFollowupFlows.ts`
- Create: `apps/web/src/features/followup/hooks/useFollowupSteps.ts`

- [ ] **Step 1: Criar `useFollowupFlows.ts`**

```typescript
// apps/web/src/features/followup/hooks/useFollowupFlows.ts
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createFollowupFlow,
  deleteFollowupFlow,
  listFollowupFlows,
  updateFollowupFlow,
} from "@/lib/api";
import type { CreateFlowDto, FollowupFlow, UpdateFlowDto } from "../types";

export function useFollowupFlows() {
  const [flows, setFlows] = useState<FollowupFlow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listFollowupFlows();
      setFlows(data);
    } catch {
      setError("Não foi possível carregar os flows.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const create = useCallback(async (dto: CreateFlowDto): Promise<FollowupFlow> => {
    const flow = await createFollowupFlow(dto);
    setFlows((prev) => [...prev, flow]);
    return flow;
  }, []);

  const update = useCallback(async (id: string, dto: UpdateFlowDto): Promise<void> => {
    const updated = await updateFollowupFlow(id, dto);
    setFlows((prev) => prev.map((f) => (f.id === id ? updated : f)));
  }, []);

  const remove = useCallback(async (id: string): Promise<void> => {
    await deleteFollowupFlow(id);
    setFlows((prev) => prev.filter((f) => f.id !== id));
  }, []);

  return { flows, loading, error, reload: load, create, update, remove };
}
```

- [ ] **Step 2: Criar `useFollowupSteps.ts`**

```typescript
// apps/web/src/features/followup/hooks/useFollowupSteps.ts
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createFollowupStep,
  deleteFollowupStep,
  listFollowupSteps,
  reorderFollowupSteps,
  updateFollowupStep,
} from "@/lib/api";
import type { CreateStepDto, FollowupStep, ReorderItem, UpdateStepDto } from "../types";

export function useFollowupSteps(flowId: string) {
  const [steps, setSteps] = useState<FollowupStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listFollowupSteps(flowId);
      setSteps(data.sort((a, b) => a.position - b.position));
    } catch {
      setError("Não foi possível carregar os steps.");
    } finally {
      setLoading(false);
    }
  }, [flowId]);

  useEffect(() => { load(); }, [load]);

  const create = useCallback(async (dto: CreateStepDto): Promise<void> => {
    const step = await createFollowupStep(flowId, dto);
    setSteps((prev) => [...prev, step].sort((a, b) => a.position - b.position));
  }, [flowId]);

  const update = useCallback(async (stepId: string, dto: UpdateStepDto): Promise<void> => {
    const updated = await updateFollowupStep(flowId, stepId, dto);
    setSteps((prev) =>
      prev.map((s) => (s.id === stepId ? updated : s)).sort((a, b) => a.position - b.position)
    );
  }, [flowId]);

  const remove = useCallback(async (stepId: string): Promise<void> => {
    await deleteFollowupStep(flowId, stepId);
    setSteps((prev) => prev.filter((s) => s.id !== stepId));
  }, [flowId]);

  const reorder = useCallback(async (items: ReorderItem[]): Promise<void> => {
    await reorderFollowupSteps(flowId, items);
    const posMap = new Map(items.map((i) => [i.id, i.position]));
    setSteps((prev) =>
      prev.map((s) => ({ ...s, position: posMap.get(s.id) ?? s.position }))
          .sort((a, b) => a.position - b.position)
    );
  }, [flowId]);

  return { steps, loading, error, reload: load, create, update, remove, reorder };
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/followup/hooks/
git commit -m "feat(followup-ui): hooks useFollowupFlows e useFollowupSteps"
```

---

### Task 4: Componentes utilitários e modais

**Files:**
- Create: `apps/web/src/features/followup/components/DelayBadge.tsx`
- Create: `apps/web/src/features/followup/components/FlowFormModal.tsx`
- Create: `apps/web/src/features/followup/components/StepFormModal.tsx`

- [ ] **Step 1: Criar `DelayBadge.tsx`**

```tsx
// apps/web/src/features/followup/components/DelayBadge.tsx
export function formatDelay(hours: number): string {
  if (hours === 0) return "Imediato";
  if (hours < 24) return `${hours}h após compra`;
  const days = Math.floor(hours / 24);
  const rem = hours % 24;
  return rem === 0 ? `Dia ${days}` : `Dia ${days} +${rem}h`;
}

export function DelayBadge({ hours }: { hours: number }) {
  return (
    <span className="rounded-full bg-surface-container px-2 py-0.5 text-label-sm text-on-surface-variant font-mono">
      {formatDelay(hours)}
    </span>
  );
}
```

- [ ] **Step 2: Criar `FlowFormModal.tsx`**

```tsx
// apps/web/src/features/followup/components/FlowFormModal.tsx
"use client";

import { useState } from "react";
import type { CreateFlowDto, FollowupFlow, UpdateFlowDto } from "../types";

interface Props {
  flow?: FollowupFlow;
  onSave: (dto: CreateFlowDto | UpdateFlowDto) => Promise<void>;
  onClose: () => void;
}

export function FlowFormModal({ flow, onSave, onClose }: Props) {
  const [name, setName] = useState(flow?.name ?? "");
  const [tagsRaw, setTagsRaw] = useState((flow?.product_tags ?? []).join(", "));
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const product_tags = tagsRaw.split(",").map((t) => t.trim()).filter(Boolean);
      await onSave({ name, product_tags });
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-scrim/60">
      <div className="w-full max-w-md rounded-2xl bg-surface-container-low p-6 shadow-xl">
        <h2 className="mb-4 text-title-md font-semibold text-on-surface">
          {flow ? "Editar Flow" : "Novo Flow"}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-label-sm text-on-surface-variant mb-1">Nome</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="ex: Máquina de Vendas"
            />
          </div>
          <div>
            <label className="block text-label-sm text-on-surface-variant mb-1">
              Tags de produto (separadas por vírgula)
            </label>
            <input
              value={tagsRaw}
              onChange={(e) => setTagsRaw(e.target.value)}
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="ex: maquina_de_vendas, mv_curso"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-label-md text-on-surface-variant hover:bg-surface-container-high"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-primary px-4 py-2 text-label-md font-semibold text-on-primary disabled:opacity-50"
            >
              {saving ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Criar `StepFormModal.tsx`**

```tsx
// apps/web/src/features/followup/components/StepFormModal.tsx
"use client";

import { useState } from "react";
import type { CreateStepDto, FollowupStep, UpdateStepDto } from "../types";

interface Props {
  step?: FollowupStep;
  nextPosition: number;
  onSave: (dto: CreateStepDto | UpdateStepDto) => Promise<void>;
  onClose: () => void;
}

export function StepFormModal({ step, nextPosition, onSave, onClose }: Props) {
  const [delay, setDelay] = useState(step?.delay_from_purchase_hours ?? 0);
  const [templateName, setTemplateName] = useState(step?.meta_template_name ?? "");
  const [position, setPosition] = useState(step?.position ?? nextPosition);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave({
        position,
        delay_from_purchase_hours: delay,
        meta_template_name: templateName,
        template_variables: step?.template_variables ?? {},
      });
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-scrim/60">
      <div className="w-full max-w-md rounded-2xl bg-surface-container-low p-6 shadow-xl">
        <h2 className="mb-4 text-title-md font-semibold text-on-surface">
          {step ? "Editar Step" : "Novo Step"}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-label-sm text-on-surface-variant mb-1">
              Nome do template Meta
            </label>
            <input
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              required
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="ex: mv_boas_vindas"
            />
          </div>
          <div>
            <label className="block text-label-sm text-on-surface-variant mb-1">
              Delay após a compra (horas)
            </label>
            <input
              type="number"
              min={0}
              value={delay}
              onChange={(e) => setDelay(Number(e.target.value))}
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <p className="mt-1 text-label-sm text-on-surface-variant">
              0h = imediato, 24h = dia 1, 48h = dia 2...
            </p>
          </div>
          <div>
            <label className="block text-label-sm text-on-surface-variant mb-1">Posição</label>
            <input
              type="number"
              min={1}
              value={position}
              onChange={(e) => setPosition(Number(e.target.value))}
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-label-md text-on-surface-variant hover:bg-surface-container-high">
              Cancelar
            </button>
            <button type="submit" disabled={saving} className="rounded-lg bg-primary px-4 py-2 text-label-md font-semibold text-on-primary disabled:opacity-50">
              {saving ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/followup/components/DelayBadge.tsx \
        apps/web/src/features/followup/components/FlowFormModal.tsx \
        apps/web/src/features/followup/components/StepFormModal.tsx
git commit -m "feat(followup-ui): componentes DelayBadge e modais de formulário"
```

---

### Task 5: Componentes de lista

**Files:**
- Create: `apps/web/src/features/followup/components/FlowCard.tsx`
- Create: `apps/web/src/features/followup/components/StepItem.tsx`
- Create: `apps/web/src/features/followup/components/StepList.tsx`

- [ ] **Step 1: Criar `FlowCard.tsx`**

```tsx
// apps/web/src/features/followup/components/FlowCard.tsx
"use client";

import Link from "next/link";
import type { FollowupFlow, UpdateFlowDto } from "../types";

interface Props {
  flow: FollowupFlow;
  onEdit: () => void;
  onToggle: (dto: UpdateFlowDto) => Promise<void>;
  onDelete: () => Promise<void>;
}

export function FlowCard({ flow, onEdit, onToggle, onDelete }: Props) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-outline-variant bg-surface-container-low px-5 py-4">
      <div className="flex items-center gap-3">
        <span
          className={`h-2.5 w-2.5 rounded-full ${flow.is_active ? "bg-success" : "bg-on-surface-variant"}`}
        />
        <div>
          <Link href={`/followup/${flow.id}`} className="text-body-md font-semibold text-on-surface hover:text-primary">
            {flow.name}
          </Link>
          <p className="text-label-sm text-on-surface-variant">
            Tags: {flow.product_tags.join(", ") || "—"}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onEdit}
          className="rounded-lg px-3 py-1.5 text-label-sm text-on-surface-variant hover:bg-surface-container-high"
        >
          Editar
        </button>
        <button
          onClick={() => onToggle({ is_active: !flow.is_active })}
          className="rounded-lg px-3 py-1.5 text-label-sm text-on-surface-variant hover:bg-surface-container-high"
        >
          {flow.is_active ? "Pausar" : "Ativar"}
        </button>
        <button
          onClick={() => {
            if (confirm(`Excluir flow "${flow.name}"?`)) onDelete();
          }}
          className="rounded-lg px-3 py-1.5 text-label-sm text-error hover:bg-error-container"
        >
          Excluir
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Criar `StepItem.tsx`**

```tsx
// apps/web/src/features/followup/components/StepItem.tsx
"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { DelayBadge } from "./DelayBadge";
import type { FollowupStep } from "../types";

interface Props {
  step: FollowupStep;
  onEdit: () => void;
  onDelete: () => Promise<void>;
}

export function StepItem({ step, onEdit, onDelete }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: step.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-3 rounded-xl border border-outline-variant bg-surface-container-low px-4 py-3"
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab text-on-surface-variant hover:text-on-surface"
        aria-label="Arrastar"
      >
        <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>
          drag_indicator
        </span>
      </button>
      <span className="w-6 text-center text-label-sm font-mono text-on-surface-variant">
        {step.position}
      </span>
      <DelayBadge hours={step.delay_from_purchase_hours} />
      <span className="flex-1 text-body-sm font-mono text-on-surface">
        {step.meta_template_name}
      </span>
      <div className="flex gap-2">
        <button
          onClick={onEdit}
          className="rounded-lg p-1.5 text-on-surface-variant hover:bg-surface-container-high"
          aria-label="Editar step"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>edit</span>
        </button>
        <button
          onClick={() => {
            if (confirm("Excluir este step?")) onDelete();
          }}
          className="rounded-lg p-1.5 text-error hover:bg-error-container"
          aria-label="Excluir step"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>delete</span>
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Criar `StepList.tsx` (drag-and-drop)**

```tsx
// apps/web/src/features/followup/components/StepList.tsx
"use client";

import { useState } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { StepItem } from "./StepItem";
import { StepFormModal } from "./StepFormModal";
import type { CreateStepDto, FollowupStep, UpdateStepDto } from "../types";

interface Props {
  steps: FollowupStep[];
  onReorder: (items: { id: string; position: number }[]) => Promise<void>;
  onCreate: (dto: CreateStepDto) => Promise<void>;
  onUpdate: (stepId: string, dto: UpdateStepDto) => Promise<void>;
  onDelete: (stepId: string) => Promise<void>;
}

export function StepList({ steps, onReorder, onCreate, onUpdate, onDelete }: Props) {
  const [editingStep, setEditingStep] = useState<FollowupStep | null>(null);
  const [addingStep, setAddingStep] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = steps.findIndex((s) => s.id === active.id);
    const newIndex = steps.findIndex((s) => s.id === over.id);
    const reordered = arrayMove(steps, oldIndex, newIndex);
    const items = reordered.map((s, i) => ({ id: s.id, position: i + 1 }));
    await onReorder(items);
  }

  return (
    <div className="space-y-2">
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={steps.map((s) => s.id)} strategy={verticalListSortingStrategy}>
          {steps.map((step) => (
            <StepItem
              key={step.id}
              step={step}
              onEdit={() => setEditingStep(step)}
              onDelete={() => onDelete(step.id)}
            />
          ))}
        </SortableContext>
      </DndContext>

      <button
        onClick={() => setAddingStep(true)}
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-outline-variant px-4 py-3 text-label-md text-on-surface-variant hover:border-primary hover:text-primary"
      >
        <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>add</span>
        Adicionar Step
      </button>

      {addingStep && (
        <StepFormModal
          nextPosition={steps.length + 1}
          onSave={async (dto) => { await onCreate(dto as CreateStepDto); }}
          onClose={() => setAddingStep(false)}
        />
      )}

      {editingStep && (
        <StepFormModal
          step={editingStep}
          nextPosition={editingStep.position}
          onSave={async (dto) => { await onUpdate(editingStep.id, dto as UpdateStepDto); }}
          onClose={() => setEditingStep(null)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/followup/components/
git commit -m "feat(followup-ui): componentes FlowCard, StepItem e StepList"
```

---

### Task 6: Páginas

**Files:**
- Create: `apps/web/src/app/(admin)/followup/page.tsx`
- Create: `apps/web/src/app/(admin)/followup/[id]/page.tsx`

- [ ] **Step 1: Criar página de listagem `/followup`**

```tsx
// apps/web/src/app/(admin)/followup/page.tsx
"use client";

import { useState } from "react";
import { useFollowupFlows } from "@/features/followup/hooks/useFollowupFlows";
import { FlowCard } from "@/features/followup/components/FlowCard";
import { FlowFormModal } from "@/features/followup/components/FlowFormModal";
import { useToast } from "@/shared/hooks/useToast";

export default function FollowupPage() {
  const { flows, loading, error, create, update, remove } = useFollowupFlows();
  const [showCreate, setShowCreate] = useState(false);
  const [editingFlow, setEditingFlow] = useState<(typeof flows)[0] | null>(null);
  const toast = useToast();

  if (loading) return <div className="flex h-full items-center justify-center text-on-surface-variant">Carregando...</div>;
  if (error) return <div className="p-6 text-error">{error}</div>;

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-headline-sm font-bold text-on-surface">Follow-up Flows</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-label-md font-semibold text-on-primary hover:opacity-90"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>add</span>
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
              onToggle={async (dto) => {
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
          onSave={async (dto) => {
            try {
              await create(dto as Parameters<typeof create>[0]);
              toast.success("Flow criado");
            } catch {
              toast.error("Erro ao criar flow");
              throw dto;
            }
          }}
          onClose={() => setShowCreate(false)}
        />
      )}

      {editingFlow && (
        <FlowFormModal
          flow={editingFlow}
          onSave={async (dto) => {
            try {
              await update(editingFlow.id, dto);
              toast.success("Flow atualizado");
            } catch {
              toast.error("Erro ao atualizar flow");
              throw dto;
            }
          }}
          onClose={() => setEditingFlow(null)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Criar página de detalhe `/followup/[id]`**

```tsx
// apps/web/src/app/(admin)/followup/[id]/page.tsx
"use client";

import Link from "next/link";
import { use } from "react";
import { useFollowupSteps } from "@/features/followup/hooks/useFollowupSteps";
import { StepList } from "@/features/followup/components/StepList";
import { useToast } from "@/shared/hooks/useToast";

export default function FollowupFlowDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { steps, loading, error, create, update, remove, reorder } = useFollowupSteps(id);
  const toast = useToast();

  if (loading) return <div className="flex h-full items-center justify-center text-on-surface-variant">Carregando...</div>;
  if (error) return <div className="p-6 text-error">{error}</div>;

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-center gap-3">
        <Link href="/followup" className="text-on-surface-variant hover:text-on-surface">
          <span className="material-symbols-outlined" style={{ fontSize: "22px" }}>arrow_back</span>
        </Link>
        <h1 className="text-headline-sm font-bold text-on-surface">Steps do Flow</h1>
      </div>

      <StepList
        steps={steps}
        onReorder={async (items) => {
          try {
            await reorder(items);
            toast.success("Ordem atualizada");
          } catch {
            toast.error("Erro ao reordenar");
          }
        }}
        onCreate={async (dto) => {
          try {
            await create(dto);
            toast.success("Step adicionado");
          } catch {
            toast.error("Erro ao adicionar step");
          }
        }}
        onUpdate={async (stepId, dto) => {
          try {
            await update(stepId, dto);
            toast.success("Step atualizado");
          } catch {
            toast.error("Erro ao atualizar step");
          }
        }}
        onDelete={async (stepId) => {
          try {
            await remove(stepId);
            toast.success("Step excluído");
          } catch {
            toast.error("Erro ao excluir step");
          }
        }}
      />
    </div>
  );
}
```

- [ ] **Step 3: Adicionar item "Follow-up" na Sidebar**

Em `apps/web/src/shared/components/layout/Sidebar.tsx`, no array `NAV_ITEMS`, adicionar:

```typescript
  { label: "Follow-up", href: "/followup", icon: "schedule_send" },
```

- [ ] **Step 4: Verificar build**

```bash
cd apps/web && npm run build 2>&1 | tail -20
```
Esperado: sem erros

- [ ] **Step 5: Rodar lint**

```bash
cd apps/web && npm run lint
```
Corrigir qualquer erro.

- [ ] **Step 6: Commit final**

```bash
git add apps/web/src/app/\(admin\)/followup/ \
        apps/web/src/shared/components/layout/Sidebar.tsx
git commit -m "feat(followup-ui): páginas /followup e /followup/[id] com drag-and-drop"
```
