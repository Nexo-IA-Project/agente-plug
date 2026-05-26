"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createOnboardingStep,
  deleteOnboardingStep,
  listOnboardingSteps,
  reorderOnboardingSteps,
  updateOnboardingStep,
} from "@/lib/api";
import type { CreateStepInput, OnboardingStep, ReorderItem, UpdateStepInput } from "../types";

export function useOnboardingSteps(flowId: string) {
  const [steps, setSteps] = useState<OnboardingStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!flowId) {
      setSteps([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await listOnboardingSteps(flowId);
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
    async (dto: CreateStepInput): Promise<void> => {
      const step = await createOnboardingStep(flowId, dto);
      setSteps((prev) => [...prev, step].sort((a, b) => a.position - b.position));
    },
    [flowId]
  );

  const update = useCallback(
    async (stepId: string, dto: UpdateStepInput): Promise<void> => {
      const updated = await updateOnboardingStep(flowId, stepId, dto);
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
      await deleteOnboardingStep(flowId, stepId);
      setSteps((prev) => prev.filter((s) => s.id !== stepId));
    },
    [flowId]
  );

  const reorder = useCallback(
    async (items: ReorderItem[]): Promise<void> => {
      const posMap = new Map(items.map((i) => [i.id, i.position]));
      let snapshot: OnboardingStep[] = [];
      setSteps((prev) => {
        snapshot = prev;
        return prev
          .map((s) => ({ ...s, position: posMap.get(s.id) ?? s.position }))
          .sort((a, b) => a.position - b.position);
      });
      try {
        await reorderOnboardingSteps(flowId, items);
      } catch (err) {
        setSteps(snapshot);
        throw err;
      }
    },
    [flowId]
  );

  return { steps, loading, error, reload: load, create, update, remove, reorder };
}
