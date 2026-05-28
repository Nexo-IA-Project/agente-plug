"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { getMe, updateMe } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import { useAvatarBlob } from "@/features/profile/hooks/useAvatarBlob";
import { AvatarUploadModal } from "@/features/profile/components/AvatarUploadModal";
import { ChangePasswordForm } from "@/features/profile/components/ChangePasswordForm";
import type { MeResponse } from "@/features/profile/types";

export default function ProfilePage() {
  const { refresh } = useAuth();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [name, setName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [avatarOpen, setAvatarOpen] = useState(false);
  const toast = useToast();

  // Carrega avatar via fetch autenticado (cross-origin safe)
  const { blobUrl: avatarBlobUrl, refreshAvatar } = useAvatarBlob(
    me?.has_avatar ?? false
  );

  useEffect(() => {
    getMe()
      .then((m) => { setMe(m); setName(m.name); })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onSaveName() {
    if (!name.trim()) return;
    setSavingName(true);
    try {
      const updated = await updateMe(name.trim());
      setMe(updated);
      toast.success("Nome atualizado");
    } catch {
      toast.error("Falha ao atualizar nome");
    } finally {
      setSavingName(false);
    }
  }

  if (!me) {
    return (
      <div className="flex min-h-[200px] items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-on-surface-variant">
          <span className="material-symbols-outlined animate-spin" style={{ fontSize: "20px" }}>
            progress_activity
          </span>
          Carregando perfil...
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      {/* Page header */}
      <header className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
        <div className="flex items-center gap-5 px-7 py-6">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary-container">
            <span
              className="material-symbols-outlined text-on-primary-container"
              style={{ fontSize: "28px", fontVariationSettings: "'FILL' 1" }}
            >
              account_circle
            </span>
          </div>
          <div>
            <h1 className="text-2xl font-bold text-on-surface">Meu perfil</h1>
            <p className="mt-1 text-sm text-on-surface-variant">
              Foto, nome e senha da sua conta
            </p>
          </div>
        </div>
      </header>

      {/* Avatar + identidade */}
      <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
        <div className="flex items-center gap-3 border-b border-outline-variant/60 bg-surface-container-low dark:bg-surface-container px-5 py-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-container">
            <span
              className="material-symbols-outlined text-on-primary-container"
              style={{ fontSize: "20px", fontVariationSettings: "'FILL' 1" }}
            >
              badge
            </span>
          </div>
          <div>
            <p className="text-sm font-semibold text-on-surface">Identidade</p>
            <p className="text-xs text-on-surface-variant">Foto e nome de exibição</p>
          </div>
        </div>

        <div className="flex items-center gap-6 px-5 py-5">
          {/* Avatar clicável */}
          <button
            onClick={() => setAvatarOpen(true)}
            className="group relative h-20 w-20 shrink-0 rounded-full overflow-hidden focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
            title="Trocar foto"
          >
            {avatarBlobUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={avatarBlobUrl}
                alt={me.name}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center bg-primary text-3xl font-bold text-on-primary">
                {me.name.charAt(0).toUpperCase()}
              </div>
            )}
            {/* Overlay no hover */}
            <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition-opacity group-hover:opacity-100">
              <span className="material-symbols-outlined text-white" style={{ fontSize: "20px" }}>
                photo_camera
              </span>
            </div>
          </button>

          <div className="flex flex-1 flex-col gap-3">
            {/* Nome editável */}
            <div className="flex flex-col gap-1">
              <span className="text-xs font-medium text-on-surface-variant">Nome</span>
              <div className="flex gap-2">
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="flex-1 rounded-xl border border-outline-variant bg-surface px-3.5 py-2 text-sm text-on-surface outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                />
                <button
                  onClick={onSaveName}
                  disabled={savingName || name === me.name}
                  className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:opacity-90 disabled:opacity-40"
                >
                  Salvar
                </button>
              </div>
            </div>
            {/* Email (readonly) */}
            <div className="flex flex-col gap-1">
              <span className="text-xs font-medium text-on-surface-variant">Email</span>
              <div className="flex items-center gap-2 rounded-xl border border-outline-variant/50 bg-surface-container-low px-3.5 py-2">
                <span className="text-sm text-on-surface">{me.email}</span>
                <span className="ml-auto rounded-full bg-surface-container px-2 py-0.5 text-xs text-on-surface-variant">
                  imutável
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Role badge */}
        <div className="flex items-center gap-2 border-t border-outline-variant/60 bg-surface-container-low/50 px-5 py-3">
          <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: "16px" }}>
            {me.role === "admin" ? "admin_panel_settings" : "person"}
          </span>
          <span className="text-xs text-on-surface-variant">
            Papel:{" "}
            <strong className="text-on-surface">
              {me.role === "admin" ? "Administrador" : "Operador"}
            </strong>
          </span>
        </div>
      </div>

      {/* Senha */}
      <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
        <div className="flex items-center gap-3 border-b border-outline-variant/60 bg-surface-container-low dark:bg-surface-container px-5 py-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-container">
            <span
              className="material-symbols-outlined text-on-primary-container"
              style={{ fontSize: "20px", fontVariationSettings: "'FILL' 1" }}
            >
              lock
            </span>
          </div>
          <div>
            <p className="text-sm font-semibold text-on-surface">Segurança</p>
            <p className="text-xs text-on-surface-variant">Alterar sua senha de acesso</p>
          </div>
        </div>
        <div className="px-5 py-5">
          <ChangePasswordForm onSuccess={refresh} />
        </div>
      </div>

      {/* Modal de crop */}
      <AvatarUploadModal
        open={avatarOpen}
        onClose={() => setAvatarOpen(false)}
        onSaved={() => {
          setMe((prev) => (prev ? { ...prev, has_avatar: true } : prev));
          refreshAvatar(); // recarrega o blob sem recarregar a página
        }}
      />
    </div>
  );
}
