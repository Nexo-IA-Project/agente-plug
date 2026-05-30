// apps/web/src/features/profiles/components/ProfileListTable.tsx
"use client";

import type { ProfileListItem } from "@/features/profiles/types";

interface Props {
  profiles: ProfileListItem[];
  onEdit: (p: ProfileListItem) => void;
  onDelete: (p: ProfileListItem) => void;
}

export function ProfileListTable({ profiles, onEdit, onDelete }: Props) {
  return (
    <div className="overflow-x-auto rounded-lg border border-outline-variant">
      <table className="w-full text-body-sm">
        <thead className="bg-surface-container">
          <tr>
            <th className="px-4 py-3 text-left text-on-surface-variant">Nome</th>
            <th className="px-4 py-3 text-left text-on-surface-variant">Permissões</th>
            <th className="px-4 py-3 text-left text-on-surface-variant">Usuários</th>
            <th className="px-4 py-3 text-right text-on-surface-variant">Ações</th>
          </tr>
        </thead>
        <tbody>
          {profiles.map((p) => (
            <tr key={p.id} className="border-t border-outline-variant hover:bg-surface-container-low">
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="text-on-surface">{p.name}</span>
                  {p.is_system && (
                    <span className="inline-block rounded-full bg-surface-variant px-2 py-0.5 text-label-sm text-on-surface-variant">
                      Sistema
                    </span>
                  )}
                </div>
              </td>
              <td className="px-4 py-3 text-on-surface-variant">{p.permission_count}</td>
              <td className="px-4 py-3 text-on-surface-variant">{p.user_count}</td>
              <td className="px-4 py-3">
                <div className="flex justify-end gap-1">
                  {p.is_system ? (
                    <span
                      title="Perfil de sistema"
                      className="p-1.5 text-on-surface-variant/40"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 18 }}>lock</span>
                    </span>
                  ) : (
                    <>
                      <button
                        onClick={() => onEdit(p)}
                        title="Editar"
                        className="rounded p-1.5 hover:bg-surface-container"
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 18 }}>edit</span>
                      </button>
                      <button
                        onClick={() => onDelete(p)}
                        title="Excluir"
                        className="rounded p-1.5 text-error hover:bg-error-container"
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 18 }}>delete</span>
                      </button>
                    </>
                  )}
                </div>
              </td>
            </tr>
          ))}
          {profiles.length === 0 && (
            <tr>
              <td colSpan={4} className="px-4 py-8 text-center text-on-surface-variant">
                Nenhum perfil encontrado.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
