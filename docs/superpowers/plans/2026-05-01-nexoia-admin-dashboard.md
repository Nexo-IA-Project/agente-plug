# NexoIA Admin Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `apps/web` ao design system NexoIA com Feature Modules, tema dark/light, toasts e as 3 páginas do painel admin.

**Architecture:** Feature Modules — cada domínio em `src/features/<domain>/` com componentes, tipos e mocks próprios. Layout compartilhado em `src/shared/components/layout/`. Tokens Tailwind referenciam CSS variables que trocam entre light/dark via `next-themes`.

**Tech Stack:** Next.js 15 App Router, Tailwind CSS v3, next-themes, sonner, Recharts, Material Symbols Outlined (CSS import), TypeScript

---

### Task 1: Instalar dependências

**Files:**
- Modify: `apps/web/package.json`

- [ ] **Step 1: Instalar next-themes e sonner**

```bash
cd apps/web && npm install next-themes sonner
```

- [ ] **Step 2: Verificar instalação**

```bash
grep -E '"next-themes|"sonner' apps/web/package.json
```

Expected: ambas as linhas presentes.

- [ ] **Step 3: Commit**

```bash
git add apps/web/package.json apps/web/package-lock.json
git commit -m "chore(web): add next-themes and sonner"
```

---

### Task 2: Atualizar tailwind.config.ts com tokens NexoIA

**Files:**
- Modify: `apps/web/tailwind.config.ts`

- [ ] **Step 1: Substituir tailwind.config.ts**

```ts
// apps/web/tailwind.config.ts
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/features/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/shared/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: "var(--color-surface)",
        "surface-dim": "var(--color-surface-dim)",
        "surface-container-lowest": "var(--color-surface-container-lowest)",
        "surface-container-low": "var(--color-surface-container-low)",
        "surface-container": "var(--color-surface-container)",
        "surface-container-high": "var(--color-surface-container-high)",
        "surface-container-highest": "var(--color-surface-container-highest)",
        "surface-bright": "var(--color-surface-bright)",
        "surface-variant": "var(--color-surface-variant)",
        "on-surface": "var(--color-on-surface)",
        "on-surface-variant": "var(--color-on-surface-variant)",
        outline: "var(--color-outline)",
        "outline-variant": "var(--color-outline-variant)",
        primary: "var(--color-primary)",
        "on-primary": "var(--color-on-primary)",
        "primary-container": "var(--color-primary-container)",
        "on-primary-container": "var(--color-on-primary-container)",
        secondary: "var(--color-secondary)",
        "on-secondary": "var(--color-on-secondary)",
        "secondary-container": "var(--color-secondary-container)",
        error: "var(--color-error)",
        "on-error": "var(--color-on-error)",
        "error-container": "var(--color-error-container)",
        background: "var(--color-background)",
        "on-background": "var(--color-on-background)",
        // shadcn compat
        border: "var(--color-outline-variant)",
        input: "var(--color-outline-variant)",
        ring: "var(--color-primary)",
        foreground: "var(--color-on-surface)",
        muted: {
          DEFAULT: "var(--color-surface-container)",
          foreground: "var(--color-on-surface-variant)",
        },
        card: {
          DEFAULT: "var(--color-surface-container)",
          foreground: "var(--color-on-surface)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      fontSize: {
        h1: ["36px", { lineHeight: "1.2", letterSpacing: "-0.02em", fontWeight: "700" }],
        h2: ["24px", { lineHeight: "1.3", letterSpacing: "-0.01em", fontWeight: "600" }],
        "body-base": ["16px", { lineHeight: "1.6", letterSpacing: "0em", fontWeight: "400" }],
        "body-sm": ["14px", { lineHeight: "1.5", letterSpacing: "0em", fontWeight: "400" }],
        "label-caps": ["12px", { lineHeight: "1", letterSpacing: "0.05em", fontWeight: "600" }],
        "mono-label": ["13px", { lineHeight: "1", letterSpacing: "0em", fontWeight: "500" }],
      },
      borderRadius: {
        DEFAULT: "0.25rem",
        lg: "0.5rem",
        xl: "0.75rem",
        full: "9999px",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      spacing: {
        gutter: "24px",
        "card-padding": "24px",
        "input-padding": "12px",
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/tailwind.config.ts
git commit -m "chore(web): update tailwind config with NexoIA design tokens"
```

---

### Task 3: Atualizar globals.css com CSS variables e fontes

**Files:**
- Modify: `apps/web/src/app/globals.css`

- [ ] **Step 1: Substituir globals.css**

