# NexoIA — Web Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `apps/web/` with a Next.js 15 application containing an admin dashboard — sidebar navigation, AI performance metrics page (mocked data), KB Admin pages (list documents + upload), and an Accounts placeholder. The app communicates with the FastAPI backend already running in `apps/api/`.

**Architecture:** Next.js 15 App Router with TypeScript. Server Components for data-fetching pages; Client Components only where interactivity is required (upload form, charts). A thin `lib/api.ts` HTTP client wraps all fetch calls and reads `NEXT_PUBLIC_API_URL` from the environment. shadcn/ui provides Card, Table, Button, Input, and Dialog primitives. Tailwind CSS for layout and spacing.

**Tech Stack:** Next.js 15, TypeScript, Tailwind CSS v3, shadcn/ui, Recharts (conversations/day chart), `NEXT_PUBLIC_API_URL` env var

**Independent of Plan 2** — can run in parallel after Plan 1 (monorepo restructure) is complete.

---

## File Map

### Create
```
apps/web/package.json
apps/web/tsconfig.json
apps/web/next.config.ts
apps/web/tailwind.config.ts
apps/web/postcss.config.js
apps/web/.env.local.example
apps/web/components.json                         ← shadcn/ui config
apps/web/src/app/layout.tsx
apps/web/src/app/globals.css
apps/web/src/app/page.tsx                        ← redirect to /dashboard
apps/web/src/app/dashboard/page.tsx
apps/web/src/app/kb/page.tsx                     ← KB list
apps/web/src/app/kb/upload/page.tsx              ← KB upload
apps/web/src/app/accounts/page.tsx
apps/web/src/components/sidebar.tsx
apps/web/src/components/ui/card.tsx              ← shadcn Card
apps/web/src/components/ui/button.tsx            ← shadcn Button
apps/web/src/components/ui/table.tsx             ← shadcn Table
apps/web/src/components/ui/input.tsx             ← shadcn Input
apps/web/src/components/ui/badge.tsx             ← shadcn Badge
apps/web/src/components/dashboard/metric-card.tsx
apps/web/src/components/dashboard/conversations-chart.tsx
apps/web/src/components/kb/document-table.tsx
apps/web/src/components/kb/upload-form.tsx
apps/web/src/lib/api.ts
apps/web/src/types/api.ts
```

---

## Task 1 — Scaffold Next.js 15 app

- [ ] **Step 1: Create directory skeleton**

```bash
mkdir -p apps/web/src/app/dashboard
mkdir -p apps/web/src/app/kb/upload
mkdir -p apps/web/src/app/accounts
mkdir -p apps/web/src/components/ui
mkdir -p apps/web/src/components/dashboard
mkdir -p apps/web/src/components/kb
mkdir -p apps/web/src/lib
mkdir -p apps/web/src/types
```

- [ ] **Step 2: Create `apps/web/package.json`**

```json
{
  "name": "nexoia-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev --turbo",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "15.3.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "recharts": "^2.12.7",
    "lucide-react": "^0.436.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.2",
    "class-variance-authority": "^0.7.0",
    "@radix-ui/react-slot": "^1.1.0",
    "@radix-ui/react-dialog": "^1.1.1",
    "@radix-ui/react-dropdown-menu": "^2.1.1"
  },
  "devDependencies": {
    "typescript": "^5.5.4",
    "@types/node": "^22.5.4",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "tailwindcss": "^3.4.11",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.45",
    "eslint": "^9.9.1",
    "eslint-config-next": "15.3.0"
  }
}
```

- [ ] **Step 3: Create `apps/web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 4: Create `apps/web/next.config.ts`**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
```

- [ ] **Step 5: Create `apps/web/tailwind.config.ts`**

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 6: Create `apps/web/postcss.config.js`**

```javascript
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 7: Create `apps/web/components.json`** (shadcn/ui config)

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/app/globals.css",
    "baseColor": "slate",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
}
```

- [ ] **Step 8: Create `apps/web/.env.local.example`**

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 9: Commit**

