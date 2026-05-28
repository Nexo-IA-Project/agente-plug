"use client";

import { useEffect } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "sm" | "md" | "lg";
}

const SIZE: Record<NonNullable<Props["size"]>, string> = {
  sm: "max-w-md",
  md: "max-w-2xl",
  lg: "max-w-4xl",
};

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  size = "md",
}: Props) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  return (
    <>
      <div
        onClick={onClose}
        className={`fixed inset-0 z-[60] cursor-pointer bg-black/40 transition-opacity duration-200 ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`pointer-events-none fixed inset-0 z-[70] flex items-center justify-center p-4 transition-all duration-200 ${
          open ? "opacity-100" : "opacity-0"
        }`}
      >
        <div
          onClick={(e) => e.stopPropagation()}
          className={`pointer-events-auto w-full ${SIZE[size]} rounded-2xl border border-outline-variant bg-surface-container shadow-2xl transition-transform duration-200 ${
            open ? "scale-100" : "scale-95"
          }`}
        >
          <header className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
            <h2 className="text-lg font-semibold text-on-surface">{title}</h2>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md p-2 text-on-surface-variant hover:bg-surface-container-high"
              aria-label="Fechar"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </header>
          <div className="px-6 py-5">{children}</div>
          {footer && (
            <footer className="border-t border-outline-variant px-6 py-4">
              {footer}
            </footer>
          )}
        </div>
      </div>
    </>
  );
}
