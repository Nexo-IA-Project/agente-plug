"use client";

import { useState } from "react";
import { useMetaTemplates } from "@/features/templates/hooks/useMetaTemplates";
import { TemplateList } from "@/features/templates/components/TemplateList";
import { TemplateModal } from "@/features/templates/components/TemplateModal";
import { TemplatePreviewModal } from "@/features/templates/components/TemplatePreviewModal";
import { SyncSummaryView } from "@/features/templates/components/SyncSummaryView";
import { useConfirm } from "@/shared/components/confirm/ConfirmProvider";
import { useToast } from "@/shared/hooks/useToast";
import { editMetaTemplate, syncMetaTemplates } from "@/lib/api";
import type { EditTemplateDto, MetaTemplate } from "@/features/templates/types";

interface FlowUsage {
  id: string;
  name: string;
  step_position: number;
}

export default function TemplatesPage() {
  const { templates, loading, error, reload, create, remove } = useMetaTemplates();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<MetaTemplate | null>(null);
  const [previewingTemplate, setPreviewingTemplate] = useState<MetaTemplate | null>(null);
  const [syncing, setSyncing] = useState(false);
  const confirm = useConfirm();
  const toast = useToast();

  async function handleEdit(id: string, dto: EditTemplateDto) {
    try {
      await editMetaTemplate(id, dto);
      toast.success("Template atualizado");
      setEditingTemplate(null);
      await reload();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("409")) {
        toast.error(
          "Não foi possível editar: template aprovado pela Meta é imutável.",
        );
      } else {
        toast.error(`Falha ao editar: ${msg}`);
      }
      throw err;
    }
  }

  async function handleSync() {
    setSyncing(true);
    try {
      const preview = await syncMetaTemplates({ dryRun: true });
      const noop =
        preview.templates_to_delete.length === 0 &&
        preview.templates_to_insert.length === 0 &&
        preview.steps_to_delete.length === 0;
      if (noop) {
        toast.info("Já está sincronizado — Meta e banco batem.");
        return;
      }
      const ok = await confirm({
        title: "Sincronizar templates com a Meta?",
        description: <SyncSummaryView summary={preview} />,
        confirmLabel: "Sincronizar e apagar",
        cancelLabel: "Cancelar",
        variant: preview.steps_to_delete.length > 0 ? "danger" : "warning",
      });
      if (!ok) return;
      const applied = await syncMetaTemplates({ dryRun: false });
      const parts: string[] = [];
      if (applied.templates_to_delete.length)
        parts.push(`${applied.templates_to_delete.length} apagado(s)`);
      if (applied.templates_to_insert.length)
        parts.push(`${applied.templates_to_insert.length} importado(s)`);
      if (applied.steps_to_delete.length)
        parts.push(`${applied.steps_to_delete.length} step(s) removido(s)`);
      toast.success(`Sincronização concluída: ${parts.join(" · ") || "sem mudanças"}.`);
      await reload();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Falha ao sincronizar: ${msg}`);
    } finally {
      setSyncing(false);
    }
  }

  async function handleDelete(template: MetaTemplate) {
    const ok = await confirm({
      title: "Excluir template",
      description: `Vamos excluir "${template.name}" da Meta, do storage e do banco. Esta ação não pode ser desfeita.`,
      confirmLabel: "Excluir",
      variant: "danger",
    });
    if (!ok) return;

    try {
      await remove(template.id);
      toast.success("Template excluído");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      try {
        const parsed = JSON.parse(msg);
        if (parsed?.detail?.code === "META_TEMPLATE_IN_USE") {
          const flows = (parsed.detail.flows as FlowUsage[]) ?? [];
          const list = flows
            .map((f) => `${f.name} (passo ${f.step_position})`)
            .join(", ");
          toast.error(
            `Não é possível excluir: template em uso por ${flows.length} flow${
              flows.length === 1 ? "" : "s"
            }: ${list}`,
          );
          return;
        }
      } catch {
        // not JSON
      }
      toast.error(`Falha ao excluir: ${msg}`);
    }
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-on-surface-variant">
        <span className="material-symbols-outlined animate-spin" style={{ fontSize: "20px" }}>
          progress_activity
        </span>
        <span className="text-sm">Carregando templates...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="rounded-xl border border-error/30 bg-error-container px-5 py-4 text-error">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div
      className="-mx-6 -my-6 flex flex-col bg-surface-container-lowest"
      style={{ height: "calc(100vh - 64px)" }}
    >
      <TemplateList
        templates={templates}
        onRefresh={reload}
        onSync={handleSync}
        syncing={syncing}
        onNew={() => setModalOpen(true)}
        onDelete={handleDelete}
        onEdit={(t) => setEditingTemplate(t)}
        onPreview={(t) => setPreviewingTemplate(t)}
      />

      <TemplateModal
        open={modalOpen || !!editingTemplate}
        onClose={() => {
          setModalOpen(false);
          setEditingTemplate(null);
        }}
        onCreate={async (dto) => {
          await create(dto);
          toast.success("Template enviado para aprovação da Meta");
          await reload();
        }}
        onEdit={handleEdit}
        template={editingTemplate ?? undefined}
      />

      <TemplatePreviewModal
        template={previewingTemplate}
        onClose={() => setPreviewingTemplate(null)}
      />
    </div>
  );
}
