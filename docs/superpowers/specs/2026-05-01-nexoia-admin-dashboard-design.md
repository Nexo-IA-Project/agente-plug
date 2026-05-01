# NexoIA Admin Dashboard — Design Spec

## Objetivo

Refatorar o frontend `apps/web` para seguir o design system NexoIA (paleta, tipografia, espaçamento), implementar as 3 páginas do painel admin (Dashboard, KB Admin, Accounts) com arquitetura Feature Modules, suporte a tema dark/light e sistema de toast.

---

## Stack

- **Next.js 15** (App Router, TypeScript)
- **Tailwind CSS** — tokens NexoIA completos
- **shadcn/ui** — componentes base headless
- **next-themes** — dark/light sem SSR flash
- **sonner** — toasts modernos (success, error, warning, info)
- **Recharts** — gráfico de barras no dashboard
- **Material Symbols Outlined** — ícones via CDN no layout

---

## Estrutura de Arquivos

```
apps/web/src/
  app/
    layout.tsx              ← ThemeProvider + ToastProvider (Toaster sonner)
    page.tsx                ← redirect → /dashboard
    dashboard/page.tsx
    kb/page.tsx             ← lista de documentos (mantida, não alterada neste escopo)
    kb/upload/page.tsx
    accounts/page.tsx

  features/
    dashboard/
      components/
        KpiCard.tsx
        ConversationsChart.tsx
        ModelHealthCard.tsx
        SkillsTable.tsx
      data/
        dashboardMocks.ts
      types.ts

    kb/
      components/
        Dropzone.tsx
        FileList.tsx
        FileItem.tsx
        UploadProgress.tsx
      data/
        kbMocks.ts
      types.ts

    accounts/
      components/
        ComingSoon.tsx

  shared/
    components/
      ui/                   ← shadcn existente (Button, Badge, Card...) — sem mudança de conteúdo
      layout/
        Sidebar.tsx          ← substitui src/components/sidebar.tsx
        TopBar.tsx
        ThemeToggle.tsx
      toast/
        ToastProvider.tsx
    hooks/
      useToast.ts

  lib/                      ← mantido em src/lib/ (não movido)
    api.ts
    utils.ts
  types/                    ← mantido em src/types/ (não movido)
    api.ts
```

---

## Design System

### Paleta de Cores (tokens Tailwind)

| Token | Valor |
|---|---|
| `surface` | `#131315` |
| `surface-dim` | `#131315` |
| `surface-container-lowest` | `#0e0e10` |
| `surface-container-low` | `#1b1b1d` |
| `surface-container` | `#1f1f21` |
| `surface-container-high` | `#2a2a2b` |
| `surface-container-highest` | `#353436` |
| `surface-bright` | `#39393b` |
| `surface-variant` | `#353436` |
| `on-surface` | `#e4e2e4` |
| `on-surface-variant` | `#c6c6cd` |
| `outline` | `#909097` |
| `outline-variant` | `#45464d` |
| `primary` | `#bec6e0` |
| `on-primary` | `#283044` |
| `primary-container` | `#0f172a` |
| `on-primary-container` | `#798098` |
| `secondary` | `#b7c8e1` |
| `secondary-container` | `#3a4a5f` |
| `tertiary` | `#dec29a` |
| `tertiary-container` | `#231500` |
| `error` | `#ffb4ab` |
| `error-container` | `#93000a` |
| `background` | `#131315` |
| `on-background` | `#e4e2e4` |
| `inverse-surface` | `#e4e2e4` |
| `inverse-on-surface` | `#303032` |

### Tipografia

| Token | Família | Tamanho | Peso | Line-height | Letter-spacing |
|---|---|---|---|---|---|
| `h1` | Plus Jakarta Sans | 36px | 700 | 1.2 | -0.02em |
| `h2` | Plus Jakarta Sans | 24px | 600 | 1.3 | -0.01em |
| `body-base` | Plus Jakarta Sans | 16px | 400 | 1.6 | 0 |
| `body-sm` | Plus Jakarta Sans | 14px | 400 | 1.5 | 0 |
| `label-caps` | Plus Jakarta Sans | 12px | 600 | 1 | 0.05em |
| `mono-label` | Inter | 13px | 500 | 1 | 0 |

### Border Radius

| Token | Valor |
|---|---|
| `DEFAULT` | `0.25rem` |
| `lg` | `0.5rem` |
| `xl` | `0.75rem` |
| `full` | `9999px` |

### Spacing

- `gutter`: 24px
- `card-padding`: 24px
- `input-padding`: 12px
- `container-max`: 1280px

---

## Tema Dark/Light

- `next-themes` com `defaultTheme="dark"` e `attribute="class"`
- `suppressHydrationWarning` no `<html>` para evitar SSR flash
- `ThemeToggle` no `TopBar`: ícone `light_mode` / `dark_mode` (Material Symbols)
- Dark mode: usa tokens `surface-*` do design system
- Light mode: usa escala `slate-*` (slate-50 background, white cards, slate-800 borders)

---

## Sistema de Toast (Sonner)

`ToastProvider.tsx` renderiza `<Toaster />` do sonner com tema customizado seguindo o design system.

`useToast.ts` expõe:

```ts
const toast = useToast()
toast.success("Arquivo indexado com sucesso")
toast.error("Erro de leitura do arquivo")
toast.warning("Arquivo excede o tamanho recomendado")
toast.info("Processamento iniciado")
```

Estilo padrão: fundo `surface-container-high`, borda `outline-variant`, texto `on-surface`. Posição: `bottom-right`.

---

## Componentes por Página

### Layout Compartilhado

