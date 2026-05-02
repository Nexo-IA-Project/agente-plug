// apps/web/src/features/dashboard/components/SkillsTable.tsx
import type { SkillMetric } from "../types";

export function SkillsTable({ skills }: { skills: SkillMetric[] }) {
  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container p-card-padding">
      <div className="mb-6 flex items-center justify-between">
        <h3 className="text-h2 font-sans font-semibold text-on-surface">Top 5 Habilidades Acionadas</h3>
        <button className="text-mono-label font-mono text-primary hover:text-on-surface transition-colors">
          Ver Relatório Completo
        </button>
      </div>
      <table className="w-full border-collapse text-left">
        <thead>
          <tr>
            <th className="border-b border-outline-variant pb-3 pl-2 text-label-caps font-sans uppercase tracking-wider text-on-surface-variant">
              Nome da Habilidade
            </th>
            <th className="border-b border-outline-variant pb-3 text-right text-label-caps font-sans uppercase tracking-wider text-on-surface-variant">
              Contagem
            </th>
            <th className="border-b border-outline-variant pb-3 pr-2 text-right text-label-caps font-sans uppercase tracking-wider text-on-surface-variant">
              Porcentagem
            </th>
          </tr>
        </thead>
        <tbody>
          {skills.map((skill, idx) => {
            const isLast = idx === skills.length - 1;
            const border = isLast ? "" : "border-b border-outline-variant/50";
            return (
              <tr key={skill.id} className="group transition-colors hover:bg-surface-variant/30">
                <td className={`py-4 pl-2 text-body-sm text-on-surface ${border}`}>
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded bg-surface text-on-surface-variant group-hover:text-primary transition-colors">
                      <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>{skill.icon}</span>
                    </div>
                    <span className="font-medium">{skill.name}</span>
                  </div>
                </td>
                <td className={`py-4 text-right text-mono-label font-mono text-on-surface ${border}`}>
                  {skill.count.toLocaleString("pt-BR")}
                </td>
                <td className={`py-4 pr-2 text-right ${border}`}>
                  <div className="flex items-center justify-end gap-3">
                    <span className="text-mono-label font-mono text-on-surface">{skill.pct.toFixed(1)}%</span>
                    <div className="h-1 w-16 overflow-hidden rounded-full bg-surface">
                      <div className="h-full bg-primary" style={{ width: `${skill.pct}%` }} />
                    </div>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
