"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AuthProvider, useAuthContext } from "@/features/auth/context/AuthContext";

function MustChangePasswordGate({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuthContext();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!user) return;
    if (user.must_change_password && pathname !== "/change-password") {
      router.replace("/change-password");
    }
  }, [isLoading, user, pathname, router]);

  return <>{children}</>;
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <MustChangePasswordGate>{children}</MustChangePasswordGate>
    </AuthProvider>
  );
}