```css
/* apps/web/src/app/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block');

.material-symbols-outlined {
  font-family: 'Material Symbols Outlined';
  font-weight: normal;
  font-style: normal;
  font-size: 20px;
  line-height: 1;
  letter-spacing: normal;
  text-transform: none;
  display: inline-block;
  white-space: nowrap;
  direction: ltr;
  -webkit-font-smoothing: antialiased;
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
}

/* ── Light mode ─────────────────────────────────────────────────────────── */
:root {
  --color-surface: #ffffff;
  --color-surface-dim: #f8fafc;
  --color-surface-container-lowest: #ffffff;
  --color-surface-container-low: #f8fafc;
  --color-surface-container: #f1f5f9;
  --color-surface-container-high: #e2e8f0;
  --color-surface-container-highest: #cbd5e1;
  --color-surface-bright: #ffffff;
  --color-surface-variant: #e2e8f0;
  --color-on-surface: #0f172a;
  --color-on-surface-variant: #475569;
  --color-outline: #94a3b8;
  --color-outline-variant: #e2e8f0;
  --color-primary: #3b4b6e;
  --color-on-primary: #ffffff;
  --color-primary-container: #dae2fd;
  --color-on-primary-container: #0f172a;
  --color-secondary: #4a6a8a;
  --color-on-secondary: #ffffff;
  --color-secondary-container: #dbeafe;
  --color-error: #dc2626;
  --color-on-error: #ffffff;
  --color-error-container: #fee2e2;
  --color-background: #f8fafc;
  --color-on-background: #0f172a;
  --radius: 0.25rem;
}

/* ── Dark mode ──────────────────────────────────────────────────────────── */
.dark {
  --color-surface: #131315;
  --color-surface-dim: #131315;
  --color-surface-container-lowest: #0e0e10;
  --color-surface-container-low: #1b1b1d;
  --color-surface-container: #1f1f21;
  --color-surface-container-high: #2a2a2b;
  --color-surface-container-highest: #353436;
  --color-surface-bright: #39393b;
  --color-surface-variant: #353436;
  --color-on-surface: #e4e2e4;
  --color-on-surface-variant: #c6c6cd;
  --color-outline: #909097;
  --color-outline-variant: #45464d;
  --color-primary: #bec6e0;
  --color-on-primary: #283044;
  --color-primary-container: #0f172a;
  --color-on-primary-container: #798098;
  --color-secondary: #b7c8e1;
  --color-on-secondary: #213145;
  --color-secondary-container: #3a4a5f;
  --color-error: #ffb4ab;
  --color-on-error: #690005;
  --color-error-container: #93000a;
  --color-background: #131315;
  --color-on-background: #e4e2e4;
  --radius: 0.25rem;
}

@layer base {
  * { @apply border-border; }
  body { @apply bg-background text-foreground font-sans antialiased; }
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/app/globals.css
git commit -m "chore(web): add NexoIA CSS variables and Material Symbols import"
```

---

### Task 4: Criar Providers (ThemeProvider + Toaster)

**Files:**
- Create: `apps/web/src/shared/components/providers.tsx`

- [ ] **Step 1: Criar providers.tsx**

```tsx
// apps/web/src/shared/components/providers.tsx
"use client";

import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} disableTransitionOnChange>
      {children}
      <Toaster
        position="bottom-right"
        toastOptions={{
          classNames: {
            toast:
              "bg-[var(--color-surface-container-high)] border border-[var(--color-outline-variant)] text-[var(--color-on-surface)] font-sans text-sm rounded-lg shadow-none",
            title: "text-[var(--color-on-surface)] font-semibold",
            description: "text-[var(--color-on-surface-variant)]",
            success: "!border-l-4 !border-l-green-500",
            error: "!border-l-4 !border-l-[var(--color-error)]",
            warning: "!border-l-4 !border-l-amber-400",
            info: "!border-l-4 !border-l-[var(--color-secondary)]",
          },
        }}
      />
    </ThemeProvider>
  );
}
```

---

### Task 5: Criar ThemeToggle

**Files:**
- Create: `apps/web/src/shared/components/layout/ThemeToggle.tsx`

- [ ] **Step 1: Criar ThemeToggle.tsx**

```tsx
// apps/web/src/shared/components/layout/ThemeToggle.tsx
"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="h-9 w-9" />;

  const isDark = theme === "dark";

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Mudar para tema claro" : "Mudar para tema escuro"}
      className="flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
    >
      <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>
        {isDark ? "light_mode" : "dark_mode"}
      </span>
    </button>
  );
}
```

---

### Task 6: Criar TopBar

**Files:**
- Create: `apps/web/src/shared/components/layout/TopBar.tsx`

- [ ] **Step 1: Criar TopBar.tsx**

```tsx
// apps/web/src/shared/components/layout/TopBar.tsx
import { ThemeToggle } from "./ThemeToggle";

export function TopBar() {
  return (
    <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-outline-variant bg-surface/80 backdrop-blur-md px-8">
      <div className="relative flex max-w-sm flex-1 items-center">
        <span className="material-symbols-outlined absolute left-3 text-on-surface-variant" style={{ fontSize: "18px" }}>
          search
        </span>
        <input
          type="text"
          placeholder="Buscar..."
          className="w-full rounded-lg border border-outline-variant bg-surface-container py-2 pl-10 pr-4 text-body-sm text-on-surface placeholder:text-on-surface-variant outline-none focus:ring-2 focus:ring-primary transition-all"
        />
      </div>

      <div className="flex items-center gap-2">
        <button className="relative flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors">
          <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>notifications</span>
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-primary" />
        </button>
        <button className="flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors">
          <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>help_outline</span>
        </button>
        <ThemeToggle />
        <div className="ml-2 flex h-8 w-8 items-center justify-center rounded-full border border-outline-variant bg-surface-container">
          <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: "16px" }}>person</span>
        </div>
      </div>
    </header>
  );
}
```

