"use client";

import { useRef, useState } from "react";
import type { CreateTemplateDto, MediaKind, TemplateButton, UploadedMedia } from "../types";
import { TemplatePreview } from "./TemplatePreview";
import { MediaUploadField } from "./MediaUploadField";
import { VariablesEditor } from "./VariablesEditor";
import { ButtonsEditor } from "./ButtonsEditor";
import {
  validateName,
  validateBody,
  validateHeader,
  validateFooter,
  validateButtons,
  HEADER_TEXT_MAX,
  BODY_TEXT_MAX,
  FOOTER_MAX,
  type ValidationError,
} from "../validation";
import { useToast } from "@/shared/hooks/useToast";

type HeaderType = "NONE" | "TEXT" | "IMAGE" | "VIDEO" | "DOCUMENT";

interface Props {
  onCreate: (dto: CreateTemplateDto) => Promise<void>;
}

const HEADER_OPTS: { value: HeaderType; label: string; icon: string }[] = [
  { value: "NONE", label: "Nenhum", icon: "block" },
  { value: "TEXT", label: "Texto", icon: "title" },
  { value: "IMAGE", label: "Imagem", icon: "image" },
  { value: "VIDEO", label: "Vídeo", icon: "videocam" },
  { value: "DOCUMENT", label: "Doc", icon: "description" },
];

const inputCls = "field-input";
const labelCls = "field-label";

function slugifyLive(input: string): string {
  // Versão ao vivo: preserva trailing `_` pra usuário poder continuar digitando
  // depois de espaço/separador. Trim final é feito no submit (slugifyFinal).
  return input
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // remove diacríticos (acentos)
    .replace(/[^a-z0-9]+/g, "_") // qualquer outro caractere → underscore
    .replace(/^_+/, "") // só remove underscores no início
    .slice(0, 512);
}

function slugifyFinal(input: string): string {
  return slugifyLive(input).replace(/_+$/, "");
}

