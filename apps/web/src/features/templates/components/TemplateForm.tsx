"use client";

import { useState } from "react";
import type { CreateTemplateDto } from "../types";
import { TemplatePreview } from "./TemplatePreview";

interface Props {
  onCreate: (dto: CreateTemplateDto) => Promise<void>;
}

export function TemplateForm({ onCreate }: Props) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState<"MARKETING" | "UTILITY" | "AUTHENTICATION">("MARKETING");
  const [language, setLanguage] = useState("pt_BR");
  const [bodyText, setBodyText] = useState("");
  const [headerText, setHeaderText] = useState("");
  const [footerText, setFooterText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function buildComponents(): Record<string, unknown>[] {
    const components: Record<string, unknown>[] = [];

    if (headerText.trim()) {
      components.push({ type: "HEADER", format: "TEXT", text: headerText.trim() });
    }

    if (bodyText.trim()) {
      const vars = [...bodyText.matchAll(/\{\{(\d+)\}\}/g)].map((m) => m[1]);
      const bodyComp: Record<string, unknown> = { type: "BODY", text: bodyText.trim() };
      if (vars.length > 0) {
        bodyComp.example = {
          body_text: [vars.map((v) => `Exemplo variável ${v}`)],
        };
      }
      components.push(bodyComp);
    }

    if (footerText.trim()) {
      components.push({ type: "FOOTER", text: footerText.trim() });
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

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="mb-1 block text-xs text-on-surface-variant">
            Nome do template
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="ex: mv_boas_vindas"
            className="w-full rounded-lg border border-outline bg-surface px-3 py-2 font-mono text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <p className="mt-1 text-xs text-on-surface-variant">
            Somente letras minúsculas, números e underscores.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-xs text-on-surface-variant">Categoria</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as typeof category)}
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="MARKETING">Marketing</option>
              <option value="UTILITY">Utilitário</option>
              <option value="AUTHENTICATION">Autenticação</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-on-surface-variant">Idioma</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="pt_BR">Português (BR)</option>
              <option value="en_US">English (US)</option>
            </select>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs text-on-surface-variant">
            Cabeçalho (opcional)
          </label>
          <input
            value={headerText}
            onChange={(e) => setHeaderText(e.target.value)}
            placeholder="Texto do cabeçalho"
            className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs text-on-surface-variant">
            Corpo da mensagem <span className="text-error">*</span>
          </label>
          <textarea
            value={bodyText}
            onChange={(e) => setBodyText(e.target.value)}
            required
            rows={5}
            placeholder="Olá {{1}}, seu acesso ao {{2}} está disponível!"
            className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <p className="mt-1 text-xs text-on-surface-variant">
            Use {`{{1}}`}, {`{{2}}`} para variáveis dinâmicas.
          </p>
        </div>

        <div>
          <label className="mb-1 block text-xs text-on-surface-variant">
            Rodapé (opcional)
          </label>
          <input
            value={footerText}
            onChange={(e) => setFooterText(e.target.value)}
            placeholder="Texto do rodapé"
            className="w-full rounded-lg border border-outline bg-surface px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        {error && (
          <div className="rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-error">
            {error}
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-on-primary disabled:opacity-50"
          >
            {saving ? "Enviando para Meta..." : "Enviar para Meta"}
          </button>
        </div>
      </form>

      <div className="lg:sticky lg:top-6">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
          Preview
        </p>
        <TemplatePreview
          body={bodyText || "Escreva o corpo da mensagem..."}
          header={headerText || undefined}
          footer={footerText || undefined}
        />
      </div>
    </div>
  );
}