---

### Task 7: Criar Sidebar (substitui src/components/sidebar.tsx)

**Files:**
- Create: `apps/web/src/shared/components/layout/Sidebar.tsx`

- [ ] **Step 1: Criar Sidebar.tsx**

```tsx
// apps/web/src/shared/components/layout/Sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { label: "Painel", href: "/dashboard", icon: "dashboard" },
  { label: "Base de Conhecimento", href: "/kb", icon: "database" },
  { label: "Contas", href: "/accounts", icon: "group" },
] as const;

const FOOTER_ITEMS = [
  { label: "Configurações", href: "/settings", icon: "settings" },
  { label: "Suporte", href: "/support", icon: "contact_support" },
] as const;

function NavItem({ href, icon, label, active }: { href: string; icon: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2.5 text-body-sm transition-colors",
        active
          ? "bg-surface-container font-semibold text-on-surface"
          : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface"
      )}
    >
      <span
        className="material-symbols-outlined"
        style={{ fontSize: "20px", fontVariationSettings: active ? "'FILL' 1" : "'FILL' 0" }}
      >
        {icon}
      </span>
      {label}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-50 flex h-screen w-[240px] flex-col border-r border-outline-variant bg-surface-container-lowest">
      <div className="px-6 py-5">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary" style={{ fontSize: "22px", fontVariationSettings: "'FILL' 1" }}>
            psychology
          </span>
          <span className="text-lg font-bold tracking-tight text-on-surface">NexoIA</span>
        </div>
        <p className="mt-0.5 text-label-caps text-on-surface-variant">AI Agent Platform</p>
      </div>

      <nav className="flex-1 space-y-1 px-4">
        {NAV_ITEMS.map((item) => (
          <NavItem
            key={item.href}
            {...item}
            active={pathname === item.href || pathname.startsWith(item.href + "/")}
          />
        ))}
      </nav>

      <div className="space-y-1 border-t border-outline-variant px-4 py-4">
        {FOOTER_ITEMS.map((item) => (
          <NavItem key={item.href} {...item} active={pathname === item.href} />
        ))}
      </div>
    </aside>
  );
}
```

---

### Task 8: Atualizar layout.tsx + commit do bloco de layout

**Files:**
- Modify: `apps/web/src/app/layout.tsx`

- [ ] **Step 1: Substituir layout.tsx**

```tsx
// apps/web/src/app/layout.tsx
import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/shared/components/providers";
import { Sidebar } from "@/shared/components/layout/Sidebar";
import { TopBar } from "@/shared/components/layout/TopBar";

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
});

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "NexoIA Admin",
  description: "NexoIA AI Agent Administration Panel",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning className={`${plusJakartaSans.variable} ${inter.variable}`}>
      <body>
        <Providers>
          <div className="flex min-h-screen bg-background">
            <Sidebar />
            <div className="ml-[240px] flex flex-1 flex-col">
              <TopBar />
              <main className="flex-1 p-gutter">
                {children}
              </main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Verificar que o app sobe sem erros**

```bash
cd apps/web && npm run dev 2>&1 | head -20
```

Expected: `Ready in` sem erros de import.

- [ ] **Step 3: Commit bloco de layout (Tasks 4–8)**

```bash
git add apps/web/src/app/layout.tsx \
  apps/web/src/shared/components/providers.tsx \
  apps/web/src/shared/components/layout/ThemeToggle.tsx \
  apps/web/src/shared/components/layout/TopBar.tsx \
  apps/web/src/shared/components/layout/Sidebar.tsx
git commit -m "feat(web): add Providers, Sidebar, TopBar, ThemeToggle with dark/light theme"
```

---

### Task 9: Criar useToast hook

**Files:**
- Create: `apps/web/src/shared/hooks/useToast.ts`

- [ ] **Step 1: Criar useToast.ts**

```ts
// apps/web/src/shared/hooks/useToast.ts
import { toast as sonnerToast } from "sonner";

