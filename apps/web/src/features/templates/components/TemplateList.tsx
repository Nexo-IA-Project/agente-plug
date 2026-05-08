"use client";

import type { MetaTemplate } from "../types";
import { TemplateStatusBadge } from "./TemplateStatusBadge";

interface Props {
  templates: MetaTemplate[];
  onRefresh: () => void;
  onNew: () => void;
  onDelete: (template: MetaTemplate) => void;
}

function getCategoryIcon(category: string): string {
  if (category === "MARKETING") return "campaign";
  if (category === "UTILITY") return "build";
  return "receipt_long";
}

function getBodyPreview(template: MetaTemplate): string | null {
  const body = template.components.find((c) => c.type === "BODY");
  if (!body?.text) return null;
  return body.text.length > 140 ? body.text.slice(0, 140) + "…" : body.text;
}

export function TemplateList({ templates, onRefresh, onNew, onDelete }: Props) {
  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-outline-variant/40 px-8 py-5">
        <div>
          <h1 className="text-headline-sm font-bold text-on-surface">Templates WhatsApp</h1>
          <p className="mt-0.5 text-label-sm text-on-surface-variant">
            {templates.length === 0
              ? "Nenhum template cadastrado"
              : `${templates.length} template${templates.length !== 1 ? "s" : ""} sincronizado${templates.length !== 1 ? "s" : ""} com a Meta`}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onRefresh}
            className="flex items-center gap-2 rounded-xl border border-outline-variant px-4 py-2.5 text-label-md text-on-surface-variant transition-colors hover:bg-surface-container-high"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
              refresh
            </span>
            Atualizar
          </button>
          <button
            onClick={onNew}
            className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-label-md font-semibold text-on-primary transition-opacity hover:opacity-90"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
              add
            </span>
            Novo Template
          </button>
        </div>
      </div>

      {/* Lista */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {templates.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-container-high">
              <span
                className="material-symbols-outlined text-on-surface-variant"
                style={{ fontSize: "32px" }}
              >
                receipt_long
              </span>
            </div>
            <div>
              <p className="text-body-lg font-semibold text-on-surface">
                Nenhum template cadastrado
              </p>
              <p className="mt-1 text-body-sm text-on-surface-variant">
                Crie seu primeiro template para enviar via WhatsApp
              </p>
            </div>
            <button
              onClick={onNew}
              className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-label-md font-semibold text-on-primary hover:opacity-90"
            >
              <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
                add
              </span>
              Criar primeiro template
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {templates.map((t) => {
              const isApproved = t.status === "APPROVED";
              const isRejected = t.status === "REJECTED";
              const preview = getBodyPreview(t);

              return (
                <div
                  key={t.id}
                  className="group relative flex items-center gap-4 rounded-2xl border border-outline-variant/60 bg-surface-container-low px-5 py-4 transition-shadow hover:shadow-md"
                >
                  {/* Status bar lateral */}
                  <div
                    className={`absolute left-0 top-3 bottom-3 w-[3px] rounded-r-full ${
                      isApproved
                        ? "bg-success"
                        : isRejected
                          ? "bg-error"
                          : "bg-amber-400"
                    }`}
                  />

                  {/* Ícone categoria */}
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-container">
                    <span
                      className="material-symbols-outlined text-on-primary-container"
                      style={{ fontSize: "22px", fontVariationSettings: "'FILL' 1" }}
                    >
                      {getCategoryIcon(t.category)}
                    </span>
                  </div>

                  {/* Info */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-mono text-body-md font-semibold text-on-surface">
                        {t.name}
                      </span>
                      <TemplateStatusBadge status={t.status} />
                    </div>
                    <div className="mt-0.5 flex items-center gap-3 text-label-sm text-on-surface-variant">
                      <span className="flex items-center gap-1">
                        <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
                          label
                        </span>
                        {t.category}
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
                          translate
                        </span>
                        {t.language}
                      </span>
                    </div>
                    {preview && (
                      <p className="mt-1.5 truncate text-body-sm text-on-surface-variant/80">
                        {preview}
                      </p>
                    )}
                    {t.rejection_reason && (
                      <p className="mt-1.5 rounded-lg bg-error-container/40 px-2 py-1 text-xs text-error">
                        Motivo: {t.rejection_reason}
                      </p>
                    )}
                  </div>

                  {/* Ações */}
                  <button
                    onClick={() => onDelete(t)}
                    title="Excluir template"
                    className="ml-2 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-on-surface-variant opacity-0 transition-all hover:bg-error-container hover:text-error group-hover:opacity-100"
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>
                      delete
                    </span>
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
