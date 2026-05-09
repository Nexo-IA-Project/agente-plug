"use client";

import { useState } from "react";
import { useMetaTemplates } from "@/features/templates/hooks/useMetaTemplates";
import { TemplateList } from "@/features/templates/components/TemplateList";
import { TemplateModal } from "@/features/templates/components/TemplateModal";
import { useConfirm } from "@/shared/components/confirm/ConfirmProvider";
import { useToast } from "@/shared/hooks/useToast";
import type { MetaTemplate } from "@/features/templates/types";

interface FlowUsage {
  id: string;
  name: string;
  step_position: number;
}

// TODO: remover após validar visual — mocks só pra ver PENDING e REJECTED na UI.
const PREVIEW_MOCKS: MetaTemplate[] = [
  {
    id: "mock-pending-1",
    name: "promo_black_friday",
    category: "MARKETING",
    language: "pt_BR",
    status: "PENDING",
    components: [
      {
        type: "BODY",
        text: "Oi {{1}}, só hoje! Aproveite {{2}}% de desconto em todos os cursos. Use o cupom NEXOIA na finalização.",
      },
      {
        type: "BUTTONS",
        buttons: [
          { type: "URL", text: "Aproveitar agora" },
          { type: "QUICK_REPLY", text: "Não, obrigado" },
        ],
      },
    ],
    media_url: null,
    media_kind: null,
    rejection_reason: null,
    meta_template_id: "1234567890",
    created_at: new Date().toISOString(),
  },
  {
    id: "mock-rejected-1",
    name: "convite_bonus_v2",
    category: "UTILITY",
    language: "pt_BR",
    status: "REJECTED",
    components: [
      {
        type: "HEADER",
        format: "IMAGE",
        example: { header_handle: [] },
      },
      {
        type: "BODY",
        text: "Parabéns {{1}}! Você ganhou acesso ao bônus exclusivo. Clique abaixo pra resgatar.",
      },
    ],
    media_url: null,
    media_kind: "IMAGE",
    rejection_reason:
      "O conteúdo da mensagem se enquadra como Marketing, mas a categoria foi enviada como Utility. Recategorize e reenvie.",
    meta_template_id: "0987654321",
    created_at: new Date().toISOString(),
  },
];

export default function TemplatesPage() {
  const { templates, loading, error, reload, create, remove } = useMetaTemplates();
  const [modalOpen, setModalOpen] = useState(false);
  const confirm = useConfirm();
  const toast = useToast();

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
        templates={[...templates, ...PREVIEW_MOCKS]}
        onRefresh={reload}
        onNew={() => setModalOpen(true)}
        onDelete={handleDelete}
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