export function useToast() {
  return {
    success: (message: string, description?: string) =>
      sonnerToast.success(message, { description }),
    error: (message: string, description?: string) =>
      sonnerToast.error(message, { description }),
    warning: (message: string, description?: string) =>
      sonnerToast.warning(message, { description }),
    info: (message: string, description?: string) =>
      sonnerToast.info(message, { description }),
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/shared/hooks/useToast.ts
git commit -m "feat(web): add useToast hook wrapping sonner"
```

---

### Task 10: Dashboard — tipos e mocks

**Files:**
- Create: `apps/web/src/features/dashboard/types.ts`
- Create: `apps/web/src/features/dashboard/data/dashboardMocks.ts`

- [ ] **Step 1: Criar types.ts**

```ts
// apps/web/src/features/dashboard/types.ts

export type TrendDirection = "up" | "down" | "neutral";

export interface KpiMetric {
  id: string;
  title: string;
  value: string;
  icon: string;
  trend: {
    direction: TrendDirection;
    label: string;
    positiveIsDown?: boolean;
  };
}

export interface DayData {
  day: string;
  count: number;
}

export interface SkillMetric {
  id: string;
  name: string;
  icon: string;
  count: number;
  pct: number;
}

export interface ModelHealth {
  cpuUsage: number;
  avgLatencyMs: number;
  status: "healthy" | "degraded" | "down";
}
```

- [ ] **Step 2: Criar dashboardMocks.ts**

```ts
// apps/web/src/features/dashboard/data/dashboardMocks.ts
import type { KpiMetric, DayData, SkillMetric, ModelHealth } from "../types";

export const kpiData: KpiMetric[] = [
  {
    id: "total-conversations",
    title: "Total de Conversas",
    value: "12.405",
    icon: "chat_bubble",
    trend: { direction: "up", label: "+14% vs semana anterior" },
  },
  {
    id: "resolution-rate",
    title: "Taxa de Resolução IA",
    value: "86.2%",
    icon: "psychology_alt",
    trend: { direction: "up", label: "+2.1% vs semana anterior" },
  },
  {
    id: "escalation-rate",
    title: "Taxa de Escalação",
    value: "13.8%",
    icon: "support_agent",
    trend: { direction: "down", label: "-1.5% vs semana anterior", positiveIsDown: true },
  },
  {
    id: "avg-turns",
    title: "Média de Turnos",
    value: "3.4",
    icon: "forum",
    trend: { direction: "neutral", label: "Estável" },
  },
];

export const chartData: DayData[] = [
  { day: "Seg", count: 800 },
  { day: "Ter", count: 1200 },
  { day: "Qua", count: 1000 },
  { day: "Qui", count: 1700 },
  { day: "Sex", count: 1500 },
  { day: "Sáb", count: 600 },
  { day: "Dom", count: 1300 },
];

export const skillsData: SkillMetric[] = [
  { id: "1", name: "Consultar Fatura", icon: "receipt_long", count: 4205, pct: 33.9 },
  { id: "2", name: "Redefinir Senha", icon: "password", count: 2840, pct: 22.8 },
  { id: "3", name: "Cancelar Assinatura", icon: "cancel", count: 1520, pct: 12.2 },
  { id: "4", name: "Agendar Atendimento", icon: "schedule", count: 985, pct: 7.9 },
  { id: "5", name: "Dúvida sobre Produto", icon: "info", count: 740, pct: 5.9 },
];

export const modelHealthData: ModelHealth = {
  cpuUsage: 42,
  avgLatencyMs: 124,
  status: "healthy",
};
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/dashboard/types.ts \
  apps/web/src/features/dashboard/data/dashboardMocks.ts
git commit -m "feat(web/dashboard): add types and mock data"
```

---

### Task 11: KpiCard component

**Files:**
- Create: `apps/web/src/features/dashboard/components/KpiCard.tsx`

- [ ] **Step 1: Criar KpiCard.tsx**

```tsx
// apps/web/src/features/dashboard/components/KpiCard.tsx
import { cn } from "@/lib/utils";
import type { KpiMetric } from "../types";

function TrendBadge({ trend }: { trend: KpiMetric["trend"] }) {
  if (trend.direction === "neutral") {
    return (
      <div className="mt-1 flex items-center gap-1">
        <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: "14px" }}>
          horizontal_rule
        </span>
        <span className="text-mono-label font-mono text-on-surface-variant">{trend.label}</span>
      </div>
    );
  }

  const isGood =
    trend.positiveIsDown
      ? trend.direction === "down"
      : trend.direction === "up";

  const [trendValue, ...rest] = trend.label.split(" ");

  return (
    <div className="mt-1 flex items-center gap-1">
      <span
        className={cn("material-symbols-outlined", isGood ? "text-green-400" : "text-error")}
        style={{ fontSize: "14px" }}
      >
        {trend.direction === "up" ? "trending_up" : "trending_down"}
      </span>
      <span className={cn("text-mono-label font-mono", isGood ? "text-green-400" : "text-error")}>
        {trendValue}
      </span>
      <span className="ml-1 text-body-sm text-on-surface-variant">{rest.join(" ")}</span>
    </div>
  );
}

export function KpiCard({ metric }: { metric: KpiMetric }) {
  return (
    <div className="flex h-[140px] flex-col justify-between rounded-xl border border-outline-variant bg-surface-container p-card-padding">
      <div className="flex items-start justify-between">
        <span className="text-label-caps font-sans uppercase tracking-wider text-on-surface-variant">
          {metric.title}
        </span>
        <span className="material-symbols-outlined text-primary" style={{ fontSize: "22px" }}>
          {metric.icon}
        </span>
      </div>
      <div>
        <div className="text-h2 font-sans font-semibold text-on-surface">{metric.value}</div>
        <TrendBadge trend={metric.trend} />
      </div>
    </div>
  );
}
```

---

### Task 12: ConversationsChart component

**Files:**
- Create: `apps/web/src/features/dashboard/components/ConversationsChart.tsx`

- [ ] **Step 1: Criar ConversationsChart.tsx**

```tsx
// apps/web/src/features/dashboard/components/ConversationsChart.tsx
"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import type { DayData } from "../types";

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-outline-variant bg-surface-container-high px-3 py-2 text-body-sm shadow-none">
      <p className="font-medium text-on-surface">{label}</p>
      <p className="text-primary">{payload[0].value.toLocaleString("pt-BR")} conversas</p>
    </div>
  );
}

