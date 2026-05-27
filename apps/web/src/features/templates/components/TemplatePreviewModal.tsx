"use client";

import { useCallback, useEffect, useState } from "react";

import type { MetaTemplate } from "../types";
import { IPhonePreview } from "./IPhonePreview";

interface Props {
  template: MetaTemplate | null;
  onClose: () => void;
}

/**
 * Modal central com efeito scale-from-center (mesmo do TemplateModal de criação)
 * que mostra o template renderizado dentro de uma moldura iPhone com WhatsApp.
 */
export function TemplatePreviewModal({ template, onClose }: Props) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!template) {
      setVisible(false);
      return;
    }
    const raf = requestAnimationFrame(() => {
      requestAnimationFrame(() => setVisible(true));
    });
    return () => cancelAnimationFrame(raf);
  }, [template]);

  const handleClose = useCallback(() => {
    setVisible(false);
    setTimeout(onClose, 320);
  }, [onClose]);

  useEffect(() => {
    if (!template) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [template, handleClose]);

  if (!template) return null;

  const open = visible;

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
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-scrim/60"
        style={{
          opacity: open ? 1 : 0,
          transition: "opacity 500ms ease",
        }}
        onClick={handleClose}
      />

      {/* Modal */}
      <div
        className="relative z-50 flex flex-col bg-surface-container p-6"
        style={{
          width: "min(420px, calc(100% - 64px))",
          maxHeight: "92vh",
          borderRadius: "20px",
          boxShadow:
            "0 24px 80px rgba(0,0,0,0.5), 0 4px 16px rgba(0,0,0,0.3)",
          transformOrigin: "center center",
          transform: open ? "scale(1)" : "scale(0.78)",
          opacity: open ? 1 : 0,
          transition:
            "transform 600ms cubic-bezier(0.16, 1, 0.3, 1), opacity 480ms ease",
          overflow: "hidden",
        }}
      >
        <button
          type="button"
          onClick={handleClose}
          aria-label="Fechar"
          className="absolute right-3 top-3 rounded-lg p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container-high"
        >
          <span
            className="material-symbols-outlined"
            style={{ fontSize: "20px" }}
          >
            close
          </span>
        </button>

        <div className="mb-4 px-2 text-center">
          <h3 className="text-base font-semibold text-on-surface">
            {template.name}
          </h3>
          <p className="mt-0.5 font-mono text-[11px] text-on-surface-variant">
            {template.category} · {template.language}
          </p>
          <div className="mt-2 inline-flex">
            <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
              {template.status?.toLowerCase()}
            </span>
          </div>
        </div>

        <IPhonePreview template={template} />

        <div className="mt-5 flex justify-center">
          <button
            type="button"
            onClick={handleClose}
            className="rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-on-primary transition-colors hover:bg-primary/90"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
