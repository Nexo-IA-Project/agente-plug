"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { getMe, updateMe, myAvatarUrl } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import { AvatarUploadModal } from "@/features/profile/components/AvatarUploadModal";
import { ChangePasswordForm } from "@/features/profile/components/ChangePasswordForm";
import type { MeResponse } from "@/features/profile/types";

export default function ProfilePage() {
  const { refresh } = useAuth();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [name, setName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [avatarOpen, setAvatarOpen] = useState(false);
  const [avatarVersion, setAvatarVersion] = useState(Date.now());
  const toast = useToast();

  useEffect(() => {
    getMe()
      .then((m) => {
        setMe(m);
        setName(m.name);
      })
      .catch(() => {
        toast.error("Falha ao carregar perfil");
      });
  }, [toast]);

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
      <div className="p-8 flex items-center justify-center">
        <span className="text-on-surface-variant">Carregando...</span>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl p-8 flex flex-col gap-8">
      <h1 className="text-headline-md">Meu perfil</h1>

      {/* Avatar */}
      <section className="flex items-center gap-6">
        <button
          onClick={() => setAvatarOpen(true)}
          className="relative h-24 w-24 rounded-full overflow-hidden bg-surface-container hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-primary"
          title="Trocar foto"
        >
          {me.has_avatar ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={myAvatarUrl(avatarVersion)}
              alt={me.name}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-4xl text-on-surface-variant">
              {me.name.charAt(0).toUpperCase()}
            </div>
          )}
        </button>
        <div className="flex flex-col gap-1">
          <span className="text-body-lg font-medium">{me.name}</span>
          <span className="text-body-sm text-on-surface-variant">{me.email}</span>
          <span className="text-body-sm text-on-surface-variant">
            Papel:{" "}
            <strong>{me.role === "admin" ? "Administrador" : "Operador"}</strong>
          </span>
        </div>
      </section>

      {/* Nome */}
      <section className="flex flex-col gap-3 max-w-md">
        <h2 className="text-title-md">Nome</h2>
        <div className="flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1 px-3 py-2 rounded border border-outline-variant bg-surface"
          />
          <button
            onClick={onSaveName}
            disabled={savingName || name === me.name}
            className="px-4 py-2 rounded bg-primary text-on-primary disabled:opacity-50"
          >
            Salvar
          </button>
        </div>
      </section>

      {/* Senha */}
      <section className="flex flex-col gap-3">
        <h2 className="text-title-md">Alterar senha</h2>
        <ChangePasswordForm onSuccess={refresh} />
      </section>

      {/* Modal de crop */}
      <AvatarUploadModal
        open={avatarOpen}
        onClose={() => setAvatarOpen(false)}
        onSaved={() => {
          setAvatarVersion(Date.now());
          setMe((prev) => (prev ? { ...prev, has_avatar: true } : prev));
        }}
      />
    </div>
  );
}
