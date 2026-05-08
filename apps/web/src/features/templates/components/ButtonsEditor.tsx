"use client";

import {
  BUTTONS_TOTAL_MAX,
  BUTTON_LABEL_MAX,
  BUTTON_URL_MAX,
  CTA_BUTTONS_MAX,
} from "../validation";
import type { TemplateButton } from "../types";

interface Props {
  buttons: TemplateButton[];
  onChange: (buttons: TemplateButton[]) => void;
}

export function ButtonsEditor({ buttons, onChange }: Props) {
  const ctaCount = buttons.filter(
    (b) => b.type === "URL" || b.type === "PHONE_NUMBER",
  ).length;

  const add = (type: TemplateButton["type"]) => {
    if (buttons.length >= BUTTONS_TOTAL_MAX) return;
    if ((type === "URL" || type === "PHONE_NUMBER") && ctaCount >= CTA_BUTTONS_MAX) return;
    const next: TemplateButton = { type, text: "" };
    if (type === "URL") next.url = "";
    if (type === "PHONE_NUMBER") next.phone_number = "";
    onChange([...buttons, next]);
  };

  const update = (i: number, patch: Partial<TemplateButton>) => {
    const next = buttons.map((b, idx) => (idx === i ? { ...b, ...patch } : b));
    onChange(next);
  };

  const remove = (i: number) => {
    onChange(buttons.filter((_, idx) => idx !== i));
  };

  return (
    <div className="space-y-2">
      {buttons.map((b, i) => (
        <div
          key={i}
          className="flex items-center gap-2 p-2 rounded border border-outline-variant bg-surface-container"
        >
          <select
            className="px-2 py-1 rounded border border-outline-variant bg-surface text-sm"
            value={b.type}
            onChange={(e) =>
              update(i, { type: e.target.value as TemplateButton["type"] })
            }
          >
            <option value="QUICK_REPLY">Quick Reply</option>
            <option value="URL">URL</option>
            <option value="PHONE_NUMBER">Telefone</option>
          </select>
          <input
            type="text"
            className="flex-1 px-2 py-1 rounded border border-outline-variant bg-surface text-sm"
            placeholder="Label (max 25)"
            maxLength={BUTTON_LABEL_MAX}
            value={b.text}
            onChange={(e) => update(i, { text: e.target.value })}
          />
          {b.type === "URL" && (
            <input
              type="url"
              className="flex-[2] px-2 py-1 rounded border border-outline-variant bg-surface text-sm"
              placeholder="https://..."
              maxLength={BUTTON_URL_MAX}
              value={b.url || ""}
              onChange={(e) => update(i, { url: e.target.value })}
            />
          )}
          {b.type === "PHONE_NUMBER" && (
            <input
              type="tel"
              className="flex-[2] px-2 py-1 rounded border border-outline-variant bg-surface text-sm"
              placeholder="+5511999999999"
              value={b.phone_number || ""}
              onChange={(e) => update(i, { phone_number: e.target.value })}
            />
          )}
          <button
            type="button"
            className="text-error hover:underline text-sm"
            onClick={() => remove(i)}
          >
            Remover
          </button>
        </div>
      ))}
      <div className="flex gap-2">
        <button
          type="button"
          disabled={buttons.length >= BUTTONS_TOTAL_MAX}
          className="text-sm text-primary disabled:opacity-50 hover:underline"
          onClick={() => add("QUICK_REPLY")}
        >
          + Quick Reply
        </button>
        <button
          type="button"
          disabled={ctaCount >= CTA_BUTTONS_MAX || buttons.length >= BUTTONS_TOTAL_MAX}
          className="text-sm text-primary disabled:opacity-50 hover:underline"
          onClick={() => add("URL")}
        >
          + URL
        </button>
        <button
          type="button"
          disabled={ctaCount >= CTA_BUTTONS_MAX || buttons.length >= BUTTONS_TOTAL_MAX}
          className="text-sm text-primary disabled:opacity-50 hover:underline"
          onClick={() => add("PHONE_NUMBER")}
        >
          + Telefone
        </button>
      </div>
      <div className="text-xs text-on-surface-variant">
        Total: {buttons.length}/{BUTTONS_TOTAL_MAX} · CTA: {ctaCount}/{CTA_BUTTONS_MAX}
      </div>
    </div>
  );
}
