// apps/web/src/shared/components/InactivityGuard.tsx
"use client";

import { useEffect, useRef } from "react";
import { clearToken } from "@/lib/auth";

const INACTIVITY_MS = 8 * 60 * 60 * 1000; // 8 horas
const EVENTS = ["mousemove", "keydown", "click", "scroll", "touchstart"] as const;

export function InactivityGuard({ children }: { children: React.ReactNode }) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function logout() {
      clearToken();
      window.location.href = "/login";
    }

    function reset() {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(logout, INACTIVITY_MS);
    }

    reset();
    EVENTS.forEach((e) => window.addEventListener(e, reset, { passive: true }));

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      EVENTS.forEach((e) => window.removeEventListener(e, reset));
    };
  }, []);

  return <>{children}</>;
}
