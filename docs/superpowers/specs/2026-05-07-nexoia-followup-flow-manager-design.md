# NexoIA — Follow-up Flow Manager: Tela de Gestão de Fluxos

**Data:** 2026-05-07  
**Status:** Aprovado  
**Subsistema:** B — Follow-up Flow Manager (frontend)  
**Depende de:** Spec C (Follow-up Engine — API endpoints)

---

## Visão Geral

Implementar as telas de administração para criar, visualizar, editar, reordenar e deletar fluxos de follow-up e seus steps. Cada step referencia um template Meta aprovado pelo nome. O design segue o design system NexoIA (tokens CSS, Material Symbols, `useToast`).

---

## Requisitos Funcionais

| # | Requisito |
|---|-----------|
| RF-FM01 | Página `/followup` lista todos os flows do account com nome, tags de produto, status (ativo/pausado) e número de steps |
| RF-FM02 | Botão "Novo Flow" abre modal para informar nome e product tags |
| RF-FM03 | Cada flow tem ações: Editar nome/tags, Ativar/Pausar, Deletar (com confirmação) |
| RF-FM04 | Clicar num flow abre `/followup/[id]` com a lista de steps ordenada por `position` |
| RF-FM05 | Cada step exibe: posição, delay (formatado como "Dia X, Hora Y"), nome do template Meta |
| RF-FM06 | Steps podem ser reordenados por drag-and-drop; reorder chama `PATCH /admin/followup/flows/{id}/steps/reorder` |
| RF-FM07 | Botão "Adicionar Step" abre formulário inline com campos: delay_from_purchase_hours e meta_template_name |
| RF-FM08 | Cada step tem ações: Editar e Deletar (com confirmação) |
| RF-FM09 | Sidebar exibe item "Follow-up" com ícone `schedule_send` |
| RF-FM10 | Toasts de sucesso/erro em todas as operações |
| RF-FM11 | Delay exibido de forma legível: `delay_from_purchase_hours` → "Imediato", "1h após compra", "Dia 1 (24h)", "Dia 2 (48h)", etc. |

## Requisitos Não-Funcionais

| # | Requisito |
|---|-----------|
| RNF-FM01 | Feature module em `src/features/followup/` com `components/`, `types.ts`, `hooks/` |
| RNF-FM02 | Design system NexoIA: tokens semânticos (`bg-surface-container`, `text-on-surface`), sem hex hardcoded |
| RNF-FM03 | Drag-and-drop via `@dnd-kit/core` (já disponível no ecossistema Next.js — adicionar se ausente) |
| RNF-FM04 | Funções de API em `src/lib/api.ts` seguindo o padrão de `getAccountSettings` / `updateAccountSettings` |
| RNF-FM05 | Página de detalhe usa `useParams` do Next.js App Router |

---

## Arquitetura Frontend

### Feature Module

```
apps/web/src/features/followup/
  types.ts                        ← FollowupFlow, FollowupStep, CreateFlowDto, CreateStepDto
  hooks/
    useFollowupFlows.ts            ← CRUD de flows (GET/POST/PUT/DELETE)
    useFollowupSteps.ts            ← CRUD de steps + reorder
  components/
    FlowList.tsx                   ← lista de flows com ações
    FlowCard.tsx                   ← card individual do flow
    FlowFormModal.tsx              ← modal criar/editar flow
    StepList.tsx                   ← lista de steps com drag-and-drop
    StepItem.tsx                   ← item individual do step
    StepFormModal.tsx              ← modal criar/editar step
    DelayBadge.tsx                 ← formata delay_from_purchase_hours → texto legível
```

### Páginas

```
apps/web/src/app/(admin)/followup/
  page.tsx                         ← lista de flows (RF-FM01..03)
  [id]/
    page.tsx                       ← detalhe do flow com steps (RF-FM04..08)
```

### Tipos