**`Sidebar`**
- Largura fixa: 240px, height: 100vh, `position: fixed`
- Header: ícone `psychology` (Material Symbols, FILL=1) + "NexoIA" (h1-bold) + "AI Agent Platform" (body-sm, on-surface-variant)
- Navegação: Dashboard, Base de Conhecimento, Contas
- Estado ativo: `bg-slate-100 dark:bg-slate-900`, texto bold, ícone filled
- Footer: Configurações, Suporte
- Borda direita: 1px `outline-variant`

**`TopBar`**
- Height: 64px, `position: sticky`, `backdrop-blur-md`, `bg-white/80 dark:bg-surface/80`
- Esquerda: input de busca com ícone `search`
- Direita: botão notifications (com badge de ponto), botão help, avatar, `ThemeToggle`

---

### Dashboard (`/dashboard`)

**`KpiCard`** — props: `title`, `value`, `icon`, `trend?: { value, direction, label }`
- Container: `bg-surface-container border border-outline-variant rounded-xl p-card-padding h-[140px]`
- Label: `label-caps` uppercase
- Valor: `h2` bold
- Trend: verde para `up`/positivo em taxa de escalação down, vermelho para negativo, neutro para estável

**4 KPIs mockados:**
1. Total de Conversas — 12.405 — `+14%` up
2. Taxa de Resolução IA — 86.2% — `+2.1%` up
3. Taxa de Escalação — 13.8% — `-1.5%` down (verde = bom)
4. Média de Turnos — 3.4 — Estável

**`ConversationsChart`** — Recharts `ResponsiveContainer` + `BarChart`
- Dados: Seg→Dom com valores mockados
- Cor das barras: `primary` (#bec6e0)
- Eixos: `XAxis` + `YAxis` com estilo `on-surface-variant`
- Tooltip customizado com fundo `surface-container-high`
- Grid: linhas horizontais dashed `outline-variant`

**`ModelHealthCard`** — card col-span-4 (de 12)
- 2 progress bars: CPU 42%, Latência 20% (124ms)
- Barra CPU: cor `primary`, barra Latência: cor `secondary`
- Fundo das barras: `surface`

**`SkillsTable`** — tabela sem bordas verticais
- Colunas: Nome, Contagem, Porcentagem
- Headers: `label-caps` uppercase
- Última coluna: valor % + mini progress bar inline (w-16, h-1)
- Row hover: `bg-surface-variant/30`

---

### KB Admin (`/kb/upload`)

**`Dropzone`**
- Área dashed: `border-2 border-dashed border-outline-variant`, `rounded-xl`
- Drag-over: `border-primary`
- `<input type="file">` invisible sobre toda a área (inset-0, opacity-0, z-10)
- Aceita: `.pdf,.docx,.txt`
- Ícone `cloud_upload` + textos + badges de formato (PDF, DOCX, TXT)
- Ao soltar arquivo mockado: dispara `toast.success("Arquivo enviado para processamento")`

**`UploadProgress`** — exibido abaixo do dropzone durante upload
- Nome do arquivo + porcentagem + barra de progresso
- Cor: `primary`

**`FileItem`** — 3 estados:
- `indexed`: ícone `check_circle` (primary), badge "INDEXADO" (primary/10 bg)
- `error`: borda `error/30`, ícone `warning`, texto riscado, botão `refresh` → `toast.info("Tentando novamente...")`
- `processing`: spinner inline

**`FileList`** — painel lateral 320px com lista de `FileItem`s e contador no header

---

### Accounts (`/accounts`)

**`ComingSoon`**
- Card centralizado: `max-w-lg`, ícone `construction`, label "EM BREVE" (label-caps primary), título h1, descrição body-base, botão "Voltar ao Dashboard"
- Botão usa `router.push('/dashboard')`

---

## Dados Mockados

### `dashboardMocks.ts`

```ts
export const kpiData: KpiMetric[] = [...]
export const chartData: DayData[] = [
  { day: 'Seg', count: 800 },
  { day: 'Ter', count: 1200 },
  ...
]
export const skillsData: SkillMetric[] = [...]
export const modelHealthData: ModelHealth = {
  cpuUsage: 42,
  avgLatencyMs: 124,
  status: 'healthy',
}
```

### `kbMocks.ts`

```ts
export const processedFiles: KbFile[] = [
  { id: '1', name: 'manuais_tecnicos_v2.docx', size: '2.4 MB', status: 'indexed' },
  { id: '2', name: 'politicas_RH_2023.pdf', size: '1.1 MB', status: 'indexed' },
  { id: '3', name: 'log_servidor_corrompido.txt', size: '0.3 MB', status: 'error' },
  { id: '4', name: 'atas_reuniao_diretoria.pdf', size: '5.7 MB', status: 'indexed' },
]
```

---

## O que NÃO muda

- `lib/api.ts` — cliente HTTP existente mantido
- `types/api.ts` — tipos de API existentes mantidos
- `lib/utils.ts` — função `cn()` mantida
- Migrations, backend, workers — zero mudança

---

## Dependências novas

```bash
pnpm add next-themes sonner
```

(Recharts já está instalado)

---

## Ordem de Implementação

1. Instalar `next-themes` e `sonner`
2. Atualizar `tailwind.config.ts` com tokens NexoIA
3. Atualizar `globals.css` com variáveis light/dark
4. Atualizar `layout.tsx` — ThemeProvider + Toaster + Material Symbols CDN
5. Criar `shared/components/layout/` — Sidebar, TopBar, ThemeToggle
6. Criar `shared/hooks/useToast.ts`
7. Criar `features/dashboard/` — types, mocks, componentes, page
8. Criar `features/kb/` — types, mocks, componentes, page upload
9. Criar `features/accounts/` — ComingSoon, page
10. Remover componentes antigos substituídos
