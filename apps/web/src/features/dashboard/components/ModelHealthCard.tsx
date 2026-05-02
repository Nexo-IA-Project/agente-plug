// apps/web/src/features/dashboard/components/ModelHealthCard.tsx
import type { ModelHealth } from "../types";
import { cn } from "@/lib/utils";

function ProgressBar({ label, value, displayValue, color }: { label: string; value: number; displayValue: string; color: "primary" | "secondary" }) {
  return (
    <div>
      <div className="mb-1 flex justify-between">
        <span className="text-mono-label font-mono text-on-surface-variant">{label}</span>
        <span className="text-mono-label font-mono text-on-surface">{displayValue}</span>
      </div>
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-surface"
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className={color === "primary" ? "h-full rounded-full bg-primary" : "h-full rounded-full bg-secondary"}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

const statusConfig = {
  healthy: { color: "bg-green-500", label: "Operacional" },
  degraded: { color: "bg-yellow-500", label: "Degradado" },
  down: { color: "bg-red-500", label: "Offline" },
} as const;

export function ModelHealthCard({ health }: { health: ModelHealth }) {
  const latencyPct = Math.min((health.avgLatencyMs / 500) * 100, 100);
  const { color, label } = statusConfig[health.status];

  return (
    <div className="flex h-full flex-col rounded-xl border border-outline-variant bg-surface-container overflow-hidden">
      <div className="h-1 w-full bg-gradient-to-r from-primary to-secondary" />
      <div className="flex flex-1 flex-col p-card-padding">
        <div className="mb-3 flex items-start justify-between">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-outline-variant bg-primary-container">
            <span className="material-symbols-outlined text-primary" style={{ fontSize: "22px" }}>memory</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className={cn("h-2 w-2 rounded-full", color)} />
            <span className="text-body-sm text-on-surface-variant">{label}</span>
          </div>
        </div>
        <h3 className="text-h2 font-sans font-semibold text-on-surface">Saúde do Modelo</h3>
        <p className="mt-2 text-body-sm text-on-surface-variant">
          A latência do modelo principal está otimizada. Nenhuma anomalia detectada nas últimas 24 horas.
        </p>
        <div className="mt-auto space-y-4 pt-6">
          <ProgressBar label="Uso de CPU" value={health.cpuUsage} displayValue={`${health.cpuUsage}%`} color="primary" />
          <ProgressBar label="Latência Média" value={latencyPct} displayValue={`${health.avgLatencyMs}ms`} color="secondary" />
        </div>
      </div>
    </div>
  );
}
