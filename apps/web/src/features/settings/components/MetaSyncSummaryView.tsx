import type { MetaSyncSummary } from "@/lib/api";

interface Props {
  summary: MetaSyncSummary;
}

export function MetaSyncSummaryView({ summary }: Props) {
  const { templates_to_delete, templates_to_insert, steps_to_delete } = summary;

  return (
    <div className="space-y-3">
      <p>
        As credenciais Meta mudaram. Para evitar inconsistência, vamos
        sincronizar o catálogo de templates com a WABA atual.
      </p>

      {templates_to_delete.length > 0 && (
        <section>
          <p className="font-semibold text-red-700 dark:text-red-400">
            {templates_to_delete.length} template(s) serão APAGADOS:
          </p>
          <ul className="mt-1 max-h-32 overflow-y-auto rounded-lg bg-surface-container-high/60 px-3 py-2 text-xs">
            {templates_to_delete.map((name) => (
              <li key={name} className="font-mono">
                {name}
              </li>
            ))}
          </ul>
        </section>
      )}

      {steps_to_delete.length > 0 && (
        <section>
          <p className="font-semibold text-amber-700 dark:text-amber-400">
            {steps_to_delete.length} step(s) de flow serão removidos em cascata:
          </p>
          <ul className="mt-1 max-h-32 overflow-y-auto rounded-lg bg-surface-container-high/60 px-3 py-2 text-xs">
            {steps_to_delete.map((s) => (
              <li key={s.step_id}>
                <span className="font-semibold">{s.flow_name}</span>
                <span className="text-on-surface-variant">
                  {" "}
                  · step #{s.position} ({s.template_name})
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {templates_to_insert.length > 0 && (
        <section>
          <p className="font-semibold text-emerald-700 dark:text-emerald-400">
            {templates_to_insert.length} template(s) serão importados:
          </p>
          <ul className="mt-1 max-h-32 overflow-y-auto rounded-lg bg-surface-container-high/60 px-3 py-2 text-xs">
            {templates_to_insert.map((name) => (
              <li key={name} className="font-mono">
                {name}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
