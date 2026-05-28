"use client";

import { useEffect, useRef, useState } from "react";
import { DayPicker, type DateRange } from "react-day-picker";
import { ptBR } from "date-fns/locale";
import "react-day-picker/style.css";

interface Props {
  value: DateRange | undefined;
  onChange: (range: DateRange | undefined) => void;
  placeholder?: string;
}

function formatRange(r: DateRange | undefined): string {
  if (!r?.from) return "";
  const f = r.from.toLocaleDateString("pt-BR");
  if (!r.to) return f;
  const t = r.to.toLocaleDateString("pt-BR");
  return `${f} → ${t}`;
}

type PresetKey = "today" | "7d" | "30d" | "this-month";

function preset(name: PresetKey): DateRange {
  const now = new Date();
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  if (name === "today") return { from: start, to: start };
  if (name === "7d") {
    const from = new Date(start);
    from.setDate(from.getDate() - 6);
    return { from, to: start };
  }
  if (name === "30d") {
    const from = new Date(start);
    from.setDate(from.getDate() - 29);
    return { from, to: start };
  }
  // this-month
  const from = new Date(now.getFullYear(), now.getMonth(), 1);
  return { from, to: start };
}

export function DatePicker({
  value,
  onChange,
  placeholder = "Selecionar período",
}: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-low px-3 py-2 text-left text-sm text-on-surface"
      >
        <span
          className="material-symbols-outlined text-on-surface-variant"
          style={{ fontSize: "18px" }}
        >
          calendar_month
        </span>
        <span className={value?.from ? "text-on-surface" : "text-on-surface-variant"}>
          {formatRange(value) || placeholder}
        </span>
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-2 rounded-xl border border-outline-variant bg-surface-container p-3 shadow-xl">
          <div className="mb-2 flex flex-wrap gap-1.5">
            {([
              { label: "Hoje", key: "today" },
              { label: "7 dias", key: "7d" },
              { label: "30 dias", key: "30d" },
              { label: "Este mês", key: "this-month" },
            ] as { label: string; key: PresetKey }[]).map((p) => (
              <button
                key={p.key}
                type="button"
                onClick={() => onChange(preset(p.key))}
                className="rounded-full border border-outline-variant px-2.5 py-1 text-xs text-on-surface hover:bg-surface-container-high"
              >
                {p.label}
              </button>
            ))}
          </div>
          <DayPicker
            mode="range"
            selected={value}
            onSelect={onChange}
            locale={ptBR}
            weekStartsOn={0}
            className="text-sm"
          />
        </div>
      )}
    </div>
  );
}
