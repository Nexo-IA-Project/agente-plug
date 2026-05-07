"use client";

import { useCallback, useEffect, useState } from "react";
import { createMetaTemplate, listMetaTemplates } from "@/lib/api";
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
    } catch {
      setError("Não foi possível carregar os templates. Verifique META_WABA_ID nas configurações.");
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

  return { templates, loading, error, reload: load, create };
}
