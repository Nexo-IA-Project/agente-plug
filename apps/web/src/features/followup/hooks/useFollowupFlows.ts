"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createFollowupFlow,
  deleteFollowupFlow,
  listFollowupFlows,
  updateFollowupFlow,
} from "@/lib/api";
import type { CreateFlowDto, FollowupFlow, UpdateFlowDto } from "../types";

export function useFollowupFlows() {
  const [flows, setFlows] = useState<FollowupFlow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listFollowupFlows();
      setFlows(data);
    } catch {
      setError("Não foi possível carregar os flows.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const create = useCallback(
    async (dto: CreateFlowDto): Promise<FollowupFlow> => {
      const flow = await createFollowupFlow(dto);
      setFlows((prev) => [...prev, flow]);
      return flow;
    },
    []
  );

  const update = useCallback(async (id: string, dto: UpdateFlowDto): Promise<void> => {
    const updated = await updateFollowupFlow(id, dto);
    setFlows((prev) => prev.map((f) => (f.id === id ? updated : f)));
  }, []);

  const remove = useCallback(async (id: string): Promise<void> => {
    await deleteFollowupFlow(id);
    setFlows((prev) => prev.filter((f) => f.id !== id));
  }, []);

  return { flows, loading, error, reload: load, create, update, remove };
}