```bash
git add apps/web/package.json apps/web/tsconfig.json apps/web/next.config.ts \
        apps/web/tailwind.config.ts apps/web/postcss.config.js \
        apps/web/components.json apps/web/.env.local.example
git commit -m "chore(web): scaffold Next.js 15 project config files"
```

---

## Task 2 — Global styles and `lib/` utilities

- [ ] **Step 1: Create `apps/web/src/app/globals.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --ring: 222.2 84% 4.9%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --primary: 210 40% 98%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --ring: 212.7 26.8% 83.9%;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}
```

- [ ] **Step 2: Create `apps/web/src/lib/utils.ts`**

```typescript
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 3: Create `apps/web/src/types/api.ts`**

```typescript
// apps/web/src/types/api.ts

export interface KbDocument {
  id: string;
  filename: string;
  status: "pending" | "processing" | "ready" | "error";
  chunk_count: number;
  created_at: string;
}

export interface KbDocumentListResponse {
  items: KbDocument[];
  total: number;
}

export interface UploadDocumentResponse {
  id: string;
  filename: string;
  status: string;
}

export interface ApiError {
  detail: string;
}
```

- [ ] **Step 4: Create `apps/web/src/lib/api.ts`**

```typescript
// apps/web/src/lib/api.ts

import type {
  KbDocumentListResponse,
  UploadDocumentResponse,
} from "@/types/api";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      Accept: "application/json",
      ...(options?.headers ?? {}),
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ─── KB Admin ────────────────────────────────────────────────────────────────

export async function listDocuments(
  accountId: string,
): Promise<KbDocumentListResponse> {
  return apiFetch<KbDocumentListResponse>(
    `/admin/documents?account_id=${encodeURIComponent(accountId)}`,
  );
}

export async function uploadDocument(
  accountId: string,
  file: File,
): Promise<UploadDocumentResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("account_id", accountId);
  return apiFetch<UploadDocumentResponse>("/admin/documents", {
    method: "POST",
    body: form,
    // Do NOT set Content-Type — browser sets multipart boundary automatically
  });
}

export async function deleteDocument(
  documentId: string,
): Promise<void> {
  return apiFetch<void>(`/admin/documents/${documentId}`, {
    method: "DELETE",
  });
}
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/app/globals.css apps/web/src/lib/ apps/web/src/types/
git commit -m "feat(web): add global styles, api client, and shared types"
```

---

## Task 3 — shadcn/ui primitive components

- [ ] **Step 1: Create `apps/web/src/components/ui/card.tsx`**

```tsx
// apps/web/src/components/ui/card.tsx
import * as React from "react";
import { cn } from "@/lib/utils";

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-lg border bg-card text-card-foreground shadow-sm",
      className,
    )}
    {...props}
  />
));
Card.displayName = "Card";

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6", className)}
    {...props}
  />
));
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
      "text-2xl font-semibold leading-none tracking-tight",
      className,
    )}
    {...props}
  />
));
CardTitle.displayName = "CardTitle";

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
));
CardDescription.displayName = "CardDescription";

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
));
CardContent.displayName = "CardContent";

const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center p-6 pt-0", className)}
    {...props}
  />
));
CardFooter.displayName = "CardFooter";

export { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle };
```

- [ ] **Step 2: Create `apps/web/src/components/ui/button.tsx`**

```tsx
// apps/web/src/components/ui/button.tsx
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-red-500 text-white hover:bg-red-600",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
```

- [ ] **Step 3: Create `apps/web/src/components/ui/table.tsx`**

```tsx
// apps/web/src/components/ui/table.tsx
import * as React from "react";
import { cn } from "@/lib/utils";

const Table = React.forwardRef<
  HTMLTableElement,
  React.HTMLAttributes<HTMLTableElement>
>(({ className, ...props }, ref) => (
  <div className="relative w-full overflow-auto">
    <table
      ref={ref}
      className={cn("w-full caption-bottom text-sm", className)}
      {...props}
    />
  </div>
));
Table.displayName = "Table";

