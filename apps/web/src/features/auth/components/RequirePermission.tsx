"use client";

import { usePermission } from "@/features/auth/hooks/usePermission";

export function RequirePermission({
  perm,
  children,
}: {
  perm: string;
  children: React.ReactNode;
}) {
  const { loading, can } = usePermission();

  if (loading) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-on-surface-variant">
        <span className="material-symbols-outlined animate-spin" style={{ fontSize: "32px" }}>
          progress_activity
        </span>
        <p className="text-body-md">Carregando...</p>
      </div>
    );
  }

  if (!can(perm)) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
        <span
          className="material-symbols-outlined text-on-surface-variant"
          style={{ fontSize: "40px" }}
        >
          lock
        </span>
        <h2 className="text-title-lg font-semibold text-on-surface">Acesso restrito</h2>
        <p className="max-w-sm text-body-md text-on-surface-variant">
          Você não tem permissão para ver esta página.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
