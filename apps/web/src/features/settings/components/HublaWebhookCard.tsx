"use client";

import { useToast } from "@/shared/hooks/useToast";

const HUBLA_WEBHOOK_URL = "https://api-iag2.ianexo.com.br/webhook/hubla";

export function HublaWebhookCard() {
  const toast = useToast();

  async function copy(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`${label} copiado`);
    } catch {
      toast.error("Falha ao copiar");
    }
  }

  return (
    <div className="mt-4 rounded-lg border border-outline-variant bg-surface-container-low p-4">
      <h4 className="text-sm font-semibold text-on-surface">URL do Webhook</h4>
      <p className="mt-1 text-xs text-on-surface-variant">
        Configure essa URL no painel da Hubla para receber eventos.
      </p>
      <div className="mt-3 flex items-center gap-2 rounded-md border border-outline-variant bg-surface px-3 py-2">
        <code className="flex-1 truncate font-mono text-xs text-on-surface">
          {HUBLA_WEBHOOK_URL}
        </code>
        <button
          type="button"
          onClick={() => void copy(HUBLA_WEBHOOK_URL, "URL")}
          className="rounded-md p-1.5 text-on-surface-variant hover:bg-surface-container-high"
          aria-label="Copiar URL"
        >
          <span className="material-symbols-outlined text-base">
            content_copy
          </span>
        </button>
      </div>

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
          No campo &quot;Secret&quot; / &quot;Token&quot;, cole o mesmo valor
          configurado em <strong>Webhook Secret</strong> acima.
        </li>
        <li>
          Selecione os eventos que quer disparar fluxos de onboarding (ex:{" "}
          <code>subscription.activated</code>,{" "}
          <code>lead.abandoned_cart</code>, etc).
        </li>
        <li>
          Salve. A partir daí, qualquer evento dispara automaticamente os
          fluxos configurados em <strong>/onboarding</strong>.
        </li>
      </ol>
    </div>
  );
}
