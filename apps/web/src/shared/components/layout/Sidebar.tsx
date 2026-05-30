// apps/web/src/shared/components/layout/Sidebar.tsx
"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import { usePermission } from "@/features/auth/hooks/usePermission";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useAvatar } from "@/features/profile/context/AvatarContext";

const NAV_ITEMS = [
  { label: "Painel", href: "/dashboard", icon: "dashboard" },
  { label: "Base de Conhecimento", href: "/kb", icon: "database" },
  { label: "Contas", href: "/accounts", icon: "group" },
  { label: "Produtos", href: "/products", icon: "inventory_2" },
  { label: "Leads", href: "/leads", icon: "person_search" },
  { label: "Onboarding", href: "/onboarding", icon: "schedule_send" },
  { label: "Pendências", href: "/onboarding/pendencias", icon: "report" },
  { label: "Templates", href: "/templates", icon: "sms" },
  { label: "Usuários", href: "/users", icon: "manage_accounts", adminOnly: true },
  { label: "Perfis", href: "/profiles", icon: "badge", adminOnly: true },
  { label: "Configurações", href: "/settings", icon: "settings", exact: true },
];

const FOOTER_ITEMS = [
  { label: "Tokens de API", href: "/settings/tokens", icon: "key" },
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
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const { isAdmin } = usePermission();
  const { user } = useAuth();
  const { blobUrl: avatarUrl } = useAvatar();

  const visibleItems = NAV_ITEMS.filter(
    (item) => !(item as { adminOnly?: boolean }).adminOnly || isAdmin
  );

  return (
    <aside className="fixed left-0 top-0 z-50 flex h-screen w-[240px] flex-col border-r border-outline-variant bg-surface-container-lowest">
      <div className="px-6 py-5">
        <Image
          src={isDark ? "/logo-dark.png" : "/logo-light.png"}
          alt="NexoIA"
          width={120}
          height={48}
          priority
          className="h-auto w-[120px]"
        />
      </div>

      <nav className="flex-1 space-y-1 px-4">
        {visibleItems.map((item) => {
          // Itens mais específicos (ex: /onboarding/pendencias) têm prioridade:
          // se outro item de menu casa com um prefixo mais longo, este não fica ativo.
          const isPrefixMatch =
            pathname === item.href || pathname.startsWith(item.href + "/");
          const hasMoreSpecific = visibleItems.some(
            (other) =>
              other.href !== item.href &&
              other.href.startsWith(item.href + "/") &&
              (pathname === other.href || pathname.startsWith(other.href + "/")),
          );
          const active =
            "exact" in item && item.exact
              ? pathname === item.href
              : isPrefixMatch && !hasMoreSpecific;
          return <NavItem key={item.href} {...item} active={active} />;
        })}
      </nav>

      <div className="space-y-1 border-t border-outline-variant px-4 py-4">
        {FOOTER_ITEMS.map((item) => (
          <NavItem key={item.href} {...item} active={pathname === item.href} />
        ))}
      </div>

      <div className="mt-auto border-t border-outline-variant p-3">
        <Link href="/profile" className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-surface-container">
          <div className="relative h-8 w-8 shrink-0">
            {avatarUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={avatarUrl} alt="" className="h-8 w-8 rounded-full object-cover" />
            ) : (
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-on-primary select-none">
                {user?.email?.charAt(0).toUpperCase() ?? "?"}
              </div>
            )}
          </div>
          <div className="flex flex-col text-body-sm overflow-hidden min-w-0">
            <span className="truncate">{user?.email ?? ""}</span>
            <span className="text-label-sm text-on-surface-variant">
              {user?.role === "admin" ? "Admin" : "Operador"}
            </span>
          </div>
        </Link>
      </div>
    </aside>
  );
}
