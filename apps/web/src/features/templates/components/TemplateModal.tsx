"use client";

import { TemplateForm } from "./TemplateForm";
import type { CreateTemplateDto, EditTemplateDto, MetaTemplate } from "../types";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreate?: (dto: CreateTemplateDto) => Promise<void>;
  onEdit?: (id: string, dto: EditTemplateDto) => Promise<void>;
  template?: MetaTemplate;
}

export function TemplateModal({ open, onClose, onCreate, onEdit, template }: Props) {
  const isEditing = !!template;
  const title = isEditing ? `Editar template — ${template!.name}` : "Novo Template";
  const subtitle = isEditing
    ? "Edite o template Meta (apenas templates não-aprovados)"
    : "Crie um template para envio via WhatsApp Business";

  return (
    <div
      className="fixed z-40"
      style={{
        left: "240px",
        right: 0,
        top: 0,
        bottom: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        pointerEvents: open ? "auto" : "none",
      }}
    >
      {/* Overlay — NÃO fecha ao clicar */}
      <div
        className="absolute inset-0 bg-scrim/60"
        style={{
          opacity: open ? 1 : 0,
          transition: "opacity 500ms ease",
        }}
      />

      {/* Modal — cresce do centro com mesmo efeito do FlowDrawer */}
      <div
        className="relative z-50 flex flex-col bg-surface-container"
        style={{
          width: "min(1100px, calc(100% - 64px))",
          maxHeight: "90vh",
          borderRadius: "20px",
          boxShadow: "0 24px 80px rgba(0,0,0,0.5), 0 4px 16px rgba(0,0,0,0.3)",
          transformOrigin: "center center",
          transform: open ? "scale(1)" : "scale(0.78)",
          opacity: open ? 1 : 0,
          transition: "transform 600ms cubic-bezier(0.16, 1, 0.3, 1), opacity 480ms ease",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-outline-variant/40 px-6 py-5">
          <div>
            <h2 className="text-title-md font-semibold text-on-surface">{title}</h2>
            <p className="mt-0.5 text-label-sm text-on-surface-variant">{subtitle}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container-high"
            aria-label="Fechar"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "22px" }}>
              close
            </span>
          </button>
        </div>

        {/* Body com scroll */}
        <div className="flex-1 overflow-y-auto" style={{ minHeight: 0 }}>
          <div className="p-6">
            <TemplateForm
              initialTemplate={template}
              onCreate={
                onCreate
                  ? async (dto) => {
                      await onCreate(dto);
                      onClose();
                    }
                  : undefined
              }
              onEdit={
                onEdit
                  ? async (id, dto) => {
                      await onEdit(id, dto);
                      onClose();
                    }
                  : undefined
              }
            />
          </div>
        </div>
      </div>
    </div>
  );
}
