"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { ConfirmDialog, type ConfirmOptions } from "./ConfirmDialog";

interface PendingConfirm extends ConfirmOptions {
  resolve: (value: boolean) => void;
}

interface ConfirmContextValue {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<PendingConfirm | null>(null);
  const [open, setOpen] = useState(false);

  const confirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise<boolean>((resolve) => {
      setPending({ ...options, resolve });
      // Double-RAF: garante que o primeiro paint seja com `open=false`
      // (estado inicial: scale pequeno + opacity 0). No próximo frame, abre — a transição
      // CSS detecta a mudança e dispara a animação suave.
      requestAnimationFrame(() => {
        requestAnimationFrame(() => setOpen(true));
      });
    });
  }, []);

  function handleConfirm() {
    if (!pending) return;
    pending.resolve(true);
    setOpen(false);
    // Aguarda a animação de saída antes de desmontar
    setTimeout(() => setPending(null), 320);
  }

  function handleCancel() {
    if (!pending) return;
    pending.resolve(false);
    setOpen(false);
    setTimeout(() => setPending(null), 320);
  }

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {pending && (
        <ConfirmDialog
          open={open}
          title={pending.title}
          description={pending.description}
          confirmLabel={pending.confirmLabel}
          cancelLabel={pending.cancelLabel}
          variant={pending.variant}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): ConfirmContextValue["confirm"] {
  const ctx = useContext(ConfirmContext);
  if (!ctx) {
    throw new Error("useConfirm precisa estar dentro de <ConfirmProvider>");
  }
  return ctx.confirm;
}
