"use client";

import { usePermissionContext } from "@/features/auth/context/PermissionContext";

export function usePermission() {
  const { permissions, isAdmin, loading } = usePermissionContext();
  const can = (key: string): boolean => isAdmin || permissions.has(key);
  return { isAdmin, loading, can };
}
