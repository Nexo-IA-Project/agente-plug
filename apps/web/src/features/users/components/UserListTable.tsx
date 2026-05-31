// apps/web/src/features/users/components/UserListTable.tsx
"use client";

import type { User } from "@/features/users/types";

interface Props {
  users: User[];
  onEdit: (u: User) => void;
  onResetPassword: (u: User) => void;
  onDelete: (u: User) => void;
  currentUserId: string;
  canManage?: boolean;
}

export function UserListTable({
  users,
  onEdit,
  onResetPassword,
  onDelete,
  currentUserId,
  canManage = true,
}: Props) {
  return (
    <div className="overflow-x-auto rounded-lg border border-outline-variant">
      <table className="w-full text-body-sm">
        <thead className="bg-surface-container">
          <tr>
            <th className="px-4 py-3 text-left text-on-surface-variant">Nome</th>
            <th className="px-4 py-3 text-left text-on-surface-variant">Email</th>
            <th className="px-4 py-3 text-left text-on-surface-variant">Papel</th>
            <th className="px-4 py-3 text-left text-on-surface-variant">Perfil</th>
            <th className="px-4 py-3 text-left text-on-surface-variant">Status</th>
            <th className="px-4 py-3 text-left text-on-surface-variant">Último login</th>
            <th className="px-4 py-3 text-right text-on-surface-variant">Ações</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className="border-t border-outline-variant hover:bg-surface-container-low">
              <td className="px-4 py-3">
                <span className="inline-flex items-center gap-2">
                  <span className="text-on-surface">{u.name}</span>
                  {u.is_owner && (
                    <span
                      title="Dono da conta — protegido pela plataforma"
                      className="inline-flex items-center gap-1 rounded-full bg-warning/15 px-2 py-0.5 text-label-sm font-medium text-warning"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 13 }}>
                        shield
                      </span>
                      Owner
                    </span>
                  )}
                </span>
              </td>
              <td className="px-4 py-3 text-on-surface-variant">{u.email}</td>
              <td className="px-4 py-3">
                <span className={`inline-block px-2 py-0.5 rounded-full text-label-sm ${
                  u.role === "admin"
                    ? "bg-primary-container text-on-primary-container"
                    : "bg-secondary-container text-on-secondary-container"
                }`}>
                  {u.role === "admin" ? "Admin" : "Operador"}
                </span>
              </td>
              <td className="px-4 py-3 text-on-surface-variant">
                {u.profile_name ?? "—"}
              </td>
              <td className="px-4 py-3">
                <span className={u.is_active ? "text-on-surface" : "text-on-surface-variant"}>
                  {u.is_active ? "Ativo" : "Inativo"}
                </span>
              </td>
              <td className="px-4 py-3 text-on-surface-variant">
                {u.last_login_at
                  ? new Date(u.last_login_at).toLocaleString("pt-BR")
                  : "—"}
              </td>
              <td className="px-4 py-3">
                {canManage ? (
                  <div className="flex gap-1 justify-end">
                    <button
                      onClick={() => onEdit(u)}
                      disabled={u.is_owner}
                      title={u.is_owner ? "Protegido pela plataforma" : "Editar"}
                      className="p-1.5 rounded hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 18 }}>edit</span>
                    </button>
                    <button
                      onClick={() => onResetPassword(u)}
                      title="Resetar senha"
                      className="p-1.5 rounded hover:bg-surface-container"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 18 }}>lock_reset</span>
                    </button>
                    {u.id !== currentUserId && (
                      <button
                        onClick={() => onDelete(u)}
                        disabled={u.is_owner}
                        title={u.is_owner ? "Protegido pela plataforma" : "Excluir"}
                        className="p-1.5 rounded text-error hover:bg-error-container disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 18 }}>delete</span>
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="text-right text-on-surface-variant">—</div>
                )}
              </td>
            </tr>
          ))}
          {users.length === 0 && (
            <tr>
              <td colSpan={7} className="px-4 py-8 text-center text-on-surface-variant">
                Nenhum usuário encontrado.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
