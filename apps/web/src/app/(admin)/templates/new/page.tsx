"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { TemplateForm } from "@/features/templates/components/TemplateForm";
import { useMetaTemplates } from "@/features/templates/hooks/useMetaTemplates";
import { useToast } from "@/shared/hooks/useToast";
import { RequirePermission } from "@/features/auth/components/RequirePermission";

export default function NewTemplatePage() {
  const { create } = useMetaTemplates();
  const toast = useToast();
  const router = useRouter();

  return (
    <RequirePermission perm="templates.view">
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-6 flex items-center gap-3">
        <Link href="/templates" className="text-on-surface-variant hover:text-on-surface">
          <span className="material-symbols-outlined" style={{ fontSize: "22px" }}>arrow_back</span>
        </Link>
        <h1 className="text-2xl font-bold text-on-surface">Novo Template</h1>
      </div>
      <TemplateForm
        onCreate={async (dto) => {
          await create(dto);
          toast.success("Template enviado para aprovação da Meta");
          router.push("/templates");
        }}
      />
    </div>
    </RequirePermission>
  );
}
