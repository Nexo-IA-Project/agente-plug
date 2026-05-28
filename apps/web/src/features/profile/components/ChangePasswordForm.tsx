"use client";

import { useState } from "react";
import { changeMyPassword } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";

interface Props {
  onSuccess?: () => void;
}

export function ChangePasswordForm({ onSuccess }: Props) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const toast = useToast();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (next.length < 8) {
      toast.error("Nova senha deve ter no mínimo 8 caracteres");
      return;
    }
    if (next !== confirm) {
      toast.error("As senhas não conferem");
      return;
    }
    setSubmitting(true);
    try {
      await changeMyPassword(current, next);
      toast.success("Senha alterada");
      setCurrent("");
      setNext("");
      setConfirm("");
      onSuccess?.();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erro ao alterar senha";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 max-w-md">
      <label className="flex flex-col gap-1">
        <span className="text-body-sm text-on-surface-variant">Senha atual</span>
        <input
          type="password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
          className="px-3 py-2 rounded border border-outline-variant bg-surface"
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-body-sm text-on-surface-variant">Nova senha (mín. 8 caracteres)</span>
        <input
          type="password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          required
          minLength={8}
          className="px-3 py-2 rounded border border-outline-variant bg-surface"
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-body-sm text-on-surface-variant">Confirmar nova senha</span>
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          minLength={8}
          className="px-3 py-2 rounded border border-outline-variant bg-surface"
        />
      </label>
      <button
        type="submit"
        disabled={submitting}
        className="self-start px-4 py-2 rounded bg-primary text-on-primary disabled:opacity-50"
      >
        {submitting ? "Salvando..." : "Alterar senha"}
      </button>
    </form>
  );
}
