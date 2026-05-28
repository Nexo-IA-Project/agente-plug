"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { fetchMyAvatarBlob } from "@/lib/api";
import { useAuth } from "@/features/auth/hooks/useAuth";

interface AvatarContextValue {
  blobUrl: string | null;
  refreshAvatar: () => Promise<void>;
}

const Ctx = createContext<AvatarContextValue>({ blobUrl: null, refreshAvatar: async () => {} });

export function AvatarProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const currentBlob = useRef<string | null>(null);

  const refreshAvatar = useCallback(async () => {
    const url = await fetchMyAvatarBlob();
    if (currentBlob.current) URL.revokeObjectURL(currentBlob.current);
    currentBlob.current = url;
    setBlobUrl(url);
  }, []);

  useEffect(() => {
    if (!user) return;
    refreshAvatar();
    return () => {
      if (currentBlob.current) URL.revokeObjectURL(currentBlob.current);
    };
  }, [user, refreshAvatar]);

  return <Ctx.Provider value={{ blobUrl, refreshAvatar }}>{children}</Ctx.Provider>;
}

export function useAvatar() {
  return useContext(Ctx);
}
