// apps/web/src/shared/components/layout/Sidebar.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import { usePermission } from "@/features/auth/hooks/usePermission";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useAvatar } from "@/features/profile/context/AvatarContext";

type NavEntry = { label: string; href: string; icon: string; perm: string; exact?: boolean };

const NAV_ITEMS: NavEntry[] = [
  { label: "Dashboard", href: "/dashboard", icon: "dashboard", perm: "dashboard.view" },
  { label: "Base de Conhecimento", href: "/kb", icon: "database", perm: "kb.view" },
  { label: "Produtos", href: "/products", icon: "inventory_2", perm: "products.view" },
  { label: "Leads", href: "/leads", icon: "person_search", perm: "leads.view" },
  { label: "Onboarding", href: "/onboarding", icon: "schedule_send", perm: "onboarding.view" },
  { label: "Pendências", href: "/onboarding/pendencias", icon: "report", perm: "onboarding.view" },
  { label: "Templates", href: "/templates", icon: "sms", perm: "templates.view" },
  { label: "Usuários", href: "/users", icon: "manage_accounts", perm: "users.view" },
  { label: "Perfis", href: "/profiles", icon: "badge", perm: "profiles.view" },
];

const SETTINGS_CHILDREN: NavEntry[] = [
  { label: "Integrações", href: "/settings", icon: "hub", perm: "settings.view", exact: true },
  { label: "Comportamento", href: "/settings/comportamento", icon: "tune", perm: "settings.view", exact: true },
  { label: "API / Tokens", href: "/settings/tokens", icon: "key", perm: "tokens.view", exact: true },
];

const ADMIN_CHILDREN: NavEntry[] = [
  { label: "Auditoria", href: "/administracao/auditoria", icon: "policy", perm: "audit.view" },
  { label: "Histórico de Acesso", href: "/administracao/acesso", icon: "manage_accounts", perm: "audit.view" },
];

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

function SettingsChildItem({ href, icon, label, active }: { href: string; icon: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-3 rounded-lg py-2 pl-9 pr-3 text-label-lg transition-colors",
        active
          ? "bg-surface-container font-semibold text-on-surface"
          : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface"
      )}
    >
      <span
        className="material-symbols-outlined"
        style={{ fontSize: "18px", fontVariationSettings: active ? "'FILL' 1" : "'FILL' 0" }}
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
  const { can } = usePermission();
  const { user } = useAuth();
  const { blobUrl: avatarUrl } = useAvatar();

  const visibleItems = NAV_ITEMS.filter((item) => can(item.perm));
  const visibleSettings = SETTINGS_CHILDREN.filter((item) => can(item.perm));

  const settingsHrefs = SETTINGS_CHILDREN.map((c) => c.href);
  const onSettingsRoute = settingsHrefs.includes(pathname);
  const [settingsOpen, setSettingsOpen] = useState(onSettingsRoute);

  const visibleAdmin = ADMIN_CHILDREN.filter((item) => can(item.perm));
  const adminHrefs = ADMIN_CHILDREN.map((c) => c.href);
  const onAdminRoute = adminHrefs.some((h) => pathname.startsWith(h));
  const [adminOpen, setAdminOpen] = useState(onAdminRoute);

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
          const active = item.exact
            ? pathname === item.href
            : isPrefixMatch && !hasMoreSpecific;
          return <NavItem key={item.href} {...item} active={active} />;
        })}

        {visibleSettings.length > 0 && (
          <div>
            <button
              type="button"
              onClick={() => setSettingsOpen((v) => !v)}
              aria-expanded={settingsOpen}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-body-sm transition-colors",
                onSettingsRoute
                  ? "bg-surface-container font-semibold text-on-surface"
                  : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface"
              )}
            >
              <span
                className="material-symbols-outlined"
                style={{ fontSize: "20px", fontVariationSettings: onSettingsRoute ? "'FILL' 1" : "'FILL' 0" }}
              >
                settings
              </span>
              <span className="flex-1 text-left">Configurações</span>
              <span
                className={cn(
                  "material-symbols-outlined transition-transform duration-200",
                  settingsOpen && "rotate-180"
                )}
                style={{ fontSize: "20px" }}
              >
                expand_more
              </span>
            </button>

            <div
              className={cn(
                "overflow-hidden transition-all duration-300 ease-in-out",
                settingsOpen ? "max-h-60 opacity-100" : "max-h-0 opacity-0"
              )}
            >
              <div className="mt-1 space-y-1">
                {visibleSettings.map((child) => (
                  <SettingsChildItem
                    key={child.href}
                    {...child}
                    active={pathname === child.href}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {visibleAdmin.length > 0 && (
          <div>
            <button
              type="button"
              onClick={() => setAdminOpen((v) => !v)}
              aria-expanded={adminOpen}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-body-sm transition-colors",
                onAdminRoute
                  ? "bg-surface-container font-semibold text-on-surface"
                  : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface"
              )}
            >
              <span
                className="material-symbols-outlined"
                style={{ fontSize: "20px", fontVariationSettings: onAdminRoute ? "'FILL' 1" : "'FILL' 0" }}
              >
                admin_panel_settings
              </span>
              <span className="flex-1 text-left">Administração</span>
              <span
                className={cn(
                  "material-symbols-outlined transition-transform duration-200",
                  adminOpen && "rotate-180"
                )}
                style={{ fontSize: "20px" }}
              >
                expand_more
              </span>
            </button>

            <div
              className={cn(
                "overflow-hidden transition-all duration-300 ease-in-out",
                adminOpen ? "max-h-60 opacity-100" : "max-h-0 opacity-0"
              )}
            >
              <div className="mt-1 space-y-1">
                {visibleAdmin.map((child) => (
                  <SettingsChildItem
                    key={child.href}
                    {...child}
                    active={pathname === child.href}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </nav>

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
