"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { getToken, clearToken } from "@/lib/auth";
import { decodeJwt, type AuthTokenPayload } from "@/features/auth/lib/jwt";

export interface AuthUser {
  id: string;
  email: string;
  role: "admin" | "operator";
  must_change_password: boolean;
}

interface AuthContextValue {
  user: AuthUser | null;
  /** UUID da conta (tenant) ativa, extraído do JWT. null se não autenticado. */
  accountId: string | null;
  isLoading: boolean;
  refresh: () => void;
  logout: () => void;
}

const Ctx = createContext<AuthContextValue | undefined>(undefined);

function payloadToUser(p: AuthTokenPayload | null): AuthUser | null {
  if (!p) return null;
  return {
    id: p.user_id,
    email: p.sub,
    role: p.role,
    must_change_password: p.must_change_password,
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accountId, setAccountId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(() => {
    const token = getToken();
    const payload = token ? decodeJwt(token) : null;
    setUser(payloadToUser(payload));
    setAccountId(payload?.account_id ?? null);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    setAccountId(null);
    window.location.href = "/login";
  }, []);

  return (
    <Ctx.Provider value={{ user, accountId, isLoading, refresh, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuthContext(): AuthContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuthContext must be used inside AuthProvider");
  return v;
}
