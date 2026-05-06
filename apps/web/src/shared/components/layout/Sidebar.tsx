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
  { label: "Tokens de API", href: "/settings/tokens", icon: "key" },
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
