"use client";

import { useEffect, useState } from "react";
import { listMetaTemplates } from "@/lib/api";
import type { MetaTemplate } from "@/features/templates/types";

/**
 * Busca o template Meta pelo `name` e retorna os componentes completos
 * (incluindo media_url/media_kind). Cache simples em módulo entre chamadas
 * para evitar refetch quando vários StepItem usam mesmo template.
 */
const _cache: Record<string, MetaTemplate> = {};
let _allCachePromise: Promise<MetaTemplate[]> | null = null;

async function _fetchAll(): Promise<MetaTemplate[]> {
  if (_allCachePromise === null) {
    // Reset on failure to allow retry — sem isso, uma falha de rede transitória
    // travaria todos os StepItem em "sem mídia" até reload da página.
    _allCachePromise = listMetaTemplates().catch((err) => {
      _allCachePromise = null;
      throw err;
    });
  }
  return _allCachePromise;
}

export function useMetaTemplateDetail(name: string | null) {
  const [template, setTemplate] = useState<MetaTemplate | null>(
    name ? (_cache[name] ?? null) : null,
  );
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!name) {
      setTemplate(null);
      return;
    }
    if (_cache[name]) {
      setTemplate(_cache[name]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    _fetchAll()
      .then((all) => {
        if (cancelled) return;
        for (const t of all) _cache[t.name] = t;
        const found = _cache[name] ?? null;
        setTemplate(found);
      })
      .catch(() => {
        if (!cancelled) setTemplate(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [name]);

  return { template, loading };
}
