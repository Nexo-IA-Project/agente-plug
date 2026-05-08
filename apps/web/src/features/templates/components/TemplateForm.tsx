"use client";

import { useRef, useState } from "react";
import type { CreateTemplateDto } from "../types";
import { TemplatePreview } from "./TemplatePreview";

type HeaderType = "NONE" | "TEXT" | "IMAGE" | "VIDEO" | "DOCUMENT";
type ButtonType = "QUICK_REPLY" | "URL" | "PHONE_NUMBER";

interface ButtonDraft {
  type: ButtonType;
  text: string;
  url: string;
  phone_number: string;
}

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

const inputCls =
  "w-full rounded-lg border border-outline bg-surface px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary placeholder:text-on-surface-variant/50";
const labelCls = "mb-1 block text-xs font-medium text-on-surface-variant";

export function TemplateForm({ onCreate }: Props) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState<"MARKETING" | "UTILITY" | "AUTHENTICATION">("MARKETING");
  const [language, setLanguage] = useState("pt_BR");
  const [headerType, setHeaderType] = useState<HeaderType>("NONE");
  const [headerText, setHeaderText] = useState("");
  const [headerMediaUrl, setHeaderMediaUrl] = useState("");
  const [bodyText, setBodyText] = useState("");
  const [footerText, setFooterText] = useState("");
  const [buttons, setButtons] = useState<ButtonDraft[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bodyRef = useRef<HTMLTextAreaElement>(null);

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

  function addButton() {
    if (buttons.length >= 3) return;
    setButtons((b) => [...b, { type: "QUICK_REPLY", text: "", url: "", phone_number: "" }]);
  }

  function removeButton(i: number) {
    setButtons((b) => b.filter((_, idx) => idx !== i));
  }

  function updateButton(i: number, patch: Partial<ButtonDraft>) {
    setButtons((b) => b.map((btn, idx) => (idx === i ? { ...btn, ...patch } : btn)));
  }

  function buildComponents(): Record<string, unknown>[] {
    const components: Record<string, unknown>[] = [];

    if (headerType === "TEXT" && headerText.trim()) {
      components.push({ type: "HEADER", format: "TEXT", text: headerText.trim() });
    } else if (headerType !== "NONE" && headerMediaUrl.trim()) {
      components.push({
        type: "HEADER",
        format: headerType,
        example: { header_handle: [headerMediaUrl.trim()] },
      });
    }

    if (bodyText.trim()) {
      const vars = [...bodyText.matchAll(/\{\{(\d+)\}\}/g)].map((m) => m[1]);
      const bodyComp: Record<string, unknown> = { type: "BODY", text: bodyText.trim() };
      if (vars.length > 0) {
        bodyComp.example = { body_text: [vars.map((v) => `Valor ${v}`)] };
      }
      components.push(bodyComp);
    }

    if (footerText.trim()) {
      components.push({ type: "FOOTER", text: footerText.trim() });
    }

    if (buttons.length > 0) {
      components.push({
        type: "BUTTONS",
        buttons: buttons
          .filter((b) => b.text.trim())
          .map((b) => {
            const btn: Record<string, string> = { type: b.type, text: b.text.trim() };
            if (b.type === "URL" && b.url.trim()) btn.url = b.url.trim();
            if (b.type === "PHONE_NUMBER" && b.phone_number.trim())
              btn.phone_number = b.phone_number.trim();
            return btn;
          }),
      });
    }

    return components;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!bodyText.trim()) {
      setError("O corpo da mensagem é obrigatório.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onCreate({
        name: name.toLowerCase().replace(/\s+/g, "_"),
        category,
        language,
        components: buildComponents(),
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao criar template na Meta.");
      setSaving(false);
    }
  }

  const previewButtons = buttons
    .filter((b) => b.text.trim())
    .map((b) => ({ type: b.type, text: b.text }));

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
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="ex: welcome_message"
                className={inputCls}
              />
              <p className="mt-1 text-xs text-on-surface-variant">
                Somente letras minúsculas, números e underscores.
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
                  <option value="AUTHENTICATION">Autenticação</option>
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
                    onClick={() => setHeaderType(opt.value)}
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
                <input
                  value={headerText}
                  onChange={(e) => setHeaderText(e.target.value)}
                  placeholder="Texto do cabeçalho"
                  className={inputCls}
                />
              )}
              {(headerType === "IMAGE" || headerType === "VIDEO" || headerType === "DOCUMENT") && (
                <input
                  value={headerMediaUrl}
                  onChange={(e) => setHeaderMediaUrl(e.target.value)}
                  placeholder="URL da mídia (ex: https://...)"
                  className={inputCls}
                />
              )}
            </div>

            {/* Body */}
            <div>
              <div className="mb-1 flex items-center justify-between">
                <label className={labelCls.replace("mb-1 ", "")}>
                  Body <span className="text-error">*</span>
                </label>
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
                className={inputCls}
              />
              <p className="mt-1 text-xs text-on-surface-variant">
                Use {`{{1}}`}, {`{{2}}`}... para variáveis dinâmicas. {bodyText.length}/1024
              </p>
            </div>

            {/* Footer */}
            <div>
              <label className={labelCls}>Rodapé (opcional)</label>
              <input
                value={footerText}
                onChange={(e) => setFooterText(e.target.value)}
                placeholder="Rodapé do template"
                className={inputCls}
              />
              <p className="mt-1 text-xs text-on-surface-variant">{footerText.length}/60</p>
            </div>
          </div>
        </section>

        {/* Botões */}
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-on-surface-variant">
              Botões (opcional)
            </h3>
            {buttons.length < 3 && (
              <button
                type="button"
                onClick={addButton}
                className="flex items-center gap-1.5 rounded-lg border border-outline-variant px-3 py-1.5 text-xs font-medium text-on-surface-variant hover:border-primary/40 hover:text-primary"
              >
                <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
                  add
                </span>
                Adicionar
              </button>
            )}
          </div>

          {buttons.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-outline-variant bg-surface-container-low px-5 py-4 text-center text-xs text-on-surface-variant">
              Nenhum botão (máx. 3)
            </div>
          ) : (
            <div className="space-y-3">
              {buttons.map((btn, i) => (
                <div
                  key={i}
                  className="rounded-2xl border border-outline-variant bg-surface-container-low p-4"
                >
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-xs font-medium text-on-surface">Botão {i + 1}</span>
                    <button
                      type="button"
                      onClick={() => removeButton(i)}
                      className="text-error hover:text-error/70"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                        delete
                      </span>
                    </button>
                  </div>
                  <div className="grid grid-cols-[140px_1fr] gap-3">
                    <div>
                      <label className={labelCls}>Tipo</label>
                      <select
                        value={btn.type}
                        onChange={(e) => updateButton(i, { type: e.target.value as ButtonType })}
                        className={inputCls}
                      >
                        <option value="QUICK_REPLY">Resposta rápida</option>
                        <option value="URL">URL</option>
                        <option value="PHONE_NUMBER">Telefone</option>
                      </select>
                    </div>
                    <div>
                      <label className={labelCls}>Texto do botão</label>
                      <input
                        value={btn.text}
                        onChange={(e) => updateButton(i, { text: e.target.value })}
                        placeholder="Ex: Ver detalhes"
                        className={inputCls}
                      />
                    </div>
                  </div>
                  {btn.type === "URL" && (
                    <div className="mt-3">
                      <label className={labelCls}>URL</label>
                      <input
                        value={btn.url}
                        onChange={(e) => updateButton(i, { url: e.target.value })}
                        placeholder="https://exemplo.com/{{1}}"
                        className={inputCls}
                      />
                    </div>
                  )}
                  {btn.type === "PHONE_NUMBER" && (
                    <div className="mt-3">
                      <label className={labelCls}>Número de telefone</label>
                      <input
                        value={btn.phone_number}
                        onChange={(e) => updateButton(i, { phone_number: e.target.value })}
                        placeholder="+5511999998888"
                        className={inputCls}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {error && (
          <div className="rounded-xl border border-error/30 bg-error-container px-4 py-3 text-sm text-error">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={saving}
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
        />
      </div>
    </div>
  );
}
