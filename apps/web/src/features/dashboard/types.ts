// apps/web/src/features/dashboard/types.ts

export type TrendDirection = "up" | "down" | "neutral";

export interface KpiMetric {
  id: string;
  title: string;
  value: string;
  icon: string;
  trend: {
    direction: TrendDirection;
    label: string;
    positiveIsDown?: boolean;
  };
}

export interface DayData {
  day: string;
  count: number;
}

export interface SkillMetric {
  id: string;
  name: string;
  icon: string;
  count: number;
  pct: number;
}

export interface ModelHealth {
  cpuUsage: number;
  avgLatencyMs: number;
  status: "healthy" | "degraded" | "down";
}