const TableHeader = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <thead ref={ref} className={cn("[&_tr]:border-b", className)} {...props} />
));
TableHeader.displayName = "TableHeader";

const TableBody = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tbody
    ref={ref}
    className={cn("[&_tr:last-child]:border-0", className)}
    {...props}
  />
));
TableBody.displayName = "TableBody";

const TableRow = React.forwardRef<
  HTMLTableRowElement,
  React.HTMLAttributes<HTMLTableRowElement>
>(({ className, ...props }, ref) => (
  <tr
    ref={ref}
    className={cn(
      "border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted",
      className,
    )}
    {...props}
  />
));
TableRow.displayName = "TableRow";

const TableHead = React.forwardRef<
  HTMLTableCellElement,
  React.ThHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <th
    ref={ref}
    className={cn(
      "h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0",
      className,
    )}
    {...props}
  />
));
TableHead.displayName = "TableHead";

const TableCell = React.forwardRef<
  HTMLTableCellElement,
  React.TdHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <td
    ref={ref}
    className={cn(
      "p-4 align-middle [&:has([role=checkbox])]:pr-0",
      className,
    )}
    {...props}
  />
));
TableCell.displayName = "TableCell";

export { Table, TableBody, TableCell, TableHead, TableHeader, TableRow };
```

- [ ] **Step 4: Create `apps/web/src/components/ui/input.tsx`**

```tsx
// apps/web/src/components/ui/input.tsx
import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

export { Input };
```

- [ ] **Step 5: Create `apps/web/src/components/ui/badge.tsx`**

```tsx
// apps/web/src/components/ui/badge.tsx
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        destructive: "border-transparent bg-red-500 text-white",
        outline: "text-foreground",
        success: "border-transparent bg-green-100 text-green-800",
        warning: "border-transparent bg-yellow-100 text-yellow-800",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
```

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/ui/
git commit -m "feat(web): add shadcn/ui primitive components (Card, Button, Table, Input, Badge)"
```

---

## Task 4 — Sidebar navigation component

- [ ] **Step 1: Create `apps/web/src/components/sidebar.tsx`**

```tsx
// apps/web/src/components/sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  BookOpen,
  Users,
  BrainCircuit,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  {
    label: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    label: "KB Admin",
    href: "/kb",
    icon: BookOpen,
  },
  {
    label: "Accounts",
    href: "/accounts",
    icon: Users,
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-60 flex-col border-r bg-white">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 border-b px-6">
        <BrainCircuit className="h-6 w-6 text-primary" />
        <span className="text-lg font-semibold tracking-tight">NexoIA</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active =
            pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t p-4">
        <p className="text-xs text-muted-foreground">NexoIA Admin v0.1</p>
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/components/sidebar.tsx
git commit -m "feat(web): add sidebar navigation component"
```

---

## Task 5 — Root layout

- [ ] **Step 1: Create `apps/web/src/app/layout.tsx`**

```tsx
// apps/web/src/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "NexoIA Admin",
  description: "NexoIA AI Agent Administration Panel",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body className={inter.className}>
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 overflow-auto bg-muted/30 p-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Create `apps/web/src/app/page.tsx`** (root redirect)

```tsx
// apps/web/src/app/page.tsx
import { redirect } from "next/navigation";

