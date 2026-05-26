"use client";

import { useState } from "react";
import { updateAccountSettings } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import type { AccountSettings, AccountSettingsPatch } from "@/features/settings/types";

export function useFieldSave(onSaved: (updated: AccountSettings) => void) {
  const toast = useToast();

  async function saveField(key: keyof AccountSettings, value: string | number): Promise<boolean> {
    try {
      const updated = await updateAccountSettings({ [key]: value } as AccountSettingsPatch);
      onSaved(updated);
      toast.success("Configuração salva.");
      return true;
    } catch {
      toast.error("Erro ao salvar configuração.");
      return false;
    }
  }

  return { saveField };
}
