import Link from "next/link";
import type { MetaTemplate } from "../types";
import { TemplateStatusBadge } from "./TemplateStatusBadge";

interface Props {
  templates: MetaTemplate[];
  onRefresh: () => void;
}

export function TemplateList({ templates, onRefresh }: Props) {
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-on-surface">Templates WhatsApp</h1>
        <div className="flex gap-3">
          <button
            onClick={onRefresh}
            className="flex items-center gap-2 rounded-lg border border-outline px-4 py-2 text-sm text-on-surface-variant hover:bg-surface-container-low"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>refresh</span>
            Atualizar
          </button>
          <Link
            href="/templates/new"
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:opacity-90"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>add</span>
            Novo Template
          </Link>
        </div>
      </div>

      {templates.length === 0 ? (
        <div className="rounded-xl border border-outline-variant bg-surface-container-low py-16 text-center text-on-surface-variant">
          Nenhum template encontrado. Crie o primeiro!
        </div>
      ) : (
        <div className="space-y-3">
          {templates.map((t) => (
            <div
              key={t.id}
              className="flex items-center justify-between rounded-xl border border-outline-variant bg-surface-container-low px-5 py-4"
            >
              <div>
                <p className="font-mono text-sm font-semibold text-on-surface">{t.name}</p>
                <p className="text-xs text-on-surface-variant">
                  {t.category} · {t.language}
                </p>
                {t.rejection_reason && (
                  <p className="mt-1 text-xs text-error">Motivo: {t.rejection_reason}</p>
                )}
              </div>
              <TemplateStatusBadge status={t.status} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
