"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createFollowupStep,
  deleteFollowupStep,
  listFollowupSteps,
  reorderFollowupSteps,
  updateFollowupStep,
} from "@/lib/api";
import type { CreateStepDto, FollowupStep, ReorderItem, UpdateStepDto } from "../types";

export function useFollowupSteps(flowId: string) {
  const [steps, setSteps] = useState<FollowupStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listFollowupSteps(flowId);
      setSteps(data.sort((a, b) => a.position - b.position));
    } catch {
      setError("Não foi possível carregar os steps.");
    } finally {
      setLoading(false);
    }
  }, [flowId]);

  useEffect(() => {
    load();
  }, [load]);

  const create = useCallback(
    async (dto: CreateStepDto): Promise<void> => {
      const step = await createFollowupStep(flowId, dto);
      setSteps((prev) => [...prev, step].sort((a, b) => a.position - b.position));
    },
    [flowId]
  );

  const update = useCallback(
    async (stepId: string, dto: UpdateStepDto): Promise<void> => {
      const updated = await updateFollowupStep(flowId, stepId, dto);
      setSteps((prev) =>
        prev
          .map((s) => (s.id === stepId ? updated : s))
          .sort((a, b) => a.position - b.position)
      );
    },
    [flowId]
  );

  const remove = useCallback(
    async (stepId: string): Promise<void> => {
      await deleteFollowupStep(flowId, stepId);
      setSteps((prev) => prev.filter((s) => s.id !== stepId));
    },
    [flowId]
  );

  const reorder = useCallback(
    async (items: ReorderItem[]): Promise<void> => {
      await reorderFollowupSteps(flowId, items);
      const posMap = new Map(items.map((i) => [i.id, i.position]));
      setSteps((prev) =>
        prev
          .map((s) => ({ ...s, position: posMap.get(s.id) ?? s.position }))
          .sort((a, b) => a.position - b.position)
      );
    },
    [flowId]
  );

  return { steps, loading, error, reload: load, create, update, remove, reorder };
}
