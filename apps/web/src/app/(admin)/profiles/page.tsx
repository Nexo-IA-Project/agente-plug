// apps/web/src/app/(admin)/profiles/page.tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { listProfiles, getProfile, deleteProfile } from "@/lib/api";
import { usePermission } from "@/features/auth/hooks/usePermission";
import { useToast } from "@/shared/hooks/useToast";
import { ProfileListTable } from "@/features/profiles/components/ProfileListTable";
import { ProfileDrawer } from "@/features/profiles/components/ProfileDrawer";
import type { ProfileListItem, ProfileDetail } from "@/features/profiles/types";

export default function ProfilesPage() {
  const { isAdmin } = usePermission();
  const [profiles, setProfiles] = useState<ProfileListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [drawerProfile, setDrawerProfile] = useState<ProfileDetail | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const items = await listProfiles();
      setProfiles(items);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao carregar perfis");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (!isAdmin) {
    return (
      <div className="p-8">
        <p className="text-on-surface-variant">Acesso restrito a administradores.</p>
      </div>
    );
  }

  function openCreate() {
    setDrawerProfile(null);
    setDrawerOpen(true);
  }

  async function openEdit(p: ProfileListItem) {
    try {
      const detail = await getProfile(p.id);
      setDrawerProfile(detail);
      setDrawerOpen(true);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao carregar perfil");
    }
  }

  async function onDelete(p: ProfileListItem) {
    if (!confirm(`Excluir o perfil "${p.name}"? Esta ação é permanente.`)) return;
    try {
      await deleteProfile(p.id);
      toast.success("Perfil excluído");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao excluir perfil");
    }
  }

  function onSaved() {
    setDrawerOpen(false);
    load();
  }

  return (
    <div className="flex flex-col gap-6 p-8">
      <header className="flex items-center justify-between">
        <h1 className="text-headline-md">Perfis</h1>
        <button onClick={openCreate} className="rounded bg-primary px-4 py-2 text-on-primary">
          + Novo perfil
        </button>
      </header>

      {loading ? (
        <div className="text-on-surface-variant">Carregando...</div>
      ) : (
        <ProfileListTable profiles={profiles} onEdit={openEdit} onDelete={onDelete} />
      )}

      <ProfileDrawer
        open={drawerOpen}
        profile={drawerProfile}
        onClose={() => setDrawerOpen(false)}
        onSaved={onSaved}
      />
    </div>
  );
}
