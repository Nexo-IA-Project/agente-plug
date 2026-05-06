// apps/web/src/app/dashboard/page.tsx
import { KpiCard } from "@/features/dashboard/components/KpiCard";
import { ConversationsChart } from "@/features/dashboard/components/ConversationsChart";
import { ModelHealthCard } from "@/features/dashboard/components/ModelHealthCard";
import { SkillsTable } from "@/features/dashboard/components/SkillsTable";
import { kpiData, chartData, skillsData, modelHealthData } from "@/features/dashboard/data/dashboardMocks";

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-h1 font-sans font-bold text-on-background">Visão Geral</h1>
          <p className="mt-1 text-body-base text-on-surface-variant">
            Métricas de performance dos seus agentes IA hoje.
          </p>
        </div>
        <button className="flex items-center gap-2 rounded-lg border border-outline-variant px-4 py-2 text-mono-label font-mono text-on-surface hover:bg-surface-container-high transition-colors">
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>calendar_today</span>
          Últimos 7 dias
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
        {kpiData.map((metric) => <KpiCard key={metric.id} metric={metric} />)}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <ConversationsChart data={chartData} />
        </div>
        <div className="lg:col-span-4">
          <ModelHealthCard health={modelHealthData} />
        </div>
      </div>

      <SkillsTable skills={skillsData} />
    </div>
  );
}
