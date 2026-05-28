"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchMyAvatarBlob } from "@/lib/api";

/**
 * Busca o avatar via fetch autenticado (suporta cross-origin).
 * Retorna um blob URL e uma função para recarregar após upload.
 * Revoga automaticamente o blob URL anterior para evitar memory leak.
 */
export function useAvatarBlob(enabled: boolean) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const currentBlob = useRef<string | null>(null);

  const load = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    try {
      const url = await fetchMyAvatarBlob();
      if (currentBlob.current) URL.revokeObjectURL(currentBlob.current);
      currentBlob.current = url;
      setBlobUrl(url);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    load();
    return () => {
      if (currentBlob.current) URL.revokeObjectURL(currentBlob.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { blobUrl, loading, refreshAvatar: load };
}
