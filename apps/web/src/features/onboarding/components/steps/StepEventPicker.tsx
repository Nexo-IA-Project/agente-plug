// apps/web/src/features/onboarding/components/steps/StepEventPicker.tsx
"use client";

import { useState } from "react";
import { EventCard } from "../EventCard";
import {
  CATEGORY_META,
  TRIGGER_EVENT_CATEGORIES,
  getEventsByCategory,
  type HublaEventCategory,
  type HublaEventType,
} from "../../lib/triggerEvents";

interface StepEventPickerProps {
  selectedEventType: HublaEventType;
  onSelect: (eventType: HublaEventType) => void;
  isActive: boolean;
  onToggleActive: (active: boolean) => void;
}

export function StepEventPicker({
  selectedEventType,
  onSelect,
  isActive,
  onToggleActive,
}: StepEventPickerProps) {
  // Inicializa tab na categoria do evento selecionado (ou subscription como default)
  const initialCategory: HublaEventCategory =
    TRIGGER_EVENT_CATEGORIES.find((c) =>
      getEventsByCategory(c).some((e) => e.value === selectedEventType),
    ) ?? "subscription";

  const [activeTab, setActiveTab] = useState<HublaEventCategory>(initialCategory);
  const events = getEventsByCategory(activeTab);

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-on-surface">
          Qual evento da Hubla dispara este flow?
        </h3>
        <p className="mt-1 text-xs text-on-surface-variant">
          Escolha a categoria nas abas e selecione o evento. Apenas um evento
          por flow.
        </p>
      </div>

      {/* Tabs de categoria */}
      <div className="flex flex-wrap gap-1 border-b border-outline-variant pb-2">
        {TRIGGER_EVENT_CATEGORIES.map((cat) => {
          const meta = CATEGORY_META[cat];
          const count = getEventsByCategory(cat).length;
          const active = activeTab === cat;
          return (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveTab(cat)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors
                ${
                  active
                    ? `${meta.tone.bgActive} ${meta.tone.text}`
                    : "text-on-surface-variant hover:bg-surface-container-high"
                }`}
            >
              <span className="material-symbols-outlined text-sm">
                {meta.icon}
              </span>
              {meta.label}
              <span className="rounded-full bg-black/10 px-1.5 text-[10px] font-semibold dark:bg-white/10">
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Grid de eventos da tab ativa */}
      <div
        key={activeTab}
        className="onboarding-step-fade grid grid-cols-1 gap-2 md:grid-cols-2"
      >
        {events.map((event) => (
          <EventCard
            key={event.value}
            event={event}
            selected={event.value === selectedEventType}
            onSelect={() => onSelect(event.value)}
          />
        ))}
      </div>

      {/* Toggle ativo */}
      <div className="flex items-center gap-2 pt-2">
        <input
          id="flow-is-active"
          type="checkbox"
          checked={isActive}
          onChange={(e) => onToggleActive(e.target.checked)}
          className="h-4 w-4 rounded border-outline-variant accent-primary"
        />
        <label htmlFor="flow-is-active" className="text-sm text-on-surface">
          Flow ativo (recebe eventos)
        </label>
      </div>
    </div>
  );
}
