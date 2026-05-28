// apps/web/src/features/users/components/ResetPasswordDialog.tsx
"use client";

import { Modal } from "@/shared/components/Modal";
import type { User } from "@/features/users/types";

interface Props {
  open: boolean;
  user: User | null;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}

export function ResetPasswordDialog({ open, user, onClose, onConfirm }: Props) {
  if (!user) return null;
  return (
    <Modal open={open} onClose={onClose} title="Resetar senha">
      <div className="flex flex-col gap-4 p-2">
        <p className="text-body-md">
          Uma nova senha temporária será gerada para{" "}
          <strong>{user.name}</strong> ({user.email}) e enviada por email. A
          senha atual deixará de funcionar imediatamente.
        </p>
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-2 rounded bg-surface-container">
            Cancelar
          </button>
          <button
            onClick={onConfirm}
            className="px-3 py-2 rounded bg-primary text-on-primary"
          >
            Resetar e enviar email
          </button>
        </div>
      </div>
    </Modal>
  );
}