export function ConversationsChart({ data }: { data: DayData[] }) {
  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container p-card-padding">
      <div className="mb-6 flex items-center justify-between">
        <h3 className="text-h2 font-sans font-semibold text-on-surface">Conversas por dia</h3>
        <button className="material-symbols-outlined text-on-surface-variant hover:text-on-surface transition-colors" style={{ fontSize: "20px" }}>
          more_horiz
        </button>
      </div>
      <div className="h-[300px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barCategoryGap="40%">
            <CartesianGrid vertical={false} stroke="var(--color-outline-variant)" strokeDasharray="3 3" />
            <XAxis
              dataKey="day"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "var(--color-on-surface-variant)", fontSize: 13, fontFamily: "var(--font-mono)" }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: "var(--color-on-surface-variant)", fontSize: 13, fontFamily: "var(--font-mono)" }}
              tickFormatter={(v: number) => (v >= 1000 ? `${v / 1000}k` : String(v))}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--color-surface-container-high)" }} />
            <Bar dataKey="count" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

---

### Task 13: ModelHealthCard component

**Files:**
- Create: `apps/web/src/features/dashboard/components/ModelHealthCard.tsx`

- [ ] **Step 1: Criar ModelHealthCard.tsx**

```tsx
// apps/web/src/features/dashboard/components/ModelHealthCard.tsx
import type { ModelHealth } from "../types";

function ProgressBar({ label, value, displayValue, color }: { label: string; value: number; displayValue: string; color: "primary" | "secondary" }) {
  return (
    <div>
      <div className="mb-1 flex justify-between">
        <span className="text-mono-label font-mono text-on-surface-variant">{label}</span>
        <span className="text-mono-label font-mono text-on-surface">{displayValue}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface">
        <div
          className={color === "primary" ? "h-full rounded-full bg-primary" : "h-full rounded-full bg-secondary"}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

export function ModelHealthCard({ health }: { health: ModelHealth }) {
  const latencyPct = Math.min((health.avgLatencyMs / 500) * 100, 100);

  return (
    <div className="flex h-full flex-col rounded-xl border border-outline-variant bg-surface-container overflow-hidden">
      <div className="h-1 w-full bg-gradient-to-r from-primary to-secondary" />
      <div className="flex flex-1 flex-col p-card-padding">
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-lg border border-outline-variant bg-primary-container">
          <span className="material-symbols-outlined text-primary" style={{ fontSize: "22px" }}>memory</span>
        </div>
        <h3 className="text-h2 font-sans font-semibold text-on-surface">Saúde do Modelo</h3>
        <p className="mt-2 text-body-sm text-on-surface-variant">
          A latência do modelo principal está otimizada. Nenhuma anomalia detectada nas últimas 24 horas.
        </p>
        <div className="mt-auto space-y-4 pt-6">
          <ProgressBar label="Uso de CPU" value={health.cpuUsage} displayValue={`${health.cpuUsage}%`} color="primary" />
          <ProgressBar label="Latência Média" value={latencyPct} displayValue={`${health.avgLatencyMs}ms`} color="secondary" />
        </div>
      </div>
    </div>
  );
}
```

---

### Task 14: SkillsTable component

**Files:**
- Create: `apps/web/src/features/dashboard/components/SkillsTable.tsx`

- [ ] **Step 1: Criar SkillsTable.tsx**

