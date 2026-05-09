"use client";

import { useCallback, useEffect, useState } from "react";
import { createMetaTemplate, deleteMetaTemplate, listMetaTemplates } from "@/lib/api";
import type { CreateTemplateDto, MetaTemplate } from "../types";

export function useMetaTemplates() {
  const [templates, setTemplates] = useState<MetaTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listMetaTemplates();
      setTemplates(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("422") || msg.toLowerCase().includes("waba")) {
        setTemplates([]);
      } else {
        setError("Não foi possível carregar os templates. Tente novamente.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const create = useCallback(async (dto: CreateTemplateDto): Promise<MetaTemplate> => {
    const template = await createMetaTemplate(dto);
    setTemplates((prev) => [...prev, template]);
    return template;
  }, []);

  const remove = useCallback(async (id: string): Promise<void> => {
    await deleteMetaTemplate(id);
    setTemplates((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { templates, loading, error, reload: load, create, remove };
}
