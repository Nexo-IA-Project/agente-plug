// apps/web/src/features/dashboard/components/ConversationsChart.tsx
"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import type { DayData } from "../types";

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-outline-variant bg-surface-container-high px-3 py-2 text-body-sm shadow-none">
      <p className="font-medium text-on-surface">{label}</p>
      <p className="text-primary">{payload[0].value.toLocaleString("pt-BR")} conversas</p>
    </div>
  );
}

export function ConversationsChart({ data }: { data: DayData[] }) {
  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container p-card-padding">
      <div className="mb-6 flex items-center justify-between">
        <h3 className="text-h2 font-sans font-semibold text-on-surface">Conversas por dia</h3>
        <button className="material-symbols-outlined text-on-surface-variant hover:text-on-surface transition-colors" style={{ fontSize: "20px" }}>
          more_horiz
        </button>
      </div>
      <div className="h-[300px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barCategoryGap="40%">
            <CartesianGrid vertical={false} stroke="var(--color-outline-variant)" strokeDasharray="3 3" />
            <XAxis
              dataKey="day"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "var(--color-on-surface-variant)", fontSize: 13, fontFamily: "var(--font-mono)" }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: "var(--color-on-surface-variant)", fontSize: 13, fontFamily: "var(--font-mono)" }}
              tickFormatter={(v: number) => (v >= 1000 ? `${v / 1000}k` : String(v))}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--color-surface-container-high)" }} />
            <Bar dataKey="count" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
