// apps/web/src/features/profiles/components/ProfileDrawer.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { Drawer } from "@/shared/components/Drawer";
import { useToast } from "@/shared/hooks/useToast";
import { getPermissionCatalog, createProfile, updateProfile } from "@/lib/api";
import type { ProfileDetail, PermissionGroup } from "@/features/profiles/types";

interface Props {
  open: boolean;
  profile: ProfileDetail | null; // null = criar
  onClose: () => void;
  onSaved: () => void;
}

const MODULE_LABELS: Record<string, string> = {
  dashboard: "Painel",
  kb: "Base de Conhecimento",
  products: "Produtos",
  leads: "Leads",
  onboarding: "Onboarding",
  templates: "Templates",
  users: "Usuários",
  profiles: "Perfis",
  settings: "Configurações",
  tokens: "Tokens",
  accounts: "Contas",
};

function moduleLabel(module: string): string {
  return MODULE_LABELS[module] ?? module.charAt(0).toUpperCase() + module.slice(1);
}

/** Checkbox-mestre que reflete estado parcial (indeterminate) via ref. */
function MasterCheckbox({
  checked,
  indeterminate,
  disabled,
  onChange,
}: {
  checked: boolean;
  indeterminate: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate && !checked;
  }, [indeterminate, checked]);
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      disabled={disabled}
      onChange={(e) => onChange(e.target.checked)}
    />
  );
}

export function ProfileDrawer({ open, profile, onClose, onSaved }: Props) {
  const toast = useToast();
  const [catalog, setCatalog] = useState<PermissionGroup[] | null>(null);
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  const readOnly = !!profile?.is_system;

  // Carrega catálogo uma vez (cache em estado).
  useEffect(() => {
    if (!open || catalog || loadingCatalog) return;
    setLoadingCatalog(true);
    getPermissionCatalog()
      .then(setCatalog)
      .catch((e) =>
        toast.error(e instanceof Error ? e.message : "Falha ao carregar permissões"),
      )
      .finally(() => setLoadingCatalog(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Reinicializa form ao abrir / trocar de perfil.
  useEffect(() => {
    if (!open) return;
    setName(profile?.name ?? "");
    setSelected(new Set(profile?.permissions ?? []));
  }, [open, profile]);

  function toggleOne(key: string, next: boolean) {
    setSelected((prev) => {
      const copy = new Set(prev);
      if (next) copy.add(key);
      else copy.delete(key);
      return copy;
    });
  }

  function toggleModule(group: PermissionGroup, next: boolean) {
    setSelected((prev) => {
      const copy = new Set(prev);
      for (const perm of group.permissions) {
        if (next) copy.add(perm.key);
        else copy.delete(perm.key);
      }
      return copy;
    });
  }

  async function handleSave() {
    if (!name.trim()) {
      toast.error("Informe um nome para o perfil");
      return;
    }
    setSaving(true);
    try {
      const input = { name: name.trim(), permissions: [...selected] };
      if (profile) {
        await updateProfile(profile.id, input);
        toast.success("Perfil atualizado");
      } else {
        await createProfile(input);
        toast.success("Perfil criado");
      }
      onSaved();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao salvar perfil");
    } finally {
      setSaving(false);
    }
  }

  const title = profile ? (readOnly ? "Perfil de sistema" : "Editar perfil") : "Novo perfil";

  const footer = readOnly ? (
    <div className="flex justify-end">
      <button onClick={onClose} className="rounded bg-surface-container px-3 py-2">
        Fechar
      </button>
    </div>
  ) : (
    <div className="flex justify-end gap-2">
      <button
        type="button"
        onClick={onClose}
        className="rounded bg-surface-container px-3 py-2"
      >
        Cancelar
      </button>
      <button
        type="button"
        onClick={handleSave}
        disabled={saving}
        className="rounded bg-primary px-3 py-2 text-on-primary disabled:opacity-50"
      >
        {saving ? "Salvando..." : "Salvar"}
      </button>
    </div>
  );

  return (
    <Drawer open={open} onClose={onClose} title={title} footer={footer}>
      <div className="flex flex-col gap-6">
        {readOnly && (
          <div className="rounded-lg border border-outline-variant bg-surface-container-low px-4 py-3 text-body-sm text-on-surface-variant">
            Este é um perfil de sistema e não pode ser editado.
          </div>
        )}

        <label className="flex flex-col gap-1">
          <span className="text-body-sm">Nome</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            disabled={readOnly}
            placeholder="Ex.: Suporte, Marketing..."
            className="rounded border border-outline-variant bg-surface px-3 py-2 disabled:opacity-60"
          />
        </label>

        <div className="flex flex-col gap-2">
          <span className="text-body-sm text-on-surface-variant">Permissões</span>

          {loadingCatalog && (
            <div className="text-body-sm text-on-surface-variant">Carregando permissões...</div>
          )}

          {!loadingCatalog && catalog && (
            <div className="flex flex-col gap-3">
              {catalog.map((group) => {
                const total = group.permissions.length;
                const checkedCount = group.permissions.filter((p) =>
                  selected.has(p.key),
                ).length;
                const allChecked = total > 0 && checkedCount === total;
                const someChecked = checkedCount > 0 && checkedCount < total;

                return (
                  <fieldset
                    key={group.module}
                    className="rounded-lg border border-outline-variant"
                  >
                    <legend className="sr-only">{moduleLabel(group.module)}</legend>
                    <label className="flex cursor-pointer items-center gap-3 border-b border-outline-variant px-4 py-3">
                      <MasterCheckbox
                        checked={allChecked}
                        indeterminate={someChecked}
                        disabled={readOnly}
                        onChange={(next) => toggleModule(group, next)}
                      />
                      <span className="flex-1 text-body-sm font-semibold text-on-surface">
                        {moduleLabel(group.module)}
                      </span>
                      <span className="text-label-sm text-on-surface-variant">
                        {checkedCount}/{total}
                      </span>
                    </label>

                    <div className="flex flex-col gap-2 px-4 py-3">
                      {group.permissions.map((perm) => (
                        <label
                          key={perm.key}
                          className="flex cursor-pointer items-center gap-3"
                        >
                          <input
                            type="checkbox"
                            checked={selected.has(perm.key)}
                            disabled={readOnly}
                            onChange={(e) => toggleOne(perm.key, e.target.checked)}
                          />
                          <span className="flex-1 text-body-sm text-on-surface">
                            {perm.label}
                          </span>
                          <span className="text-label-sm text-on-surface-variant">
                            {perm.action}
                          </span>
                        </label>
                      ))}
                    </div>
                  </fieldset>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </Drawer>
  );
}