```tsx
// apps/web/src/features/dashboard/components/SkillsTable.tsx
import type { SkillMetric } from "../types";

export function SkillsTable({ skills }: { skills: SkillMetric[] }) {
  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container p-card-padding">
      <div className="mb-6 flex items-center justify-between">
        <h3 className="text-h2 font-sans font-semibold text-on-surface">Top 5 Habilidades Acionadas</h3>
        <button className="text-mono-label font-mono text-primary hover:text-on-surface transition-colors">
          Ver Relatório Completo
        </button>
      </div>
      <table className="w-full border-collapse text-left">
        <thead>
          <tr>
            <th className="border-b border-outline-variant pb-3 pl-2 text-label-caps font-sans uppercase tracking-wider text-on-surface-variant">
              Nome da Habilidade
            </th>
            <th className="border-b border-outline-variant pb-3 text-right text-label-caps font-sans uppercase tracking-wider text-on-surface-variant">
              Contagem
            </th>
            <th className="border-b border-outline-variant pb-3 pr-2 text-right text-label-caps font-sans uppercase tracking-wider text-on-surface-variant">
              Porcentagem
            </th>
          </tr>
        </thead>
        <tbody>
          {skills.map((skill, idx) => {
            const isLast = idx === skills.length - 1;
            const border = isLast ? "" : "border-b border-outline-variant/50";
            return (
              <tr key={skill.id} className="group transition-colors hover:bg-surface-variant/30">
                <td className={`py-4 pl-2 text-body-sm text-on-surface ${border}`}>
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded bg-surface text-on-surface-variant group-hover:text-primary transition-colors">
                      <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>{skill.icon}</span>
                    </div>
                    <span className="font-medium">{skill.name}</span>
                  </div>
                </td>
                <td className={`py-4 text-right text-mono-label font-mono text-on-surface ${border}`}>
                  {skill.count.toLocaleString("pt-BR")}
                </td>
                <td className={`py-4 pr-2 text-right ${border}`}>
                  <div className="flex items-center justify-end gap-3">
                    <span className="text-mono-label font-mono text-on-surface">{skill.pct.toFixed(1)}%</span>
                    <div className="h-1 w-16 overflow-hidden rounded-full bg-surface">
                      <div className="h-full bg-primary" style={{ width: `${skill.pct}%` }} />
                    </div>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

---

### Task 15: Dashboard page (atualizado)

**Files:**
- Modify: `apps/web/src/app/dashboard/page.tsx`

- [ ] **Step 1: Substituir dashboard/page.tsx**

```tsx
// apps/web/src/app/dashboard/page.tsx
import { KpiCard } from "@/features/dashboard/components/KpiCard";
import { ConversationsChart } from "@/features/dashboard/components/ConversationsChart";
import { ModelHealthCard } from "@/features/dashboard/components/ModelHealthCard";
import { SkillsTable } from "@/features/dashboard/components/SkillsTable";
import { kpiData, chartData, skillsData, modelHealthData } from "@/features/dashboard/data/dashboardMocks";

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-h1 font-sans font-bold text-on-background">Visão Geral</h1>
          <p className="mt-1 text-body-base text-on-surface-variant">
            Métricas de performance dos seus agentes IA hoje.
          </p>
        </div>
        <button className="flex items-center gap-2 rounded-lg border border-outline-variant px-4 py-2 text-mono-label font-mono text-on-surface hover:bg-surface-container-high transition-colors">
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>calendar_today</span>
          Últimos 7 dias
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
        {kpiData.map((metric) => <KpiCard key={metric.id} metric={metric} />)}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <ConversationsChart data={chartData} />
        </div>
        <div className="lg:col-span-4">
          <ModelHealthCard health={modelHealthData} />
        </div>
      </div>

      <SkillsTable skills={skillsData} />
    </div>
  );
}
```

- [ ] **Step 2: Commit Tasks 10–15**

```bash
git add apps/web/src/features/dashboard/ apps/web/src/app/dashboard/page.tsx
git commit -m "feat(web/dashboard): KPI cards, chart, model health card, skills table"
```

---

### Task 16: KB — tipos e mocks

**Files:**
- Create: `apps/web/src/features/kb/types.ts`
- Create: `apps/web/src/features/kb/data/kbMocks.ts`

- [ ] **Step 1: Criar types.ts**

```ts
// apps/web/src/features/kb/types.ts

export type FileStatus = "indexed" | "error" | "processing";

export interface KbFile {
  id: string;
  name: string;
  size: string;
  status: FileStatus;
}
```

- [ ] **Step 2: Criar kbMocks.ts**

```ts
// apps/web/src/features/kb/data/kbMocks.ts
import type { KbFile } from "../types";

export const processedFiles: KbFile[] = [
  { id: "1", name: "manuais_tecnicos_v2.docx", size: "2.4 MB", status: "indexed" },
  { id: "2", name: "politicas_RH_2023.pdf", size: "1.1 MB", status: "indexed" },
  { id: "3", name: "log_servidor_corrompido.txt", size: "0.3 MB", status: "error" },
  { id: "4", name: "atas_reuniao_diretoria.pdf", size: "5.7 MB", status: "indexed" },
];
```

---

### Task 17: FileItem component

**Files:**
- Create: `apps/web/src/features/kb/components/FileItem.tsx`

- [ ] **Step 1: Criar FileItem.tsx**

```tsx
// apps/web/src/features/kb/components/FileItem.tsx
"use client";

import { cn } from "@/lib/utils";
import { useToast } from "@/shared/hooks/useToast";
import type { KbFile } from "../types";

