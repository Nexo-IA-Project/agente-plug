"use client";

import { updateAccountSettings, syncMetaTemplates, type MetaSyncSummary } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import { useConfirm } from "@/shared/components/confirm/ConfirmProvider";
import { MetaSyncSummaryView } from "@/features/settings/components/MetaSyncSummaryView";
import type { AccountSettings, AccountSettingsPatch } from "@/features/settings/types";

const META_FIELDS: ReadonlySet<keyof AccountSettings> = new Set([
  "meta_api_key",
  "meta_waba_id",
] as const);

function hasImpact(summary: MetaSyncSummary): boolean {
  return (
    summary.templates_to_delete.length > 0 ||
    summary.templates_to_insert.length > 0 ||
    summary.steps_to_delete.length > 0
  );
}

export function useFieldSave(onSaved: (updated: AccountSettings) => void) {
  const toast = useToast();
  const confirm = useConfirm();

  async function saveField(key: keyof AccountSettings, value: string | number): Promise<boolean> {
    try {
      const updated = await updateAccountSettings({ [key]: value } as AccountSettingsPatch);
      onSaved(updated);
      toast.success("Configuração salva.");

      if (META_FIELDS.has(key)) {
        await runMetaSyncFlow();
      }

      return true;
    } catch {
      toast.error("Erro ao salvar configuração.");
      return false;
    }
  }

  async function runMetaSyncFlow() {
    let preview: MetaSyncSummary;
    try {
      preview = await syncMetaTemplates({ dryRun: true });
    } catch {
      toast.error("Não foi possível buscar os templates da nova WABA.");
      return;
    }

    if (!hasImpact(preview)) {
      toast.info("Templates já sincronizados — nenhuma alteração necessária.");
      return;
    }

    const ok = await confirm({
      title: "Sincronizar templates da Meta?",
      description: <MetaSyncSummaryView summary={preview} />,
      confirmLabel: "Sincronizar e apagar",
      cancelLabel: "Cancelar",
      variant: preview.steps_to_delete.length > 0 ? "danger" : "warning",
    });

    if (!ok) return;

    try {
      const applied = await syncMetaTemplates({ dryRun: false });
      const parts: string[] = [];
      if (applied.templates_to_delete.length) {
        parts.push(`${applied.templates_to_delete.length} apagado(s)`);
      }
      if (applied.templates_to_insert.length) {
        parts.push(`${applied.templates_to_insert.length} importado(s)`);
      }
      if (applied.steps_to_delete.length) {
        parts.push(`${applied.steps_to_delete.length} step(s) removido(s)`);
      }
      toast.success(`Sincronização concluída: ${parts.join(" · ") || "sem mudanças"}.`);
    } catch {
      toast.error("Falha ao sincronizar templates.");
    }
  }

  return { saveField };
}
