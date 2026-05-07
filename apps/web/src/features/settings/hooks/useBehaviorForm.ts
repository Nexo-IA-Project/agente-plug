"use client";

import { useState } from "react";
import { updateAccountSettings } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import type { AccountSettings, AccountSettingsPatch } from "@/features/settings/types";

export interface BehaviorFormState {
  values: Partial<AccountSettings>;
  saving: boolean;
  hasChanges: boolean;
  setValue: (key: keyof AccountSettings, value: number) => void;
  discard: () => void;
  save: () => Promise<void>;
}

export function useBehaviorForm(
  onSaved: (updated: AccountSettings) => void,
): BehaviorFormState {
  const toast = useToast();
  const [values, setValues] = useState<Partial<AccountSettings>>({});
  const [saving, setSaving] = useState(false);

  const hasChanges = Object.keys(values).length > 0;

  function setValue(key: keyof AccountSettings, value: number) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function discard() {
    setValues({});
  }

  async function save() {
    if (!hasChanges) return;
    setSaving(true);
    try {
      const updated = await updateAccountSettings(values as AccountSettingsPatch);
      onSaved(updated);
      discard();
      toast.success("Comportamento do agente salvo com sucesso.");
    } catch {
      toast.error("Erro ao salvar configurações.");
    } finally {
      setSaving(false);
    }
  }

  return { values, saving, hasChanges, setValue, discard, save };
}
