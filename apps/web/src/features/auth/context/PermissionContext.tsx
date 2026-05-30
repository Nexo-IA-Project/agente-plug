"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useAuthContext } from "@/features/auth/context/AuthContext";
import { getMe } from "@/lib/api";

interface PermissionContextValue {
  permissions: Set<string>;
  isAdmin: boolean;
  loading: boolean;
  refresh: () => void;
}

const Ctx = createContext<PermissionContextValue | undefined>(undefined);

export function PermissionProvider({ children }: { children: React.ReactNode }) {
  const { user, isLoading: authLoading } = useAuthContext();
  const [permissions, setPermissions] = useState<Set<string>>(new Set());
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    if (authLoading) return;
    if (!user) {
      setPermissions(new Set());
      setIsAdmin(false);
      setLoading(false);
      return;
    }
    setLoading(true);
    getMe()
      .then((me) => {
        setPermissions(new Set(me.permissions ?? []));
        setIsAdmin(me.role === "admin");
        setLoading(false);
      })
      .catch(() => {
        setPermissions(new Set());
        setIsAdmin(false);
        setLoading(false);
      });
  }, [authLoading, user]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <Ctx.Provider value={{ permissions, isAdmin, loading, refresh }}>{children}</Ctx.Provider>
  );
}

export function usePermissionContext(): PermissionContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("usePermissionContext must be used inside PermissionProvider");
  return v;
}
