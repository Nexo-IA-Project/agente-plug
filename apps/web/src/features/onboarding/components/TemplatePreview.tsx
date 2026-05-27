"use client";

import type {
  MetaTemplate,
  TemplateButton,
  TemplateComponent,
} from "@/features/templates/types";
import {
  getMediaKind,
  getMediaUrl,
  hasMedia,
} from "../lib/templateMediaHelpers";

interface TemplatePreviewProps {
  template: MetaTemplate;
}

function getComponentText(
  components: TemplateComponent[],
  type: string,
): string | null {
  const c = components.find((x) => x.type === type);
  return c?.text ?? null;
}

function getButtons(components: TemplateComponent[]): TemplateButton[] {
  const c = components.find((x) => x.type === "BUTTONS");
  return c?.buttons ?? [];
}

/**
 * Preview da mensagem WhatsApp inline — bolha com mídia + body + footer + botões.
 * Renderiza inline (não modal) abaixo do select de template no StepInlineForm.
 */
export function TemplatePreview({ template }: TemplatePreviewProps) {
  const mediaUrl = getMediaUrl(template);
  const mediaKind = getMediaKind(template);
  const showMedia = hasMedia(template) && mediaUrl !== null;
  const headerText = getComponentText(template.components, "HEADER");
  const headerComp = template.components.find((c) => c.type === "HEADER");
  const bodyText = getComponentText(template.components, "BODY");
  const footerText = getComponentText(template.components, "FOOTER");
  const buttons = getButtons(template.components);

  return (
    <div className="rounded-lg border border-outline-variant bg-surface-container-low p-3">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
        Preview da mensagem
      </p>
      <div className="rounded-lg border border-outline-variant bg-surface-container p-3 shadow-sm">
        {/* Header com mídia */}
        {showMedia && mediaKind === "IMAGE" && (
          <img
            src={mediaUrl ?? undefined}
            alt="Header"
            className="mb-2 max-h-48 w-full rounded object-cover"
          />
        )}
        {showMedia && mediaKind === "VIDEO" && (
          <video
            src={mediaUrl ?? undefined}
            controls
            className="mb-2 max-h-48 w-full rounded bg-black"
          />
        )}
        {showMedia && mediaKind === "DOCUMENT" && (
          <a
            href={mediaUrl ?? undefined}
            target="_blank"
            rel="noopener noreferrer"
            className="mb-2 flex items-center gap-2 rounded border border-outline-variant bg-surface p-2 text-xs text-on-surface hover:bg-surface-container-high"
          >
            <span className="material-symbols-outlined text-base">
              description
            </span>
            <span className="truncate">{template.name}.pdf</span>
          </a>
        )}

        {/* Header em texto (quando não há mídia) */}
        {!showMedia && headerText && headerComp?.format === "TEXT" && (
          <p className="mb-2 text-sm font-semibold text-on-surface">
            {headerText}
          </p>
        )}

        {/* Body */}
        {bodyText && (
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-on-surface">
            {bodyText}
          </p>
        )}

        {/* Footer */}
        {footerText && (
          <p className="mt-2 text-xs italic text-on-surface-variant">
            {footerText}
          </p>
        )}

        {/* Botões */}
        {buttons.length > 0 && (
          <div className="mt-3 flex flex-col gap-1.5 border-t border-outline-variant pt-2">
            {buttons.map((btn, i) => (
              <div
                key={i}
                className="rounded border border-outline-variant bg-surface px-3 py-1.5 text-center text-xs text-primary"
              >
                {btn.text ?? "Botão"}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