export function TemplateForm({ onCreate }: Props) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState<"MARKETING" | "UTILITY">("MARKETING");
  const [language, setLanguage] = useState("pt_BR");
  const [headerType, setHeaderType] = useState<HeaderType>("NONE");
  const [headerText, setHeaderText] = useState("");
  const [media, setMedia] = useState<UploadedMedia | null>(null);
  const [bodyText, setBodyText] = useState("");
  const [bodyExamples, setBodyExamples] = useState<string[]>([]);
  const [footerText, setFooterText] = useState("");
  const [buttons, setButtons] = useState<TemplateButton[]>([]);
  const [saving, setSaving] = useState(false);
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const toast = useToast();

  function insertVariable() {
    const vars = [...bodyText.matchAll(/\{\{(\d+)\}\}/g)];
    const next = vars.length + 1;
    const tag = `{{${next}}}`;
    const el = bodyRef.current;
    if (el) {
      const start = el.selectionStart ?? bodyText.length;
      const end = el.selectionEnd ?? bodyText.length;
      const newText = bodyText.slice(0, start) + tag + bodyText.slice(end);
      setBodyText(newText);
      requestAnimationFrame(() => {
        el.focus();
        el.setSelectionRange(start + tag.length, start + tag.length);
      });
    } else {
      setBodyText((t) => t + tag);
    }
  }

  function buildDto(): CreateTemplateDto {
    const components: Record<string, unknown>[] = [];

    if (headerType === "TEXT" && headerText.trim()) {
      components.push({ type: "HEADER", format: "TEXT", text: headerText.trim() });
    } else if (
      media &&
      (headerType === "IMAGE" || headerType === "VIDEO" || headerType === "DOCUMENT")
    ) {
      components.push({
        type: "HEADER",
        format: headerType,
        example: { header_handle: [] },
      });
    }

    const bodyComponent: Record<string, unknown> = {
      type: "BODY",
      text: bodyText,
    };
    if (bodyExamples.length > 0 && bodyExamples.some((e) => e.trim())) {
      bodyComponent.example = { body_text: [bodyExamples] };
    }
    components.push(bodyComponent);

    if (footerText.trim()) {
      components.push({ type: "FOOTER", text: footerText.trim() });
    }

    if (buttons.length > 0) {
      components.push({ type: "BUTTONS", buttons });
    }

    return {
      name: slugifyFinal(name),
      category,
      language,
      components,
      media_url: media?.url ?? null,
      media_object_key: media?.objectKey ?? null,
      media_kind: media?.kind ?? null,
    };
  }

  function validateAll(): ValidationError[] {
    const errs: ValidationError[] = [];
    const ne = validateName(name);
    if (ne) errs.push(ne);
    errs.push(...validateHeader(headerType === "NONE" ? undefined : headerType, headerText));
    errs.push(...validateBody(bodyText, bodyExamples));
    if (footerText) errs.push(...validateFooter(footerText));
    errs.push(...validateButtons(buttons));
    return errs;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validateAll();
    if (errs.length > 0) {
      toast.error(errs[0].message);
      return;
    }
    setSaving(true);
    try {
      await onCreate(buildDto());
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erro ao criar template na Meta.");
      setSaving(false);
    }
  }

  const previewButtons = buttons
    .filter((b) => b.text.trim())
    .map((b) => ({ type: b.type, text: b.text }));

  const isMediaHeader =
    headerType === "IMAGE" || headerType === "VIDEO" || headerType === "DOCUMENT";

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_280px]">
      {/* ── FORM ── */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Informações básicas */}
        <section>
          <h3 className="mb-4 text-xs font-semibold uppercase tracking-widest text-on-surface-variant">
            Informações básicas
          </h3>
          <div className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container-low p-5">
            <div>
              <label className={labelCls}>Nome do template</label>
              <input
                value={name}
                onChange={(e) => setName(slugifyLive(e.target.value))}
                required
                placeholder="ex: welcome_message"
                className={inputCls}
              />
              <p className="mt-1 text-xs text-on-surface-variant">
                Convertido em tempo real para snake_case (a-z, 0-9, _).
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Categoria</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value as typeof category)}
                  className={inputCls}
                >
                  <option value="MARKETING">Marketing</option>
                  <option value="UTILITY">Utilitário</option>
                </select>
              </div>
              <div>
                <label className={labelCls}>Idioma</label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className={inputCls}
                >
                  <option value="pt_BR">Português (Brasil)</option>
                  <option value="en_US">English (US)</option>
                </select>
              </div>
            </div>
          </div>
        </section>

        {/* Componentes */}
        <section>
          <h3 className="mb-4 text-xs font-semibold uppercase tracking-widest text-on-surface-variant">
            Componentes
          </h3>
          <div className="space-y-4 rounded-2xl border border-outline-variant bg-surface-container-low p-5">
            {/* Header */}
            <div>
              <label className={labelCls}>Header (opcional)</label>
              <div className="mb-3 flex gap-2">
                {HEADER_OPTS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => {
                      setHeaderType(opt.value);
                      setMedia(null);
                    }}
                    className={[
                      "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                      headerType === opt.value
                        ? "border-primary bg-primary text-on-primary"
                        : "border-outline-variant bg-surface text-on-surface-variant hover:border-primary/40 hover:text-on-surface",
                    ].join(" ")}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
                      {opt.icon}
                    </span>
                    {opt.label}
                  </button>
                ))}
              </div>
              {headerType === "TEXT" && (
                <>
                  <input
                    value={headerText}
                    onChange={(e) => setHeaderText(e.target.value)}
                    placeholder="Texto do cabeçalho"
                    className={inputCls}
                  />
                  <p className="mt-1 text-xs text-on-surface-variant">
                    <span className={headerText.length > HEADER_TEXT_MAX ? "text-error" : ""}>
                      {headerText.length}/{HEADER_TEXT_MAX}
                    </span>
                  </p>
                </>
              )}
              {isMediaHeader && (
                <MediaUploadField
                  kind={headerType as MediaKind}
                  value={media}
                  onChange={setMedia}
                />
              )}
            </div>

            {/* Body */}
            <div>
              <div className="mb-1 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <label className={labelCls.replace("mb-1 ", "")}>
                    Body <span className="text-error">*</span>
                  </label>
                  <span
                    className={`text-xs ${bodyText.length > BODY_TEXT_MAX ? "text-error" : "text-on-surface-variant"}`}
                  >
                    {bodyText.length}/{BODY_TEXT_MAX}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={insertVariable}
                  className="flex items-center gap-1 rounded-lg border border-outline-variant px-2.5 py-1 text-xs font-medium text-on-surface-variant hover:border-primary/40 hover:text-primary"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: "13px" }}>
                    data_object
                  </span>
                  Variável
                </button>
              </div>
              <textarea
                ref={bodyRef}
                value={bodyText}
                onChange={(e) => setBodyText(e.target.value)}
                required
                rows={5}
                placeholder={"Olá {{1}}, seu acesso ao {{2}} está disponível!"}
                className="field-textarea"
              />
              <div className="mt-2">
                <VariablesEditor
                  bodyText={bodyText}
                  examples={bodyExamples}
                  onChange={setBodyExamples}
                />
              </div>
            </div>

            {/* Footer */}
            <div>
              <div className="mb-1 flex items-center justify-between">
                <label className={labelCls.replace("mb-1 ", "")}>Rodapé (opcional)</label>
                <span
                  className={`text-xs ${footerText.length > FOOTER_MAX ? "text-error" : "text-on-surface-variant"}`}
                >
                  {footerText.length}/{FOOTER_MAX}
                </span>
              </div>
              <input
                value={footerText}
                onChange={(e) => setFooterText(e.target.value)}
                placeholder="Rodapé do template"
                className={inputCls}
              />
            </div>
          </div>
        </section>

        {/* Botões */}
        <section>
          <h3 className="mb-4 text-xs font-semibold uppercase tracking-widest text-on-surface-variant">
            Botões (opcional)
          </h3>
          <div className="rounded-2xl border border-outline-variant bg-surface-container-low p-5">
            <ButtonsEditor buttons={buttons} onChange={setButtons} />
          </div>
        </section>

        <button
          type="submit"
          disabled={saving || validateAll().length > 0}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3 text-sm font-semibold text-on-primary transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
            send
          </span>
          {saving ? "Enviando para aprovação..." : "Enviar para aprovação"}
        </button>
      </form>

      {/* ── PREVIEW ── */}
      <div className="lg:sticky lg:top-6">
        <TemplatePreview
          body={bodyText || "Digite o texto do body..."}
          header={headerType === "TEXT" ? headerText || undefined : undefined}
          headerType={headerType === "NONE" ? undefined : headerType}
          footer={footerText || undefined}
          buttons={previewButtons}
          bodyExamples={bodyExamples}
        />
      </div>
    </div>
  );
}
