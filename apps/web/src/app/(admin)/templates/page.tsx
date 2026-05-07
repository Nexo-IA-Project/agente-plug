"use client";

import { useMetaTemplates } from "@/features/templates/hooks/useMetaTemplates";
import { TemplateList } from "@/features/templates/components/TemplateList";

export default function TemplatesPage() {
  const { templates, loading, error, reload } = useMetaTemplates();

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-on-surface-variant">
        Carregando templates...
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
    <div className="mx-auto max-w-3xl p-6">
      <TemplateList templates={templates} onRefresh={reload} />
    </div>
  );
}