export function FileItem({ file }: { file: KbFile }) {
  const toast = useToast();
  const isError = file.status === "error";

  return (
    <div
      className={cn(
        "relative rounded-lg border p-3 transition-colors",
        isError
          ? "overflow-hidden border-error/30 hover:border-error/50 bg-surface-container"
          : "border-outline-variant bg-surface-container hover:border-outline"
      )}
    >
      {isError && <div className="absolute bottom-0 left-0 top-0 w-1 rounded-l-lg bg-error/50" />}

      <div className={cn("mb-2 flex items-start justify-between", isError && "pl-3")}>
        <div className="flex items-center gap-2 overflow-hidden">
          <span
            className={cn("material-symbols-outlined shrink-0", isError ? "text-error" : "text-on-surface-variant")}
            style={{ fontSize: "18px" }}
          >
            {isError ? "warning" : "description"}
          </span>
          <span className={cn("truncate text-body-sm text-on-surface", isError && "line-through opacity-70")}>
            {file.name}
          </span>
        </div>
        {file.status === "indexed" && (
          <span className="material-symbols-outlined shrink-0 text-primary" style={{ fontSize: "18px" }}>
            check_circle
          </span>
        )}
        {file.status === "processing" && (
          <span className="material-symbols-outlined shrink-0 animate-spin text-on-surface-variant" style={{ fontSize: "18px" }}>
            progress_activity
          </span>
        )}
      </div>

      <div className={cn("flex items-center justify-between", isError && "pl-3")}>
        {isError ? (
          <>
            <span className="text-mono-label font-mono text-error">Erro de leitura</span>
            <button
              onClick={() => toast.info("Tentando novamente...")}
              className="text-on-surface-variant hover:text-on-surface transition-colors"
            >
              <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>refresh</span>
            </button>
          </>
        ) : (
          <>
            <span className="text-mono-label font-mono text-on-surface-variant">{file.size}</span>
            {file.status === "indexed" && (
              <span className="rounded bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-medium uppercase text-primary">
                Indexado
              </span>
            )}
          </>
        )}
      </div>
    </div>
  );
}
```

---

### Task 18: FileList component

**Files:**
- Create: `apps/web/src/features/kb/components/FileList.tsx`

- [ ] **Step 1: Criar FileList.tsx**

```tsx
// apps/web/src/features/kb/components/FileList.tsx
import { FileItem } from "./FileItem";
import type { KbFile } from "../types";

export function FileList({ files }: { files: KbFile[] }) {
  return (
    <div className="flex w-full flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-low lg:w-80">
      <div className="flex items-center justify-between border-b border-outline-variant bg-surface-container/50 px-4 py-3">
        <span className="text-label-caps font-sans uppercase tracking-wider text-on-surface-variant">
          Arquivos Processados
        </span>
        <span className="rounded bg-surface-container-high px-2 py-0.5 text-xs text-on-surface">
          {files.length}
        </span>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-2">
        {files.map((file) => <FileItem key={file.id} file={file} />)}
      </div>
    </div>
  );
}
```

---

### Task 19: UploadProgress component

**Files:**
- Create: `apps/web/src/features/kb/components/UploadProgress.tsx`

- [ ] **Step 1: Criar UploadProgress.tsx**

```tsx
// apps/web/src/features/kb/components/UploadProgress.tsx
export function UploadProgress({ filename, progress }: { filename: string; progress: number }) {
  return (
    <div className="mt-4 rounded-lg border border-outline-variant bg-surface-container p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-primary" style={{ fontSize: "20px" }}>description</span>
          <span className="text-body-sm font-medium text-on-surface">{filename}</span>
        </div>
        <span className="text-mono-label font-mono text-on-surface-variant">{progress}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-container-highest">
        <div className="h-full rounded-full bg-primary transition-all duration-300" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}
```

---

### Task 20: Dropzone component

**Files:**
- Create: `apps/web/src/features/kb/components/Dropzone.tsx`

- [ ] **Step 1: Criar Dropzone.tsx**

```tsx
// apps/web/src/features/kb/components/Dropzone.tsx
"use client";

import { useState, useCallback } from "react";
import { useToast } from "@/shared/hooks/useToast";
import { UploadProgress } from "./UploadProgress";

const ACCEPTED = [".pdf", ".docx", ".txt"];

export function Dropzone() {
  const toast = useToast();
  const [isDragOver, setIsDragOver] = useState(false);

  const processFile = useCallback(
    (file: File) => {
      const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
      if (!ACCEPTED.includes(ext)) {
        toast.error("Formato não suportado", `Use: ${ACCEPTED.join(", ")}`);
        return;
      }
      toast.success("Arquivo enviado para processamento", file.name);
    },
    [toast]
  );

  return (
    <div className="flex flex-1 flex-col">
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setIsDragOver(false); const f = e.dataTransfer.files[0]; if (f) processFile(f); }}
        className={`relative flex flex-1 min-h-[280px] flex-col items-center justify-center rounded-xl border-2 border-dashed transition-colors ${
          isDragOver ? "border-primary bg-primary/5" : "border-outline-variant hover:border-outline"
        }`}
      >
        <input
          type="file"
          accept={ACCEPTED.join(",")}
          multiple
          onChange={(e) => { const f = e.target.files?.[0]; if (f) processFile(f); }}
          className="absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0"
        />
        <div className="pointer-events-none flex flex-col items-center px-8 text-center">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-surface-container-high">
            <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: "28px" }}>
              cloud_upload
            </span>
          </div>
          <h3 className="text-body-base font-semibold text-on-surface">Arraste arquivos aqui</h3>
          <p className="mt-1 text-body-sm text-on-surface-variant">ou clique para selecionar do seu computador</p>
          <div className="mt-6 flex gap-3">
            {ACCEPTED.map((fmt) => (
              <span key={fmt} className="rounded-full border border-outline-variant bg-surface-container-high px-3 py-1 font-mono text-mono-label uppercase text-on-surface-variant">
                {fmt.replace(".", "")}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Mock progress bar */}
      <UploadProgress filename="relatorio_financeiro_Q3.pdf" progress={45} />
    </div>
  );
}
```

---

### Task 21: KB upload page (atualizado)

**Files:**
- Modify: `apps/web/src/app/kb/upload/page.tsx`

- [ ] **Step 1: Substituir kb/upload/page.tsx**

```tsx
// apps/web/src/app/kb/upload/page.tsx
import { Dropzone } from "@/features/kb/components/Dropzone";
import { FileList } from "@/features/kb/components/FileList";
import { processedFiles } from "@/features/kb/data/kbMocks";