```typescript
// features/followup/types.ts
export interface FollowupFlow {
  id: string;
  name: string;
  product_tags: string[];
  is_active: boolean;
  step_count: number;
  created_at: string;
}

export interface FollowupStep {
  id: string;
  flow_id: string;
  position: number;
  delay_from_purchase_hours: number;
  meta_template_name: string;
  template_variables: Record<string, string>;
}

export type CreateFlowDto = Pick<FollowupFlow, "name" | "product_tags">;
export type CreateStepDto = Pick<FollowupStep, "delay_from_purchase_hours" | "meta_template_name" | "template_variables">;
```

### Delay legível (helper)

```typescript
// features/followup/components/DelayBadge.tsx
export function formatDelay(hours: number): string {
  if (hours === 0) return "Imediato";
  if (hours < 24) return `${hours}h após compra`;
  const days = Math.floor(hours / 24);
  const rem = hours % 24;
  return rem === 0 ? `Dia ${days}` : `Dia ${days} +${rem}h`;
}
```

---

## Wireframe Conceitual

### `/followup` — Lista de Flows

```
┌─────────────────────────────────────────────────────┐
│ Follow-up Flows                    [+ Novo Flow]     │
│─────────────────────────────────────────────────────│
│ ● Máquina de Vendas                                  │
│   Tags: maquina_de_vendas  •  8 steps  •  Ativo     │
│                           [Editar] [Pausar] [Excluir]│
│─────────────────────────────────────────────────────│
│ ○ Produto X                                          │
│   Tags: produto_x  •  3 steps  •  Pausado           │
│                           [Editar] [Ativar] [Excluir]│
└─────────────────────────────────────────────────────┘
```

### `/followup/[id]` — Detalhe do Flow

```
┌─────────────────────────────────────────────────────┐
│ ← Máquina de Vendas                [+ Adicionar Step]│
│─────────────────────────────────────────────────────│
│ ⠿  1  │ Imediato      │ mv_boas_vindas    [✎] [🗑]  │
│ ⠿  2  │ 1h após compra│ mv_link_aula      [✎] [🗑]  │
│ ⠿  3  │ Dia 1         │ mv_depoimento     [✎] [🗑]  │
│ ⠿  4  │ Dia 1 +1h     │ mv_numeros_aviso  [✎] [🗑]  │
│ ⠿  5  │ Dia 2         │ mv_dica_produto   [✎] [🗑]  │
│ ⠿  6  │ Dia 4         │ mv_check_in       [✎] [🗑]  │
│ ⠿  7  │ Dia 9         │ mv_pesquisa_10    [✎] [🗑]  │
│ ⠿  8  │ Dia 29        │ mv_pesquisa_30    [✎] [🗑]  │
│ ⠿ = drag handle                                      │
└─────────────────────────────────────────────────────┘
```

---

## Arquivos

### Novos
```
apps/web/src/features/followup/types.ts
apps/web/src/features/followup/hooks/useFollowupFlows.ts
apps/web/src/features/followup/hooks/useFollowupSteps.ts
apps/web/src/features/followup/components/FlowList.tsx
apps/web/src/features/followup/components/FlowCard.tsx
apps/web/src/features/followup/components/FlowFormModal.tsx
apps/web/src/features/followup/components/StepList.tsx
apps/web/src/features/followup/components/StepItem.tsx
apps/web/src/features/followup/components/StepFormModal.tsx
apps/web/src/features/followup/components/DelayBadge.tsx
apps/web/src/app/(admin)/followup/page.tsx
apps/web/src/app/(admin)/followup/[id]/page.tsx
```

### Modificados
```
apps/web/src/shared/components/layout/Sidebar.tsx   + item "Follow-up" (schedule_send)
apps/web/src/lib/api.ts                             + funções de follow-up API
```

---

## Fora de Escopo

- Visualização de enrollments ativos (quem está em qual step) → v2
- Preview do template Meta na tela → depende do Spec A
- Relatório de disparos → v2
