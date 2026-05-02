// apps/web/src/features/dashboard/data/dashboardMocks.ts
import type { KpiMetric, DayData, SkillMetric, ModelHealth } from "../types";

export const kpiData: KpiMetric[] = [
  {
    id: "total-conversations",
    title: "Total de Conversas",
    value: "12.405",
    icon: "chat_bubble",
    trend: { direction: "up", label: "+14% vs semana anterior" },
  },
  {
    id: "resolution-rate",
    title: "Taxa de Resolução IA",
    value: "86.2%",
    icon: "psychology_alt",
    trend: { direction: "up", label: "+2.1% vs semana anterior" },
  },
  {
    id: "escalation-rate",
    title: "Taxa de Escalação",
    value: "13.8%",
    icon: "support_agent",
    trend: { direction: "down", label: "-1.5% vs semana anterior", positiveIsDown: true },
  },
  {
    id: "avg-turns",
    title: "Média de Turnos",
    value: "3.4",
    icon: "forum",
    trend: { direction: "neutral", label: "Estável" },
  },
];

export const chartData: DayData[] = [
  { day: "Seg", count: 800 },
  { day: "Ter", count: 1200 },
  { day: "Qua", count: 1000 },
  { day: "Qui", count: 1700 },
  { day: "Sex", count: 1500 },
  { day: "Sáb", count: 600 },
  { day: "Dom", count: 1300 },
];

export const skillsData: SkillMetric[] = [
  { id: "1", name: "Consultar Fatura", icon: "receipt_long", count: 4205, pct: 33.9 },
  { id: "2", name: "Redefinir Senha", icon: "password", count: 2840, pct: 22.8 },
  { id: "3", name: "Cancelar Assinatura", icon: "cancel", count: 1520, pct: 12.2 },
  { id: "4", name: "Agendar Atendimento", icon: "schedule", count: 985, pct: 7.9 },
  { id: "5", name: "Dúvida sobre Produto", icon: "info", count: 740, pct: 5.9 },
];

export const modelHealthData: ModelHealth = {
  cpuUsage: 42,
  avgLatencyMs: 124,
  status: "healthy",
};
