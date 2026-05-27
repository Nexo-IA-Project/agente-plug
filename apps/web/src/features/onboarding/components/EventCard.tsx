// apps/web/src/features/onboarding/components/EventCard.tsx
"use client";

import type { TriggerEventMeta } from "../lib/triggerEvents";

interface EventCardProps {
  event: TriggerEventMeta;
  selected: boolean;
  onSelect: () => void;
}

export function EventCard({ event, selected, onSelect }: EventCardProps) {
  const t = event.tone;
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`flex items-start gap-3 rounded-lg border p-3 text-left transition-all
        ${
          selected
            ? `${t.bgActive} ${t.border} ring-2 ${t.ring}`
            : "border-outline-variant bg-surface-container hover:bg-surface-container-high"
        }`}
    >
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-md ${t.bg}`}
      >
        <span className={`material-symbols-outlined ${t.text}`}>
          {event.icon}
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <h5 className="text-sm font-semibold text-on-surface">{event.label}</h5>
        <p className="mt-0.5 text-xs leading-snug text-on-surface-variant">
          {event.description}
        </p>
      </div>
    </button>
  );
}
