"use client";

import type React from "react";
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

function highlightVars(text: string): React.ReactNode {
  const parts = text.split(/(\{\{\d+\}\})/g);
  return parts.map((p, i) =>
    /^\{\{\d+\}\}$/.test(p) ? (
      <span
        key={i}
        className="mx-[1px] inline-flex items-center rounded-md bg-primary/10 px-1.5 py-px font-mono text-[0.78em] font-medium text-primary"
      >
        {p}
      </span>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}

function getBodyComponent(template: MetaTemplate) {
  return template.components.find((c) => c.type === "BODY");
}

function countVars(text: string | undefined): number {
  if (!text) return 0;
  const matches = text.match(/\{\{\d+\}\}/g) ?? [];
  return new Set(matches).size;
}

function getMediaInfo(
  template: MetaTemplate,
): { icon: string; label: string } | null {
  const header = template.components.find((c) => c.type === "HEADER");
  if (!header || header.format === "TEXT" || !header.format) return null;
  if (header.format === "IMAGE") return { icon: "image", label: "Imagem" };
  if (header.format === "VIDEO") return { icon: "videocam", label: "Vídeo" };
  if (header.format === "DOCUMENT") return { icon: "description", label: "Doc" };
  return null;
}

function buttonsCount(template: MetaTemplate): number {
  const btns = template.components.find((c) => c.type === "BUTTONS");
  return btns?.buttons?.length ?? 0;
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
              const status = (t.status ?? "").toString().toUpperCase();
              const isApproved = status === "APPROVED";
              const isRejected = status === "REJECTED";
              const isPending = status === "PENDING";

              const body = getBodyComponent(t);
              const preview = body?.text ?? null;
              const previewTruncated =
                preview && preview.length > 220 ? preview.slice(0, 220) + "…" : preview;
              const varsCount = countVars(body?.text);
              const media = getMediaInfo(t);
              const btnCount = buttonsCount(t);

              const railClass = isApproved
                ? "bg-success"
                : isRejected
                  ? "bg-error"
                  : "bg-warning";

              const statusIcon = isApproved
                ? { name: "verified", color: "text-success" }
                : isRejected
                  ? { name: "do_not_disturb_on", color: "text-error" }
                  : { name: "pending", color: "text-warning" };

              const cardClass = [
                "group relative flex items-center gap-5 overflow-hidden rounded-2xl border bg-surface-container-low pl-6 pr-4 py-4 transition-all duration-200",
                isApproved
                  ? "border-success/40 hover:border-success/60 hover:shadow-[0_4px_24px_-8px_rgba(34,197,94,0.25)]"
                  : isRejected
                    ? "border-error/40 hover:border-error/60 hover:shadow-[0_4px_24px_-8px_rgba(220,38,38,0.25)]"
                    : "border-warning/40 hover:border-warning/60 hover:shadow-[0_4px_24px_-8px_rgba(245,158,11,0.25)]",
              ].join(" ");

              return (
                <article key={t.id} className={cardClass}>
                  {/* Background tint — mesma intensidade entre os 3 status */}
                  {isApproved && (
                    <div
                      aria-hidden
                      className="pointer-events-none absolute inset-0 bg-gradient-to-r from-success/15 via-success/5 to-transparent"
                    />
                  )}
                  {isRejected && (
                    <div
                      aria-hidden
                      className="pointer-events-none absolute inset-0 bg-gradient-to-r from-error/15 via-error/5 to-transparent"
                    />
                  )}
                  {isPending && (
                    <div
                      aria-hidden
                      className="pointer-events-none absolute inset-0 bg-gradient-to-r from-warning/15 via-warning/5 to-transparent"
                    />
                  )}

                  {/* Rail vertical */}
                  <div
                    aria-hidden
                    className={`absolute left-0 top-0 bottom-0 w-[3px] ${railClass}`}
                  />

                  {/* Ícone de categoria */}
                  <div
                    className={[
                      "relative flex h-12 w-12 shrink-0 items-center justify-center rounded-xl transition-colors",
                      isApproved
                        ? "bg-success/10 text-success"
                        : isRejected
                          ? "bg-error/10 text-error"
                          : "bg-warning/10 text-warning",
                    ].join(" ")}
                  >
                    <span
                      className="material-symbols-outlined"
                      style={{ fontSize: "22px", fontVariationSettings: "'FILL' 1" }}
                    >
                      {getCategoryIcon(t.category)}
                    </span>
                  </div>

                  {/* Conteúdo */}
                  <div className="relative min-w-0 flex-1">
                    {/* Linha 1: nome + status */}
                    <div className="flex items-center gap-3">
                      <h3 className="truncate font-mono text-[15px] font-semibold tracking-tight text-on-surface">
                        {t.name}
                      </h3>
                      <TemplateStatusBadge status={t.status} />
                      <span
                        aria-hidden
                        className={`material-symbols-outlined ${statusIcon.color}`}
                        style={{ fontSize: "18px", fontVariationSettings: "'FILL' 1" }}
                        title={
                          isApproved
                            ? "Aprovado pela Meta"
                            : isRejected
                              ? "Rejeitado pela Meta"
                              : "Em análise pela Meta"
                        }
                      >
                        {statusIcon.name}
                      </span>
                    </div>

                    {/* Linha 2: metadata inline */}
                    <div className="mt-1 flex flex-wrap items-center gap-x-1.5 text-xs text-on-surface-variant">
                      <span className="font-medium uppercase tracking-wider">
                        {t.category}
                      </span>
                      <span aria-hidden className="text-outline">
                        ·
                      </span>
                      <span className="font-mono">{t.language}</span>

                      {varsCount > 0 && (
                        <>
                          <span aria-hidden className="text-outline">
                            ·
                          </span>
                          <span>
                            {varsCount} variáve{varsCount > 1 ? "is" : "l"}
                          </span>
                        </>
                      )}

                      {media && (
                        <>
                          <span aria-hidden className="text-outline">
                            ·
                          </span>
                          <span className="inline-flex items-center gap-0.5">
                            <span
                              className="material-symbols-outlined"
                              style={{ fontSize: "13px" }}
                            >
                              {media.icon}
                            </span>
                            {media.label}
                          </span>
                        </>
                      )}

                      {btnCount > 0 && (
                        <>
                          <span aria-hidden className="text-outline">
                            ·
                          </span>
                          <span className="inline-flex items-center gap-0.5">
                            <span
                              className="material-symbols-outlined"
                              style={{ fontSize: "13px" }}
                            >
                              smart_button
                            </span>
                            {btnCount}
                          </span>
                        </>
                      )}
                    </div>

                    {/* Preview do body com variáveis chip */}
                    {previewTruncated && (
                      <p className="mt-2.5 text-sm leading-relaxed text-on-surface-variant/80">
                        {highlightVars(previewTruncated)}
                      </p>
                    )}

                    {/* Motivo de rejeição inline */}
                    {isRejected && t.rejection_reason && (
                      <div className="mt-2.5 flex items-start gap-2 rounded-lg border border-error/20 bg-error/5 px-3 py-2 text-xs text-error">
                        <span
                          className="material-symbols-outlined mt-px shrink-0"
                          style={{ fontSize: "15px" }}
                        >
                          info
                        </span>
                        <span className="leading-relaxed">{t.rejection_reason}</span>
                      </div>
                    )}
                  </div>

                  {/* Ações */}
                  <div className="relative flex shrink-0 items-center self-center">
                    <button
                      onClick={() => onDelete(t)}
                      title="Excluir template"
                      aria-label={`Excluir template ${t.name}`}
                      className="flex h-10 w-10 items-center justify-center rounded-xl text-on-surface-variant transition-colors hover:bg-error/10 hover:text-error focus-visible:bg-error/10 focus-visible:text-error"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>
                        delete
                      </span>
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
