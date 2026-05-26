"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createOnboardingFlow,
  deleteOnboardingFlow,
  listOnboardingFlows,
  updateOnboardingFlow,
} from "@/lib/api";
import type { CreateFlowInput, OnboardingFlow, UpdateFlowInput } from "../types";

export function useOnboardingFlows() {
  const [flows, setFlows] = useState<OnboardingFlow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listOnboardingFlows();
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
    async (dto: CreateFlowInput): Promise<OnboardingFlow> => {
      const flow = await createOnboardingFlow(dto);
      setFlows((prev) => [...prev, flow]);
      return flow;
    },
    []
  );

  const update = useCallback(async (id: string, dto: UpdateFlowInput): Promise<void> => {
    const updated = await updateOnboardingFlow(id, dto);
    setFlows((prev) => prev.map((f) => (f.id === id ? updated : f)));
  }, []);

  const remove = useCallback(async (id: string): Promise<void> => {
    await deleteOnboardingFlow(id);
    setFlows((prev) => prev.filter((f) => f.id !== id));
  }, []);

  return { flows, loading, error, reload: load, create, update, remove };
}
