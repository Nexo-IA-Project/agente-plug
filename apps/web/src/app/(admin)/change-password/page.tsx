"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { ChangePasswordForm } from "@/features/profile/components/ChangePasswordForm";
import { clearToken } from "@/lib/auth";

export default function ChangePasswordPage() {
  const router = useRouter();
  const { user } = useAuth();

  function onSuccess() {
    // Token tem must_change_password=true — forçar re-login para obter token novo
    clearToken();
    router.replace("/login");
  }

  if (!user) return null;

  return (
    <div className="mx-auto max-w-md p-8 flex flex-col gap-6">
      <h1 className="text-headline-md">Defina uma nova senha</h1>
      <p className="text-body-md text-on-surface-variant">
        Por segurança, você precisa trocar sua senha antes de continuar. Após a
        alteração, você será redirecionado para a tela de login.
      </p>
      <ChangePasswordForm onSuccess={onSuccess} />
    </div>
  );
}
