// apps/web/src/app/(admin)/users/page.tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import {
  listUsers,
  createUser,
  updateUser,
  deleteUser,
  resetUserPassword,
  listProfiles,
} from "@/lib/api";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useToast } from "@/shared/hooks/useToast";
import { UserListTable } from "@/features/users/components/UserListTable";
import { UserDrawer } from "@/features/users/components/UserDrawer";
import { ResetPasswordDialog } from "@/features/users/components/ResetPasswordDialog";
import { RequirePermission } from "@/features/auth/components/RequirePermission";
import type { User, CreateUserInput, UpdateUserInput } from "@/features/users/types";
import type { ProfileListItem } from "@/features/profiles/types";

export default function UsersPage() {
  return (
    <RequirePermission perm="users.view">
      <UsersContent />
    </RequirePermission>
  );
}

function UsersContent() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [profiles, setProfiles] = useState<ProfileListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [drawerUser, setDrawerUser] = useState<User | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [resetUser, setResetUser] = useState<User | null>(null);
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [res, profileList] = await Promise.all([listUsers(), listProfiles()]);
      setUsers(res.items);
      setProfiles(profileList);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao carregar usuários");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function onCreate(input: CreateUserInput | UpdateUserInput) {
    try {
      await createUser(input as CreateUserInput);
      toast.success("Usuário criado e email enviado");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao criar usuário");
      throw e;
    }
  }

  async function onUpdate(input: CreateUserInput | UpdateUserInput) {
    if (!drawerUser) return;
    try {
      await updateUser(drawerUser.id, input as UpdateUserInput);
      toast.success("Usuário atualizado");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao atualizar");
      throw e;
    }
  }

  async function onDelete(u: User) {
    if (!confirm(`Excluir ${u.name}? Esta ação é permanente.`)) return;
    try {
      await deleteUser(u.id);
      toast.success("Usuário excluído");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao excluir");
    }
  }

  async function onResetConfirm() {
    if (!resetUser) return;
    try {
      await resetUserPassword(resetUser.id);
      toast.success("Senha resetada e email enviado");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao resetar senha");
    } finally {
      setResetUser(null);
    }
  }

  return (
    <div className="p-8 flex flex-col gap-6">
      <header className="flex items-center justify-between">
        <h1 className="text-headline-md">Usuários</h1>
        <button
          onClick={() => {
            setDrawerUser(null);
            setDrawerOpen(true);
          }}
          className="px-4 py-2 rounded bg-primary text-on-primary"
        >
          + Novo usuário
        </button>
      </header>

      {loading ? (
        <div className="text-on-surface-variant">Carregando...</div>
      ) : (
        <UserListTable
          users={users}
          currentUserId={currentUser?.id ?? ""}
          onEdit={(u) => {
            setDrawerUser(u);
            setDrawerOpen(true);
          }}
          onResetPassword={(u) => setResetUser(u)}
          onDelete={onDelete}
        />
      )}

      <UserDrawer
        open={drawerOpen}
        user={drawerUser}
        profiles={profiles}
        onClose={() => setDrawerOpen(false)}
        onSubmit={drawerUser ? onUpdate : onCreate}
      />

      <ResetPasswordDialog
        open={!!resetUser}
        user={resetUser}
        onClose={() => setResetUser(null)}
        onConfirm={onResetConfirm}
      />
    </div>
  );
}
