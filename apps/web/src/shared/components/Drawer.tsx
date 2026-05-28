// apps/web/src/shared/components/Drawer.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

const SIDEBAR_WIDTH = "var(--sidebar-width, 240px)";

export function Drawer({ open, onClose, title, children, footer }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  useEffect(() => {
    if (open) panelRef.current?.focus();
  }, [open]);

  if (!mounted) return null;

  const overlay = (
    <>
      {/* Backdrop */}
      <div
        aria-hidden
        onClick={onClose}
        className={`fixed inset-0 z-[60] cursor-pointer bg-black/40 transition-opacity duration-200 ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />

      {/* Painel */}
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={`fixed right-0 z-[70] flex flex-col bg-surface-container shadow-2xl transition-transform duration-300 ease-out ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
        style={{ top: 0, bottom: 0, left: SIDEBAR_WIDTH }}
      >
        <header className="flex items-center gap-3 border-b border-outline-variant px-4 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-2 text-on-surface-variant hover:bg-surface-container-high"
            aria-label="Fechar"
          >
            <span className="material-symbols-outlined">arrow_forward</span>
          </button>
          <h2 className="text-lg font-semibold text-on-surface">{title}</h2>
        </header>

        <div className="flex-1 overflow-auto px-6 py-6">{children}</div>

        {footer && (
          <footer className="border-t border-outline-variant px-6 py-4">
            {footer}
          </footer>
        )}
      </aside>
    </>
  );

  return createPortal(overlay, document.body);
}
