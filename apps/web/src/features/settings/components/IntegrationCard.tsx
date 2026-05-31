import Link from "next/link";
import type { ReactNode } from "react";

interface IntegrationCardProps {
  icon?: string;
  iconSvg?: ReactNode;
  title: string;
  subtitle: string;
  status?: "active" | "soon";
  href?: string;
  onClick?: () => void;
}

export function IntegrationCard({
  icon,
  iconSvg,
  title,
  subtitle,
  status = "active",
  href,
  onClick,
}: IntegrationCardProps) {
  const isSoon = status === "soon";
  const navegavel = !isSoon && (Boolean(href) || Boolean(onClick));

  const inner = (
    <>
      <div className="flex items-start justify-between gap-3">
        <div
          className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${
            isSoon
              ? "bg-surface-variant text-on-surface-variant"
              : "bg-primary-container text-on-primary-container"
          }`}
        >
          {iconSvg ?? (
            <span className="material-symbols-outlined" style={{ fontSize: "26px" }}>
              {icon}
            </span>
          )}
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
            isSoon
              ? "bg-surface-container text-on-surface-variant"
              : "bg-[color:var(--color-tertiary-container)] text-[color:var(--color-on-tertiary-container)]"
          }`}
        >
          {isSoon ? "Em breve" : "Ativo"}
        </span>
      </div>

      <div className="mt-4 flex items-end justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-on-surface">{title}</h3>
          <p className="mt-1 text-sm text-on-surface-variant">{subtitle}</p>
        </div>
        {navegavel && (
          <span
            className="material-symbols-outlined shrink-0 text-on-surface-variant/70"
            style={{ fontSize: "22px" }}
          >
            chevron_right
          </span>
        )}
      </div>
    </>
  );

  const className =
    "group block w-full rounded-2xl border border-outline-variant bg-white p-5 text-left transition-all hover:border-primary/40 hover:shadow-sm dark:bg-surface-container";

  if (href) {
    return (
      <Link href={href} className={`${className} cursor-pointer`}>
        {inner}
      </Link>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={`${className} ${onClick ? "cursor-pointer" : "cursor-default"}`}
    >
      {inner}
    </button>
  );
}
