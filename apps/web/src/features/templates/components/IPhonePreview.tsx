"use client";

import type { MetaTemplate } from "../types";

interface Props {
  template: MetaTemplate;
}

/**
 * Renderiza um template Meta dentro de uma moldura iPhone com tela WhatsApp
 * (header verde + chat com bolha). Variáveis `{{var}}` aparecem destacadas.
 */
export function IPhonePreview({ template }: Props) {
  const header = template.components.find((c) => c.type === "HEADER");
  const body = template.components.find((c) => c.type === "BODY");
  const footer = template.components.find((c) => c.type === "FOOTER");
  const buttons =
    template.components.find((c) => c.type === "BUTTONS")?.buttons ?? [];

  const showImage = header?.format === "IMAGE" && template.media_url;
  const showVideo = header?.format === "VIDEO" && template.media_url;
  const showDoc = header?.format === "DOCUMENT" && template.media_url;
  const showTextHeader = header?.format === "TEXT" && header.text;

  return (
    <div className="relative mx-auto w-[280px] rounded-[38px] bg-black p-2 shadow-2xl">
      <div className="absolute left-1/2 top-2 z-10 h-6 w-[120px] -translate-x-1/2 rounded-b-2xl bg-black" />
      <div className="flex h-[540px] flex-col overflow-hidden rounded-[30px] bg-[#ece5dd]">
        {/* WhatsApp Header */}
        <div className="flex items-center gap-3 bg-[#075e54] pb-2 pl-3 pr-3 pt-8 text-white">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-400 text-sm">
            👤
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold leading-tight">
              Cliente
            </p>
            <p className="text-[10px] opacity-80">online</p>
          </div>
          <div className="flex gap-3 text-sm opacity-80">
            <span>📞</span>
            <span>⋮</span>
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 overflow-y-auto p-3">
          <div className="max-w-[86%] rounded-lg rounded-bl-none bg-[#dcf8c6] p-2.5 shadow-sm">
            {showImage && (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={template.media_url ?? undefined}
                alt=""
                className="mb-1.5 h-[130px] w-full rounded object-cover"
              />
            )}
            {showVideo && (
              <video
                src={template.media_url ?? undefined}
                controls
                className="mb-1.5 h-[130px] w-full rounded bg-black"
              />
            )}
            {showDoc && (
              <a
                href={template.media_url ?? undefined}
                target="_blank"
                rel="noopener noreferrer"
                className="mb-1.5 flex items-center gap-1.5 rounded border border-zinc-300 bg-white px-2 py-1.5 text-[11px] text-zinc-800"
              >
                <span className="material-symbols-outlined text-sm">
                  description
                </span>
                <span className="truncate">{template.name}</span>
              </a>
            )}
            {showTextHeader && (
              <p className="mb-1.5 text-[12px] font-semibold text-zinc-900">
                {renderWithVariables(header?.text ?? "")}
              </p>
            )}
            {body?.text && (
              <p className="whitespace-pre-wrap text-[12px] leading-snug text-zinc-900">
                {renderWithVariables(body.text)}
              </p>
            )}
            {footer?.text && (
              <p className="mt-1.5 text-[10px] italic text-zinc-500">
                {footer.text}
              </p>
            )}
            <p className="mt-1 text-right text-[9px] text-zinc-500">
              14:23 <span>✓✓</span>
            </p>
          </div>
          {buttons.length > 0 && (
            <div className="ml-0 mt-1 flex flex-col gap-0.5">
              {buttons.map(
                (btn: { type?: string; text?: string }, i: number) => (
                  <div
                    key={i}
                    className="rounded border border-zinc-300 bg-white py-1.5 text-center text-[11px] font-medium text-sky-700"
                  >
                    {btn.text ?? "Botão"}
                  </div>
                ),
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Renderiza `{{var}}` com destaque cinza (chip). */
function renderWithVariables(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const regex = /\{\{([^}]+)\}\}/g;
  let lastIdx = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIdx) parts.push(text.slice(lastIdx, match.index));
    parts.push(
      <span
        key={`v-${match.index}`}
        className="rounded bg-zinc-200 px-1 py-0.5 font-mono text-[10px] text-zinc-700"
      >{`{{${match[1]}}}`}</span>,
    );
    lastIdx = regex.lastIndex;
  }
  if (lastIdx < text.length) parts.push(text.slice(lastIdx));
  return parts.length > 0 ? parts : text;
}
