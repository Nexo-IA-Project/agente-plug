// apps/web/src/features/users/components/UserDrawer.tsx
"use client";

import { useEffect, useState } from "react";
import { Drawer } from "@/shared/components/Drawer";
import type { User, CreateUserInput, UpdateUserInput } from "@/features/users/types";
import type { ProfileListItem } from "@/features/profiles/types";

interface Props {
  open: boolean;
  user: User | null;
  profiles: ProfileListItem[];
  onClose: () => void;
  onSubmit: (input: CreateUserInput | UpdateUserInput) => Promise<void>;
}

export function UserDrawer({ open, user, profiles, onClose, onSubmit }: Props) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"admin" | "operator">("operator");
  const [isActive, setIsActive] = useState(true);
  const [profileId, setProfileId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user) {
      setName(user.name);
      setEmail(user.email);
      setRole(user.role);
      setIsActive(user.is_active);
      setProfileId(user.profile_id);
    } else {
      setName("");
      setEmail("");
      setRole("operator");
      setIsActive(true);
      setProfileId(null);
    }
  }, [user, open]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      if (user) {
        await onSubmit({ name, role, is_active: isActive, profile_id: profileId } as UpdateUserInput);
      } else {
        await onSubmit({ name, email, role, profile_id: profileId } as CreateUserInput);
      }
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Drawer open={open} onClose={onClose} title={user ? "Editar usuário" : "Novo usuário"}>
      <form onSubmit={submit} className="flex flex-col gap-4 p-4">
        <label className="flex flex-col gap-1">
          <span className="text-body-sm">Nome</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="px-3 py-2 rounded border border-outline-variant bg-surface"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-body-sm">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required={!user}
            disabled={!!user}
            className="px-3 py-2 rounded border border-outline-variant bg-surface disabled:opacity-60"
          />
          {user && (
            <span className="text-label-sm text-on-surface-variant">
              Email não pode ser alterado
            </span>
          )}
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-body-sm">Papel</span>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as "admin" | "operator")}
            className="px-3 py-2 rounded border border-outline-variant bg-surface"
          >
            <option value="operator">Operador</option>
            <option value="admin">Administrador</option>
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-body-sm">Perfil</span>
          <select
            value={profileId ?? ""}
            onChange={(e) => setProfileId(e.target.value === "" ? null : e.target.value)}
            className="px-3 py-2 rounded border border-outline-variant bg-surface"
          >
            <option value="">Sem perfil</option>
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.is_system ? `${p.name} (sistema)` : p.name}
              </option>
            ))}
          </select>
        </label>
        {user && (
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            <span className="text-body-sm">Usuário ativo</span>
          </label>
        )}
        {!user && (
          <p className="text-label-sm text-on-surface-variant">
            Uma senha temporária será gerada e enviada por email.
          </p>
        )}
        <div className="flex justify-end gap-2 mt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-2 rounded bg-surface-container"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={saving}
            className="px-3 py-2 rounded bg-primary text-on-primary disabled:opacity-50"
          >
            {saving ? "Salvando..." : user ? "Salvar" : "Criar e enviar email"}
          </button>
        </div>
      </form>
    </Drawer>
  );
}
