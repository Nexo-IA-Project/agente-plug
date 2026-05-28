"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchMyAvatarBlob } from "@/lib/api";

/**
 * Busca o avatar via fetch autenticado (cross-origin safe).
 *
 * O efeito depende de `enabled` — quando `me` carrega e `has_avatar` muda
 * de false para true, o avatar é buscado automaticamente sem precisar
 * recarregar a página.
 */
export function useAvatarBlob(enabled: boolean) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const currentBlob = useRef<string | null>(null);

  const refreshAvatar = useCallback(async () => {
    const url = await fetchMyAvatarBlob();
    if (currentBlob.current) URL.revokeObjectURL(currentBlob.current);
    currentBlob.current = url;
    setBlobUrl(url);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    refreshAvatar();
    return () => {
      if (currentBlob.current) {
        URL.revokeObjectURL(currentBlob.current);
        currentBlob.current = null;
      }
    };
  }, [enabled, refreshAvatar]); // re-executa quando enabled muda false→true

  return { blobUrl, refreshAvatar };
}
