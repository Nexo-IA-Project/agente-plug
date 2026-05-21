"use client";

import { detectVariables } from "../validation";

interface Props {
  bodyText: string;
  examples: string[];
  onChange: (examples: string[]) => void;
}

export function VariablesEditor({ bodyText, examples, onChange }: Props) {
  const vars = Array.from(new Set(detectVariables(bodyText))).sort((a, b) => a - b);

  if (vars.length === 0) {
    return (
      <p className="text-xs text-on-surface-variant">
        Variáveis no formato {`{{1}}`}, {`{{2}}`} aparecerão aqui para você definir um exemplo.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-on-surface-variant">
        Exemplos das variáveis (obrigatório)
      </div>
      {vars.map((n, i) => (
        <div key={n} className="flex items-center gap-2">
          <span className="text-sm font-mono text-on-surface w-12">{`{{${n}}}`}</span>
          <input
            type="text"
            className="flex-1 px-3 py-2 rounded border border-outline-variant bg-surface-container text-sm"
            placeholder={`Exemplo para variável ${n}`}
            value={examples[i] || ""}
            onChange={(e) => {
              const next = [...examples];
              next[i] = e.target.value;
              onChange(next);
            }}
          />
        </div>
      ))}
    </div>
  );
}
