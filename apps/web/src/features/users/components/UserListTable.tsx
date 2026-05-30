// apps/web/src/features/users/components/UserListTable.tsx
"use client";

import type { User } from "@/features/users/types";

interface Props {
  users: User[];
  onEdit: (u: User) => void;
  onResetPassword: (u: User) => void;
  onDelete: (u: User) => void;
  currentUserId: string;
}

export function UserListTable({ users, onEdit, onResetPassword, onDelete, currentUserId }: Props) {
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
              <td className="px-4 py-3">{u.name}</td>
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
                <div className="flex gap-1 justify-end">
                  <button
                    onClick={() => onEdit(u)}
                    title="Editar"
                    className="p-1.5 rounded hover:bg-surface-container"
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
                      title="Excluir"
                      className="p-1.5 rounded hover:bg-error-container text-error"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 18 }}>delete</span>
                    </button>
                  )}
                </div>
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
