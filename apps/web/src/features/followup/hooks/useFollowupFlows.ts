"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createFollowupFlow,
  deleteFollowupFlow,
  listFollowupFlows,
  reorderFollowupFlows,
  updateFollowupFlow,
} from "@/lib/api";
import type { CreateFlowDto, FollowupFlow, ReorderItem, UpdateFlowDto } from "../types";

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

  const reorder = useCallback(async (items: ReorderItem[]): Promise<void> => {
    await reorderFollowupFlows(items);
    const posMap = new Map(items.map((i) => [i.id, i.position]));
    setFlows((prev) =>
      prev
        .map((f) => ({ ...f, position: posMap.get(f.id) ?? f.position }))
        .sort((a, b) => a.position - b.position)
    );
  }, []);

  return { flows, loading, error, reload: load, create, update, remove, reorder };
}
