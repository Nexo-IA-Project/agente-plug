"use client";

import { useState } from "react";
import { useMetaTemplates } from "@/features/templates/hooks/useMetaTemplates";
import { TemplateList } from "@/features/templates/components/TemplateList";
import { TemplateModal } from "@/features/templates/components/TemplateModal";
import { useToast } from "@/shared/hooks/useToast";

export default function TemplatesPage() {
  const { templates, loading, error, reload, create } = useMetaTemplates();
  const [modalOpen, setModalOpen] = useState(false);
  const toast = useToast();

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
        onNew={() => setModalOpen(true)}
      />

      <TemplateModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreate={async (dto) => {
          await create(dto);
          toast.success("Template enviado para aprovação da Meta");
          await reload();
        }}
      />
    </div>
  );
}
