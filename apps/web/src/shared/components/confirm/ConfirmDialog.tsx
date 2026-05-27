"use client";

import { useEffect, type ReactNode } from "react";

export type ConfirmVariant = "danger" | "warning" | "info";

export interface ConfirmOptions {
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: ConfirmVariant;
}

interface Props extends ConfirmOptions {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const VARIANT_STYLES: Record<
  ConfirmVariant,
  { icon: string; iconBg: string; iconColor: string; confirmBtn: string }
> = {
  danger: {
    icon: "delete_forever",
    iconBg: "bg-red-100",
    iconColor: "text-red-700",
    confirmBtn:
      "bg-red-600 hover:bg-red-700 text-white shadow-[0_4px_14px_rgba(220,38,38,0.4)]",
  },
  warning: {
    icon: "warning",
    iconBg: "bg-amber-100",
    iconColor: "text-amber-700",
    confirmBtn:
      "bg-amber-500 hover:bg-amber-600 text-white shadow-[0_4px_14px_rgba(245,158,11,0.4)]",
  },
  info: {
    icon: "help",
    iconBg: "bg-blue-100",
    iconColor: "text-blue-700",
    confirmBtn:
      "bg-primary hover:opacity-90 text-on-primary shadow-[0_4px_14px_rgba(0,0,0,0.25)]",
  },
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  variant = "info",
  onConfirm,
  onCancel,
}: Props) {
  const styles = VARIANT_STYLES[variant];

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
      if (e.key === "Enter") onConfirm();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onCancel, onConfirm]);

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center"
      style={{ pointerEvents: open ? "auto" : "none" }}
    >
      {/* Overlay com fade */}
      <div
        onClick={onCancel}
        className="absolute inset-0 backdrop-blur-sm"
        style={{
          backgroundColor: "rgba(0, 0, 0, 0.55)",
          opacity: open ? 1 : 0,
          transition: "opacity 320ms ease",
        }}
      />

      {/* Dialog — fade in + scale + slide vindo de baixo */}
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="relative z-10 w-[420px] max-w-[calc(100%-32px)] overflow-hidden rounded-2xl bg-surface-container"
        style={{
          boxShadow: "0 32px 80px rgba(0,0,0,0.6), 0 8px 24px rgba(0,0,0,0.35)",
          transformOrigin: "center center",
          transform: open ? "scale(1) translateY(0)" : "scale(0.85) translateY(24px)",
          opacity: open ? 1 : 0,
          filter: open ? "blur(0)" : "blur(4px)",
          transition:
            "transform 460ms cubic-bezier(0.34, 1.56, 0.64, 1)," +
            " opacity 320ms ease," +
            " filter 320ms ease",
        }}
      >
        <div className="px-6 pt-6 pb-2">
          <div className="flex items-start gap-4">
            <div
              className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ${styles.iconBg}`}
              style={{
                transform: open ? "scale(1) rotate(0deg)" : "scale(0.5) rotate(-20deg)",
                opacity: open ? 1 : 0,
                transition:
                  "transform 540ms cubic-bezier(0.34, 1.56, 0.64, 1) 80ms," +
                  " opacity 320ms ease 80ms",
              }}
            >
              <span
                className={`material-symbols-outlined ${styles.iconColor}`}
                style={{ fontSize: "26px", fontVariationSettings: "'FILL' 1" }}
              >
                {styles.icon}
              </span>
            </div>
            <div
              className="flex-1 pt-0.5"
              style={{
                opacity: open ? 1 : 0,
                transform: open ? "translateY(0)" : "translateY(8px)",
                transition: "opacity 320ms ease 140ms, transform 320ms ease 140ms",
              }}
            >
              <h3
                id="confirm-title"
                className="text-title-md font-semibold text-on-surface"
              >
                {title}
              </h3>
              {description && (
                <div className="mt-1.5 text-body-sm leading-relaxed text-on-surface-variant">
                  {description}
                </div>
              )}
            </div>
          </div>
        </div>

        <div
          className="flex items-center justify-end gap-2 px-6 pb-5 pt-5"
          style={{
            opacity: open ? 1 : 0,
            transform: open ? "translateY(0)" : "translateY(8px)",
            transition: "opacity 320ms ease 200ms, transform 320ms ease 200ms",
          }}
        >
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl px-4 py-2.5 text-label-sm font-medium text-on-surface-variant transition-colors hover:bg-surface-container-high"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            autoFocus
            className={`rounded-xl px-5 py-2.5 text-label-sm font-semibold transition-all ${styles.confirmBtn}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