export default function RootPage() {
  redirect("/dashboard");
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/layout.tsx apps/web/src/app/page.tsx
git commit -m "feat(web): add root layout with sidebar and root redirect"
```

---

## Task 6 — Dashboard page

- [ ] **Step 1: Create `apps/web/src/components/dashboard/metric-card.tsx`**

```tsx
// apps/web/src/components/dashboard/metric-card.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  value: string | number;
  description?: string;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function MetricCard({
  title,
  value,
  description,
  trend,
  className,
}: MetricCardProps) {
  return (
    <Card className={cn("", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">{value}</div>
        {description && (
          <p
            className={cn(
              "mt-1 text-xs",
              trend === "up" && "text-green-600",
              trend === "down" && "text-red-600",
              trend === "neutral" && "text-muted-foreground",
              !trend && "text-muted-foreground",
            )}
          >
            {description}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Create `apps/web/src/components/dashboard/conversations-chart.tsx`**

```tsx
// apps/web/src/components/dashboard/conversations-chart.tsx
"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface DayData {
  day: string;
  conversations: number;
}

interface ConversationsChartProps {
  data: DayData[];
}

export function ConversationsChart({ data }: ConversationsChartProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold">
          Conversas por dia (últimos 7 dias)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="day"
              tick={{ fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              allowDecimals={false}
            />
            <Tooltip
              contentStyle={{
                borderRadius: "8px",
                border: "1px solid hsl(214.3 31.8% 91.4%)",
                fontSize: "12px",
              }}
            />
            <Bar dataKey="conversations" fill="hsl(222.2 47.4% 11.2%)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Create `apps/web/src/app/dashboard/page.tsx`**

```tsx
// apps/web/src/app/dashboard/page.tsx
import { MetricCard } from "@/components/dashboard/metric-card";
import { ConversationsChart } from "@/components/dashboard/conversations-chart";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// ── Mocked data ──────────────────────────────────────────────────────────────
// Replace with real API calls once analytics endpoints are available.

const METRICS = {
  totalConversations: 1_284,
  escalationRate: "8.3%",
  resolvedByAI: "91.7%",
  avgTurnsPerConversation: 4.2,
};

const TOP_SKILLS = [
  { name: "buscar_conhecimento", calls: 512, pct: "39.9%" },
  { name: "buscar_aluno_cademi", calls: 387, pct: "30.1%" },
  { name: "enviar_link_acesso", calls: 243, pct: "18.9%" },
  { name: "verificar_elegibilidade_reembolso", calls: 89, pct: "6.9%" },
  { name: "escalar_para_humano", calls: 53, pct: "4.1%" },
];

const CONVERSATIONS_BY_DAY = [
  { day: "Seg", conversations: 162 },
  { day: "Ter", conversations: 198 },
  { day: "Qua", conversations: 215 },
  { day: "Qui", conversations: 177 },
  { day: "Sex", conversations: 231 },
  { day: "Sáb", conversations: 143 },
  { day: "Dom", conversations: 158 },
];

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Visão geral do desempenho do agente de IA
        </p>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          title="Total de conversas"
          value={METRICS.totalConversations.toLocaleString("pt-BR")}
          description="Últimos 30 dias"
          trend="neutral"
        />
        <MetricCard
          title="Taxa de escalação"
          value={METRICS.escalationRate}
          description="Para agente humano"
          trend="down"
        />
        <MetricCard
          title="Resolvido pela IA"
          value={METRICS.resolvedByAI}
          description="Sem escalação"
          trend="up"
        />
        <MetricCard
          title="Turnos médios"
          value={METRICS.avgTurnsPerConversation}
          description="Por conversa"
          trend="neutral"
        />
      </div>

      {/* Chart + Top skills */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ConversationsChart data={CONVERSATIONS_BY_DAY} />
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Top 5 skills
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {TOP_SKILLS.map((skill) => (
                <li key={skill.name} className="flex items-center justify-between">
                  <span className="max-w-[160px] truncate text-sm" title={skill.name}>
                    {skill.name}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      {skill.calls}
                    </span>
                    <Badge variant="secondary">{skill.pct}</Badge>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/dashboard/ apps/web/src/app/dashboard/
git commit -m "feat(web): add dashboard page with metric cards and conversations chart"
```

---

## Task 7 — KB Admin list page

- [ ] **Step 1: Create `apps/web/src/components/kb/document-table.tsx`**

```tsx
// apps/web/src/components/kb/document-table.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Trash2 } from "lucide-react";
import { deleteDocument } from "@/lib/api";
import type { KbDocument } from "@/types/api";

interface DocumentTableProps {
  documents: KbDocument[];
}

function statusVariant(
  status: KbDocument["status"],
): "success" | "warning" | "destructive" | "secondary" {
  switch (status) {
    case "ready":
      return "success";
    case "processing":
      return "warning";
    case "error":
      return "destructive";
    default:
      return "secondary";
  }
}

function statusLabel(status: KbDocument["status"]): string {
  switch (status) {
    case "ready":
      return "Pronto";
    case "processing":
      return "Processando";
    case "error":
      return "Erro";
    default:
      return "Pendente";
  }
}

export function DocumentTable({ documents }: DocumentTableProps) {
  const [rows, setRows] = useState<KbDocument[]>(documents);
  const [deleting, setDeleting] = useState<string | null>(null);

  async function handleDelete(id: string) {
    if (!confirm("Remover este documento da base de conhecimento?")) return;
    setDeleting(id);
    try {
      await deleteDocument(id);
      setRows((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      alert(`Erro ao remover: ${err instanceof Error ? err.message : err}`);
    } finally {
      setDeleting(null);
    }
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-md border p-8 text-center text-sm text-muted-foreground">
        Nenhum documento na base de conhecimento.{" "}
        <Link href="/kb/upload" className="underline">
          Faça o upload do primeiro documento.
        </Link>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Arquivo</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Chunks</TableHead>
          <TableHead>Criado em</TableHead>
          <TableHead className="w-12" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((doc) => (
          <TableRow key={doc.id}>
            <TableCell className="font-medium">{doc.filename}</TableCell>
            <TableCell>
              <Badge variant={statusVariant(doc.status)}>
                {statusLabel(doc.status)}
              </Badge>
            </TableCell>
            <TableCell className="text-right">{doc.chunk_count}</TableCell>
            <TableCell className="text-muted-foreground">
              {new Date(doc.created_at).toLocaleDateString("pt-BR")}
            </TableCell>
            <TableCell>
              <Button
                variant="ghost"
                size="icon"
                disabled={deleting === doc.id}
                onClick={() => handleDelete(doc.id)}
                aria-label="Remover documento"
              >
                <Trash2 className="h-4 w-4 text-muted-foreground" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 2: Create `apps/web/src/app/kb/page.tsx`**

```tsx
// apps/web/src/app/kb/page.tsx
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { DocumentTable } from "@/components/kb/document-table";
import { listDocuments } from "@/lib/api";
import { Upload } from "lucide-react";

// The account_id will come from session/auth in a future iteration.
// For now, read from env or default to "1" for development.
const ACCOUNT_ID = process.env.DEFAULT_ACCOUNT_ID ?? "1";

export default async function KbListPage() {
  let documents = [];
  let error: string | null = null;

  try {
    const response = await listDocuments(ACCOUNT_ID);
    documents = response.items;
  } catch (err) {
    error = err instanceof Error ? err.message : "Erro ao carregar documentos.";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Base de Conhecimento
          </h1>
          <p className="text-muted-foreground">
            Gerencie os documentos que o agente usa para responder dúvidas.
          </p>
        </div>
        <Button asChild>
          <Link href="/kb/upload">
            <Upload className="mr-2 h-4 w-4" />
            Upload
          </Link>
        </Button>
      </div>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : (
        <DocumentTable documents={documents} />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/kb/document-table.tsx apps/web/src/app/kb/page.tsx
git commit -m "feat(web): add KB admin list page with document table and delete action"
```

---

## Task 8 — KB Admin upload page

- [ ] **Step 1: Create `apps/web/src/components/kb/upload-form.tsx`**

```tsx
// apps/web/src/components/kb/upload-form.tsx
"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { uploadDocument } from "@/lib/api";
import { Upload, FileText, CheckCircle2 } from "lucide-react";

interface UploadFormProps {
  accountId: string;
}

export function UploadForm({ accountId }: UploadFormProps) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
    setError(null);
    setSuccess(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Selecione um arquivo para fazer o upload.");
      return;
    }

    const allowed = [".pdf", ".docx", ".txt"];
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
    if (!allowed.includes(ext)) {
      setError(`Formato não suportado. Use: ${allowed.join(", ")}`);
      return;
    }

    setUploading(true);
    setError(null);

    try {
      await uploadDocument(accountId, file);
      setSuccess(true);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setTimeout(() => router.push("/kb"), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro no upload.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <Card className="max-w-lg">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <Upload className="h-4 w-4" />
          Novo documento
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label
              htmlFor="file-input"
              className="text-sm font-medium leading-none"
            >
              Arquivo (PDF, DOCX ou TXT)
            </label>
            <Input
              id="file-input"
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={handleFileChange}
              disabled={uploading}
            />
          </div>

          {file && (
            <div className="flex items-center gap-2 rounded-md bg-muted p-3 text-sm">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="truncate">{file.name}</span>
              <span className="ml-auto text-xs text-muted-foreground">
                {(file.size / 1024).toFixed(1)} KB
              </span>
            </div>
          )}

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          {success && (
            <div className="flex items-center gap-2 text-sm text-green-700">
              <CheckCircle2 className="h-4 w-4" />
              Upload realizado! Redirecionando...
            </div>
          )}

          <Button type="submit" disabled={uploading || !file} className="w-full">
            {uploading ? "Enviando..." : "Fazer upload"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Create `apps/web/src/app/kb/upload/page.tsx`**

```tsx
// apps/web/src/app/kb/upload/page.tsx
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { UploadForm } from "@/components/kb/upload-form";
import { ArrowLeft } from "lucide-react";

const ACCOUNT_ID = process.env.DEFAULT_ACCOUNT_ID ?? "1";

export default function KbUploadPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/kb">
            <ArrowLeft className="mr-1 h-4 w-4" />
            Voltar
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Upload de documento</h1>
          <p className="text-muted-foreground">
            Adicione um novo documento à base de conhecimento.
          </p>
        </div>
      </div>

      <UploadForm accountId={ACCOUNT_ID} />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/kb/upload-form.tsx apps/web/src/app/kb/upload/
git commit -m "feat(web): add KB upload page with file validation and success redirect"
```

---

## Task 9 — Accounts placeholder page

- [ ] **Step 1: Create `apps/web/src/app/accounts/page.tsx`**

```tsx
// apps/web/src/app/accounts/page.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Users } from "lucide-react";

export default function AccountsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Accounts</h1>
        <p className="text-muted-foreground">
          Gestão de contas e configurações por tenant.
        </p>
      </div>

      <Card className="max-w-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <Users className="h-4 w-4" />
            Em breve
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            O gerenciamento de accounts está sendo desenvolvido. Aqui você
            poderá criar novos tenants, configurar integrações (Cademi, Hubla,
            ChatNexo) e definir as políticas de reembolso por conta.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/app/accounts/page.tsx
git commit -m "feat(web): add accounts placeholder page"
```

---

## Task 10 — Final verification

- [ ] **Step 1: Install dependencies**

```bash
cd apps/web
npm install
```

- [ ] **Step 2: Type-check**

```bash
cd apps/web
npx tsc --noEmit
```

Expected: zero TypeScript errors.

- [ ] **Step 3: Build check**

```bash
cd apps/web
npm run build
```

Expected: successful build with no errors. Next.js will show pages generated for `/dashboard`, `/kb`, `/kb/upload`, and `/accounts`.

- [ ] **Step 4: Verify dev server starts**

```bash
cd apps/web
npm run dev &
sleep 3
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/dashboard
# Expected: 200
kill %1
```

- [ ] **Step 5: Add `apps/web` to root workspace (if using uv / pnpm workspaces)**

If the repo root has a `pnpm-workspace.yaml` or similar, add `apps/web`:

```yaml
# pnpm-workspace.yaml
packages:
  - apps/api
  - apps/web
```

- [ ] **Step 6: Final commit**

```bash
git add apps/web/
git commit -m "feat(web): initial Next.js 15 web scaffold — dashboard, KB admin, accounts placeholder"
```
