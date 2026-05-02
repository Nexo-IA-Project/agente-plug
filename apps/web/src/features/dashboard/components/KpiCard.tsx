// apps/web/src/features/dashboard/components/KpiCard.tsx
import { cn } from "@/lib/utils";
import type { KpiMetric } from "../types";

function TrendBadge({ trend }: { trend: KpiMetric["trend"] }) {
  if (trend.direction === "neutral") {
    return (
      <div className="mt-1 flex items-center gap-1">
        <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: "14px" }}>
          horizontal_rule
        </span>
        <span className="text-mono-label font-mono text-on-surface-variant">{trend.label}</span>
      </div>
    );
  }

  const isGood =
    trend.positiveIsDown
      ? trend.direction === "down"
      : trend.direction === "up";

  const [trendValue, ...rest] = trend.label.split(" ");

  return (
    <div className="mt-1 flex items-center gap-1">
      <span
        className={cn("material-symbols-outlined", isGood ? "text-green-400" : "text-error")}
        style={{ fontSize: "14px" }}
      >
        {trend.direction === "up" ? "trending_up" : "trending_down"}
      </span>
      <span className={cn("text-mono-label font-mono", isGood ? "text-green-400" : "text-error")}>
        {trendValue}
      </span>
      <span className="ml-1 text-body-sm text-on-surface-variant">{rest.join(" ")}</span>
    </div>
  );
}

export function KpiCard({ metric }: { metric: KpiMetric }) {
  return (
    <div className="flex h-[140px] flex-col justify-between rounded-xl border border-outline-variant bg-surface-container p-card-padding">
      <div className="flex items-start justify-between">
        <span className="text-label-caps font-sans uppercase tracking-wider text-on-surface-variant">
          {metric.title}
        </span>
        <span className="material-symbols-outlined text-primary" style={{ fontSize: "22px" }}>
          {metric.icon}
        </span>
      </div>
      <div>
        <div className="text-h2 font-sans font-semibold text-on-surface">{metric.value}</div>
        <TrendBadge trend={metric.trend} />
      </div>
    </div>
  );
}