export default function KbUploadPage() {
  return (
    <div className="flex flex-col gap-6 lg:flex-row lg:h-[calc(100vh-128px)]">
      <div className="flex flex-1 flex-col rounded-xl border border-outline-variant bg-surface-container-low p-card-padding">
        <div className="mb-6">
          <h1 className="text-h2 font-sans font-semibold text-on-background">Importação de Conhecimento</h1>
          <p className="mt-1 text-body-sm text-on-surface-variant">
            Arraste e solte arquivos para alimentar a base de conhecimento do agente.
          </p>
        </div>
        <Dropzone />
      </div>
      <FileList files={processedFiles} />
    </div>
  );
}
```

- [ ] **Step 2: Commit Tasks 16–21**

```bash
git add apps/web/src/features/kb/ apps/web/src/app/kb/upload/page.tsx
git commit -m "feat(web/kb): Dropzone, FileList, FileItem, UploadProgress com toasts"
```

---

### Task 22: ComingSoon + Accounts page

**Files:**
- Create: `apps/web/src/features/accounts/components/ComingSoon.tsx`
- Modify: `apps/web/src/app/accounts/page.tsx`

- [ ] **Step 1: Criar ComingSoon.tsx**

```tsx
// apps/web/src/features/accounts/components/ComingSoon.tsx
"use client";

import { useRouter } from "next/navigation";

export function ComingSoon() {
  const router = useRouter();

  return (
    <div className="flex flex-1 items-center justify-center py-16">
      <div className="flex w-full max-w-lg flex-col items-center rounded-xl border border-outline-variant bg-surface-container-low p-card-padding text-center">
        <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-xl border border-outline-variant bg-surface-container">
          <span className="material-symbols-outlined text-primary" style={{ fontSize: "28px" }}>construction</span>
        </div>
        <span className="mb-4 text-label-caps font-sans uppercase tracking-widest text-primary">Em breve</span>
        <h2 className="text-h1 font-sans font-bold text-on-surface mb-4">Configuração de Contas</h2>
        <p className="text-body-base text-on-surface-variant max-w-sm">
          Em breve você poderá gerenciar múltiplas instâncias e configurações de inquilinos diretamente por aqui.
        </p>
        <button
          onClick={() => router.push("/dashboard")}
          className="mt-8 w-full rounded-lg bg-primary-container px-6 py-input-padding text-mono-label font-mono text-on-primary-container hover:opacity-90 transition-opacity"
        >
          Voltar ao Dashboard
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Substituir accounts/page.tsx**

```tsx
// apps/web/src/app/accounts/page.tsx
import { ComingSoon } from "@/features/accounts/components/ComingSoon";

export default function AccountsPage() {
  return <ComingSoon />;
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/accounts/ apps/web/src/app/accounts/page.tsx
git commit -m "feat(web/accounts): ComingSoon component"
```

---

### Task 23: Remover componentes antigos

**Files:**
- Delete: `apps/web/src/components/sidebar.tsx`
- Delete: `apps/web/src/components/dashboard/metric-card.tsx`
- Delete: `apps/web/src/components/dashboard/conversations-chart.tsx`
- Delete: `apps/web/src/components/kb/upload-form.tsx`
- Keep: `apps/web/src/components/kb/document-table.tsx` (usado em /kb)
- Keep: `apps/web/src/components/ui/` (shadcn — sem mudança)

- [ ] **Step 1: Remover arquivos substituídos**

```bash
rm apps/web/src/components/sidebar.tsx
rm apps/web/src/components/dashboard/metric-card.tsx
rm apps/web/src/components/dashboard/conversations-chart.tsx
rm apps/web/src/components/kb/upload-form.tsx
```

- [ ] **Step 2: Build para verificar imports quebrados**

```bash
cd apps/web && npm run build 2>&1 | grep -E "Error|error" | head -20
```

Expected: sem erros de módulo ausente. Se houver, rastrear o import e corrigir.

- [ ] **Step 3: Commit**

```bash
git add -A apps/web/src/components/
git commit -m "chore(web): remove old components replaced by feature modules"
```
