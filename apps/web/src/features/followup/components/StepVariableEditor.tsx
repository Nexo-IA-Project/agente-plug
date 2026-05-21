"use client";

import { StepVariableBinding, StepVariableSource } from "../types";

interface Props {
  templateBody: string | null;
  bindings: Record<string, StepVariableBinding>;
  onChange: (bindings: Record<string, StepVariableBinding>) => void;
}

const SOURCE_OPTIONS: Array<{ value: StepVariableSource; label: string }> = [
  { value: "customer_name", label: "Nome do aluno" },
  { value: "product_name", label: "Nome do curso" },
  { value: "contact_phone", label: "Telefone do aluno" },
  { value: "contact_email", label: "Email do aluno" },
  { value: "static", label: "Texto fixo..." },
];

function detectVariables(body: string | null): string[] {
  if (!body) return [];
  const matches = body.matchAll(/\{\{(\d+)\}\}/g);
  const set = new Set<string>();
  for (const m of matches) set.add(m[1]);
  return Array.from(set).sort((a, b) => Number(a) - Number(b));
}

export function StepVariableEditor({ templateBody, bindings, onChange }: Props) {
  const vars = detectVariables(templateBody);

  if (vars.length === 0) {
    return (
      <p className="text-xs text-on-surface-variant">
        Este template não tem variáveis dinâmicas.
      </p>
    );
  }

  const updateBinding = (key: string, patch: Partial<StepVariableBinding>) => {
    const current = bindings[key] ?? { source: "customer_name" };
    const next: StepVariableBinding = { ...current, ...patch };
    if (next.source !== "static") delete next.value;
    onChange({ ...bindings, [key]: next });
  };

  return (
    <div className="flex flex-col gap-3">
      {vars.map((key) => {
        const binding = bindings[key] ?? { source: "customer_name" as StepVariableSource };
        return (
          <div key={key} className="grid grid-cols-[80px_1fr] items-start gap-3">
            <label className="pt-2 text-sm font-medium text-on-surface">{`{{${key}}}`}</label>
            <div className="flex flex-col gap-2">
              <select
                value={binding.source}
                onChange={(e) => updateBinding(key, { source: e.target.value as StepVariableSource })}
                className="rounded-md border border-outline-variant bg-surface px-3 py-2 text-sm text-on-surface"
              >
                {SOURCE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              {binding.source === "static" && (
                <input
                  type="text"
                  value={binding.value ?? ""}
                  onChange={(e) => updateBinding(key, { value: e.target.value })}
                  placeholder="Texto fixo"
                  className="rounded-md border border-outline-variant bg-surface px-3 py-2 text-sm text-on-surface"
                />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
