// apps/web/src/features/onboarding/components/TimeInputGroup.tsx
"use client";

import { useState, useEffect } from "react";

interface TimeInputGroupProps {
  totalMinutes: number;
  onChange: (totalMinutes: number) => void;
  /** Quando false, "Imediato" mostra aviso de "envio junto com a anterior". */
  isFirstStep?: boolean;
}

interface Decomposed {
  days: number;
  hours: number;
  minutes: number;
}

const PRESETS: { label: string; minutes: number }[] = [
  { label: "Imediato", minutes: 0 },
  { label: "15min", minutes: 15 },
  { label: "30min", minutes: 30 },
  { label: "1h", minutes: 60 },
  { label: "2h", minutes: 120 },
  { label: "1 dia", minutes: 1440 },
  { label: "2 dias", minutes: 2880 },
  { label: "3 dias", minutes: 4320 },
  { label: "7 dias", minutes: 10080 },
];

const MAX_DAYS = 365;
const MAX_TOTAL_MINUTES = MAX_DAYS * 24 * 60;

function decompose(totalMinutes: number): Decomposed {
  const safe = Math.max(0, Math.min(MAX_TOTAL_MINUTES, totalMinutes));
  const days = Math.floor(safe / 1440);
  const remainAfterDays = safe - days * 1440;
  const hours = Math.floor(remainAfterDays / 60);
  const minutes = remainAfterDays - hours * 60;
  return { days, hours, minutes };
}

function compose(d: Decomposed): number {
  return d.days * 1440 + d.hours * 60 + d.minutes;
}

export function TimeInputGroup({
  totalMinutes,
  onChange,
  isFirstStep = false,
}: TimeInputGroupProps) {
  const initial = decompose(totalMinutes);
  const [days, setDays] = useState(initial.days);
  const [hours, setHours] = useState(initial.hours);
  const [minutes, setMinutes] = useState(initial.minutes);

  // Sync down se prop externa mudar (auto-fill, edit step)
  useEffect(() => {
    const d = decompose(totalMinutes);
    setDays(d.days);
    setHours(d.hours);
    setMinutes(d.minutes);
  }, [totalMinutes]);

  function emit(d: number, h: number, m: number) {
    const total = compose({ days: d, hours: h, minutes: m });
    onChange(Math.min(MAX_TOTAL_MINUTES, Math.max(0, total)));
  }

  function handleBlur() {
    // Normalização: 90 min → 1h 30min; 30h → 1d 6h
    const total = compose({ days, hours, minutes });
    const normalized = decompose(total);
    setDays(normalized.days);
    setHours(normalized.hours);
    setMinutes(normalized.minutes);
    onChange(total);
  }

  function applyPreset(min: number) {
    const d = decompose(min);
    setDays(d.days);
    setHours(d.hours);
    setMinutes(d.minutes);
    onChange(min);
  }

  const currentTotal = compose({ days, hours, minutes });
  const activePreset = PRESETS.find((p) => p.minutes === currentTotal);
  const showImmediateWarning = currentTotal === 0 && !isFirstStep;

  return (
    <div className="space-y-3">
      <div className="flex items-end gap-2">
        <Spinner
          label="Dias"
          value={days}
          min={0}
          max={MAX_DAYS}
          onChange={(v) => {
            setDays(v);
            emit(v, hours, minutes);
          }}
          onBlur={handleBlur}
        />
        <Spinner
          label="Horas"
          value={hours}
          min={0}
          max={999}
          onChange={(v) => {
            setHours(v);
            emit(days, v, minutes);
          }}
          onBlur={handleBlur}
        />
        <Spinner
          label="Minutos"
          value={minutes}
          min={0}
          max={999}
          onChange={(v) => {
            setMinutes(v);
            emit(days, hours, v);
          }}
          onBlur={handleBlur}
        />
      </div>

      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            onClick={() => applyPreset(p.minutes)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              activePreset?.label === p.label
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-outline-variant bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {showImmediateWarning && (
        <p className="text-xs italic text-on-surface-variant">
          Esta mensagem será enviada junto com a anterior.
        </p>
      )}
    </div>
  );
}

interface SpinnerProps {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
  onBlur: () => void;
}

function Spinner({ label, value, min, max, onChange, onBlur }: SpinnerProps) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
        {label}
      </span>
      <div className="flex items-center overflow-hidden rounded-lg border border-outline-variant bg-surface">
        <button
          type="button"
          onClick={() => onChange(Math.max(min, value - 1))}
          className="bg-surface-container px-2.5 py-1.5 text-on-surface-variant hover:bg-surface-container-high"
          aria-label={`Diminuir ${label.toLowerCase()}`}
        >
          −
        </button>
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          onChange={(e) => onChange(Math.max(min, Math.min(max, Number(e.target.value) || 0)))}
          onBlur={onBlur}
          className="w-14 border-0 bg-transparent text-center text-sm font-semibold text-on-surface outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
        />
        <button
          type="button"
          onClick={() => onChange(Math.min(max, value + 1))}
          className="bg-surface-container px-2.5 py-1.5 text-on-surface-variant hover:bg-surface-container-high"
          aria-label={`Aumentar ${label.toLowerCase()}`}
        >
          +
        </button>
      </div>
    </div>
  );
}
