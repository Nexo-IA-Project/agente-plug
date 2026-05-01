// apps/web/src/app/dashboard/page.tsx
import { MetricCard } from "@/components/dashboard/metric-card";
import { ConversationsChart } from "@/components/dashboard/conversations-chart";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// ── Mocked data ──────────────────────────────────────────────────────────────
// Replace with real API calls once analytics endpoints are available.

const METRICS = {
  totalConversations: 1_284,
  escalationRate: "8.3%",
  resolvedByAI: "91.7%",
  avgTurnsPerConversation: 4.2,
};

const TOP_SKILLS = [
  { name: "buscar_conhecimento", calls: 512, pct: "39.9%" },
  { name: "buscar_aluno_cademi", calls: 387, pct: "30.1%" },
  { name: "enviar_link_acesso", calls: 243, pct: "18.9%" },
  { name: "verificar_elegibilidade_reembolso", calls: 89, pct: "6.9%" },
  { name: "escalar_para_humano", calls: 53, pct: "4.1%" },
];

const CONVERSATIONS_BY_DAY = [
  { day: "Seg", conversations: 162 },
  { day: "Ter", conversations: 198 },
  { day: "Qua", conversations: 215 },
  { day: "Qui", conversations: 177 },
  { day: "Sex", conversations: 231 },
  { day: "Sáb", conversations: 143 },
  { day: "Dom", conversations: 158 },
];

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Visão geral do desempenho do agente de IA
        </p>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          title="Total de conversas"
          value={METRICS.totalConversations.toLocaleString("pt-BR")}
          description="Últimos 30 dias"
          trend="neutral"
        />
        <MetricCard
          title="Taxa de escalação"
          value={METRICS.escalationRate}
          description="Para agente humano"
          trend="down"
        />
        <MetricCard
          title="Resolvido pela IA"
          value={METRICS.resolvedByAI}
          description="Sem escalação"
          trend="up"
        />
        <MetricCard
          title="Turnos médios"
          value={METRICS.avgTurnsPerConversation}
          description="Por conversa"
          trend="neutral"
        />
      </div>

      {/* Chart + Top skills */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ConversationsChart data={CONVERSATIONS_BY_DAY} />
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Top 5 skills
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {TOP_SKILLS.map((skill) => (
                <li key={skill.name} className="flex items-center justify-between">
                  <span className="max-w-[160px] truncate text-sm" title={skill.name}>
                    {skill.name}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      {skill.calls}
                    </span>
                    <Badge variant="secondary">{skill.pct}</Badge>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
