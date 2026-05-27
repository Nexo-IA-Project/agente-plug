"use client";

import { useEffect, useState } from "react";

import { getHublaWebhookToken } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WEBHOOK_BASE = `${API_BASE_URL.replace(/\/$/, "")}/webhook/hubla`;

export function HublaWebhookCard() {
  const toast = useToast();
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getHublaWebhookToken()
      .then((res) => {
        if (!cancelled) setToken(res.token || "");
      })
      .catch(() => {
        if (!cancelled) setToken("");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const hasToken = token !== null && token.length > 0;
  const url = hasToken
    ? `${WEBHOOK_BASE}?token=${encodeURIComponent(token)}`
    : WEBHOOK_BASE;

  async function copy(value: string, label: string) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
      } else {
        const ta = document.createElement("textarea");
        ta.value = value;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      toast.success(`${label} copiado`);
    } catch {
      toast.error("Falha ao copiar");
    }
  }

  return (
    <div className="mt-4 rounded-lg border border-outline-variant bg-surface-container-low p-4">
      <h4 className="text-sm font-semibold text-on-surface">URL do Webhook</h4>
      <p className="mt-1 text-xs text-on-surface-variant">
        Configure essa URL no painel da Hubla. O token de autenticação já está
        embutido na query string.
      </p>
      <div className="mt-3 flex items-center gap-2 rounded-md border border-outline-variant bg-surface px-3 py-2">
        <code className="flex-1 truncate font-mono text-xs text-on-surface">
          {token === null ? "Carregando..." : url}
        </code>
        <button
          type="button"
          disabled={token === null}
          onClick={() => void copy(url, "URL")}
          className="rounded-md p-1.5 text-on-surface-variant hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Copiar URL"
        >
          <span className="material-symbols-outlined text-base">
            content_copy
          </span>
        </button>
      </div>
      {token !== null && !hasToken && (
        <p className="mt-2 text-xs text-error">
          Defina o <strong>Webhook Secret</strong> acima e salve antes de copiar
          a URL — caso contrário a Hubla vai cair em 401.
        </p>
      )}

      <h4 className="mt-5 text-sm font-semibold text-on-surface">
        Como configurar na Hubla
      </h4>
      <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-xs text-on-surface-variant">
        <li>Acesse o painel da Hubla → Configurações → Webhooks.</li>
        <li>
          Crie um webhook novo e cole a URL acima no campo &quot;URL do
          endpoint&quot;.
        </li>
        <li>
          Selecione os eventos que quer disparar fluxos de onboarding (ex:{" "}
          <code>subscription.activated</code>,{" "}
          <code>lead.abandoned_checkout</code>, etc).
        </li>
        <li>
          Salve. A partir daí, qualquer evento dispara automaticamente os
          fluxos configurados em <strong>/onboarding</strong>.
        </li>
      </ol>
    </div>
  );
}
