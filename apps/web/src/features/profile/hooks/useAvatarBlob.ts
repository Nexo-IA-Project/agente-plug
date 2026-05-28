"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchMyAvatarBlob } from "@/lib/api";

/**
 * Busca o avatar via fetch autenticado (suporta cross-origin).
 * `enabled` controla o carregamento inicial.
 * `refreshAvatar` sempre busca, independente de `enabled` — usado após upload.
 */
export function useAvatarBlob(enabled: boolean) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const currentBlob = useRef<string | null>(null);

  // Sempre busca, sem checar enabled — usado pelo caller após upload
  const refreshAvatar = useCallback(async () => {
    setLoading(true);
    try {
      const url = await fetchMyAvatarBlob();
      if (currentBlob.current) URL.revokeObjectURL(currentBlob.current);
      currentBlob.current = url;
      setBlobUrl(url);
    } finally {
      setLoading(false);
    }
  }, []);

  // Carregamento inicial — só roda se já havia avatar salvo
  useEffect(() => {
    if (enabled) refreshAvatar();
    return () => {
      if (currentBlob.current) URL.revokeObjectURL(currentBlob.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { blobUrl, loading, refreshAvatar };
}
