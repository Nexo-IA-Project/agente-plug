"use client";

import { useState } from "react";
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

interface DraftButton {
  type: TemplateButton["type"];
  text: string;
  url: string;
  phone_number: string;
}

const TYPE_LABEL: Record<TemplateButton["type"], string> = {
  QUICK_REPLY: "Quick Reply",
  URL: "URL",
  PHONE_NUMBER: "Telefone",
};

const EMPTY_DRAFT: DraftButton = {
  type: "QUICK_REPLY",
  text: "",
  url: "",
  phone_number: "",
};

export function ButtonsEditor({ buttons, onChange }: Props) {
  const [draft, setDraft] = useState<DraftButton | null>(null);

  const ctaCount = buttons.filter(
    (b) => b.type === "URL" || b.type === "PHONE_NUMBER",
  ).length;

  const remove = (i: number) => {
    onChange(buttons.filter((_, idx) => idx !== i));
  };

  const isCta = (t: TemplateButton["type"]) => t === "URL" || t === "PHONE_NUMBER";

  const totalAtMax = buttons.length >= BUTTONS_TOTAL_MAX;
  const ctaAtMax = ctaCount >= CTA_BUTTONS_MAX;

  const draftValid = (): boolean => {
    if (!draft) return false;
    if (!draft.text.trim() || draft.text.length > BUTTON_LABEL_MAX) return false;
    if (draft.type === "URL") {
      if (!draft.url.trim() || draft.url.length > BUTTON_URL_MAX) return false;
      try {
        const u = new URL(draft.url);
        if (!["http:", "https:"].includes(u.protocol)) return false;
      } catch {
        return false;
      }
    }
    if (draft.type === "PHONE_NUMBER") {
      if (!/^\+\d{8,15}$/.test(draft.phone_number)) return false;
    }
    if (isCta(draft.type) && ctaAtMax) return false;
    return true;
  };

  const confirmDraft = () => {
    if (!draft || !draftValid()) return;
    const next: TemplateButton = { type: draft.type, text: draft.text };
    if (draft.type === "URL") next.url = draft.url;
    if (draft.type === "PHONE_NUMBER") next.phone_number = draft.phone_number;
    onChange([...buttons, next]);
    setDraft(null);
  };

  return (
    <div className="space-y-2">
      {buttons.map((b, i) => (
        <div
          key={i}
          className="flex items-center gap-3 p-3 rounded border border-outline-variant bg-surface-container"
        >
          <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium whitespace-nowrap">
            {TYPE_LABEL[b.type]}
          </span>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-on-surface truncate">{b.text}</div>
            {b.type === "URL" && b.url && (
              <div className="text-xs text-on-surface-variant truncate">{b.url}</div>
            )}
            {b.type === "PHONE_NUMBER" && b.phone_number && (
              <div className="text-xs text-on-surface-variant truncate">{b.phone_number}</div>
            )}
          </div>
          <button
            type="button"
            className="text-error hover:underline text-sm"
            onClick={() => remove(i)}
          >
            Remover
          </button>
        </div>
      ))}

      {draft && (
        <div className="rounded-lg border border-primary/40 bg-primary/5 p-3 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-on-surface">Novo botão</span>
            <button
              type="button"
              className="text-sm text-on-surface-variant hover:underline"
              onClick={() => setDraft(null)}
            >
              Cancelar
            </button>
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-medium text-on-surface-variant">
              Tipo
            </label>
            <select
              className="w-full px-3 py-2 rounded border border-outline-variant bg-surface text-sm"
              value={draft.type}
              onChange={(e) =>
                setDraft({ ...draft, type: e.target.value as TemplateButton["type"] })
              }
            >
              <option value="QUICK_REPLY">Quick Reply</option>
              <option value="URL" disabled={ctaAtMax && !isCta(draft.type)}>
                URL {ctaAtMax ? "(limite CTA atingido)" : ""}
              </option>
              <option value="PHONE_NUMBER" disabled={ctaAtMax && !isCta(draft.type)}>
                Telefone {ctaAtMax ? "(limite CTA atingido)" : ""}
              </option>
            </select>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <label className="font-medium text-on-surface-variant">
                Label do botão
              </label>
              <span
                className={
                  draft.text.length > BUTTON_LABEL_MAX
                    ? "text-error"
                    : "text-on-surface-variant"
                }
              >
                {draft.text.length}/{BUTTON_LABEL_MAX}
              </span>
            </div>
            <input
              type="text"
              className="w-full px-3 py-2 rounded border border-outline-variant bg-surface text-sm"
              placeholder="Ex.: Acessar curso"
              maxLength={BUTTON_LABEL_MAX}
              value={draft.text}
              onChange={(e) => setDraft({ ...draft, text: e.target.value })}
            />
          </div>

          {draft.type === "URL" && (
            <div className="space-y-2">
              <label className="block text-xs font-medium text-on-surface-variant">
                URL
              </label>
              <input
                type="url"
                className="w-full px-3 py-2 rounded border border-outline-variant bg-surface text-sm"
                placeholder="https://..."
                maxLength={BUTTON_URL_MAX}
                value={draft.url}
                onChange={(e) => setDraft({ ...draft, url: e.target.value })}
              />
            </div>
          )}

          {draft.type === "PHONE_NUMBER" && (
            <div className="space-y-2">
              <label className="block text-xs font-medium text-on-surface-variant">
                Telefone (E.164)
              </label>
              <input
                type="tel"
                className="w-full px-3 py-2 rounded border border-outline-variant bg-surface text-sm"
                placeholder="+5511999999999"
                value={draft.phone_number}
                onChange={(e) => setDraft({ ...draft, phone_number: e.target.value })}
              />
            </div>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              className="px-3 py-1.5 text-sm rounded text-on-surface-variant hover:bg-surface-container"
              onClick={() => setDraft(null)}
            >
              Cancelar
            </button>
            <button
              type="button"
              disabled={!draftValid()}
              className="px-3 py-1.5 text-sm rounded bg-primary text-on-primary disabled:opacity-50"
              onClick={confirmDraft}
            >
              Adicionar
            </button>
          </div>
        </div>
      )}

      {!draft && (
        <button
          type="button"
          disabled={totalAtMax}
          className="w-full py-2 rounded border border-dashed border-outline-variant text-sm text-primary hover:bg-primary/5 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={() => setDraft(EMPTY_DRAFT)}
        >
          + Adicionar botão
        </button>
      )}

      <div className="text-xs text-on-surface-variant">
        Total: {buttons.length}/{BUTTONS_TOTAL_MAX} · CTA: {ctaCount}/{CTA_BUTTONS_MAX}
      </div>
    </div>
  );
}
