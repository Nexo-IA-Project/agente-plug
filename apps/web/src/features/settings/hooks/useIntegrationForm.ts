"use client";

import { useState } from "react";
import { updateAccountSettings } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import type { AccountSettings, AccountSettingsPatch } from "@/features/settings/types";

export interface IntegrationFormState {
  editing: Set<keyof AccountSettings>;
  values: Partial<AccountSettings>;
  saving: boolean;
  hasChanges: boolean;
  startEdit: (key: keyof AccountSettings) => void;
  cancelEdit: (key: keyof AccountSettings) => void;
  setValue: (key: keyof AccountSettings, value: string | number) => void;
  discard: () => void;
  save: () => Promise<void>;
}

export function useIntegrationForm(
  onSaved: (updated: AccountSettings) => void,
): IntegrationFormState {
  const toast = useToast();
  const [editing, setEditing] = useState<Set<keyof AccountSettings>>(new Set());
  const [values, setValues] = useState<Partial<AccountSettings>>({});
  const [saving, setSaving] = useState(false);

  const hasChanges = Object.keys(values).length > 0;

  function startEdit(key: keyof AccountSettings) {
    setEditing((prev) => new Set([...prev, key]));
    setValues((prev) => ({ ...prev, [key]: "" }));
  }

  function cancelEdit(key: keyof AccountSettings) {
    setEditing((prev) => {
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
    setValues((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  function setValue(key: keyof AccountSettings, value: string | number) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function discard() {
    setEditing(new Set());
    setValues({});
  }

  async function save() {
    if (!hasChanges) return;
    setSaving(true);
    try {
      const updated = await updateAccountSettings(values as AccountSettingsPatch);
      onSaved(updated);
      discard();
      toast.success("Integrações salvas com sucesso.");
    } catch {
      toast.error("Erro ao salvar configurações.");
    } finally {
      setSaving(false);
    }
  }

  return { editing, values, saving, hasChanges, startEdit, cancelEdit, setValue, discard, save };
}
