// apps/web/src/features/profiles/components/ProfileCards.tsx
"use client";

import type { ProfileListItem } from "@/features/profiles/types";

interface Props {
  profiles: ProfileListItem[];
  onEdit: (p: ProfileListItem) => void;
  onDelete: (p: ProfileListItem) => void;
}

export function ProfileCards({ profiles, onEdit, onDelete }: Props) {
  if (profiles.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-outline-variant bg-surface-container-low py-16 text-center text-on-surface-variant">
        <span className="material-symbols-outlined" style={{ fontSize: 40 }}>
          badge
        </span>
        <p className="text-body-md">Nenhum perfil encontrado.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {profiles.map((p) => (
        <article
          key={p.id}
          className="group relative overflow-hidden rounded-2xl border border-outline-variant bg-white p-5 transition-all hover:border-primary/40 hover:shadow-sm dark:bg-surface-container"
        >
          {/* faixa superior colorida fininha — detalhe de identidade */}
          <span
            aria-hidden
            className="absolute inset-x-0 top-0 h-1 bg-primary-container"
          />

          {/* Topo: avatar/ícone + nome + badge sistema */}
          <header className="flex items-center gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-container text-on-primary-container">
              <span className="material-symbols-outlined" style={{ fontSize: 24 }}>
                {p.is_system ? "shield_person" : "badge"}
              </span>
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h3 className="truncate text-title-md font-semibold text-on-surface">{p.name}</h3>
                {p.is_system && (
                  <span className="inline-block shrink-0 rounded-full bg-surface-variant px-2 py-0.5 text-label-sm text-on-surface-variant">
                    Sistema
                  </span>
                )}
              </div>
            </div>
          </header>

          {/* Corpo: stats de permissões e usuários */}
          <div className="mt-5 flex items-center gap-6">
            <div className="flex items-center gap-2">
              <span
                className="material-symbols-outlined text-on-surface-variant"
                style={{ fontSize: 20 }}
              >
                key
              </span>
              <div className="leading-tight">
                <div className="text-title-sm font-semibold text-on-surface">{p.permission_count}</div>
                <div className="text-label-sm text-on-surface-variant">permissões</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span
                className="material-symbols-outlined text-on-surface-variant"
                style={{ fontSize: 20 }}
              >
                group
              </span>
              <div className="leading-tight">
                <div className="text-title-sm font-semibold text-on-surface">{p.user_count}</div>
                <div className="text-label-sm text-on-surface-variant">usuários</div>
              </div>
            </div>
          </div>

          {/* Rodapé: ações ou indicador de sistema */}
          <footer className="mt-5 flex items-center justify-end gap-1 border-t border-outline-variant pt-4">
            {p.is_system ? (
              <span className="flex items-center gap-1.5 text-label-md text-on-surface-variant">
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
                  lock
                </span>
                Perfil de sistema
              </span>
            ) : (
              <>
                <button
                  onClick={() => onEdit(p)}
                  title="Editar perfil"
                  aria-label={`Editar perfil ${p.name}`}
                  className="rounded-lg p-2 text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
                    edit
                  </span>
                </button>
                <button
                  onClick={() => onDelete(p)}
                  title="Excluir perfil"
                  aria-label={`Excluir perfil ${p.name}`}
                  className="rounded-lg p-2 text-on-surface-variant transition-colors hover:bg-error-container hover:text-error"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
                    delete
                  </span>
                </button>
              </>
            )}
          </footer>
        </article>
      ))}
    </div>
  );
}
