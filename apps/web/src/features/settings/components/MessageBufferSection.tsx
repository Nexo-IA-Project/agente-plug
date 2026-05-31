"use client";

import { useState } from "react";
import { InlineEditField } from "@/features/settings/components/InlineEditField";
import { useFieldSave } from "@/features/settings/hooks/useIntegrationForm";
import { updateAccountSettings } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import type { AccountSettings } from "@/features/settings/types";

interface Props {
  initial: AccountSettings;
  onSaved: (updated: AccountSettings) => void;
}

export function MessageBufferSection({ initial, onSaved }: Props) {
  const { saveField } = useFieldSave(onSaved);
  const toast = useToast();
  const [togglingEnabled, setTogglingEnabled] = useState(false);

  async function toggleEnabled() {
    setTogglingEnabled(true);
    try {
      const updated = await updateAccountSettings({
        message_buffer_enabled: !initial.message_buffer_enabled,
      });
      onSaved(updated);
      toast.success(
        updated.message_buffer_enabled
          ? "Message Buffer habilitado."
          : "Message Buffer desabilitado."
      );
    } catch {
      toast.error("Erro ao atualizar configuração.");
    } finally {
      setTogglingEnabled(false);
    }
  }

  return (
    <section>
      <div className="mb-6 flex items-center gap-3">
        <div className="h-5 w-1 rounded-full bg-primary" />
        <div>
          <h2 className="text-lg font-semibold text-on-surface">Message Buffer</h2>
          <p className="mt-0.5 text-sm text-on-surface-variant">
            Runtime externo de mensageria. Quando habilitado, o Nexos Flow envia mensagens
            outgoing por aqui em vez de chamar o ChatNexo diretamente.
          </p>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
        {/* Header com toggle */}
        <div className="flex items-center justify-between border-b border-outline-variant/60 bg-surface-container-low dark:bg-surface-container px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-container">
              <span
                className="material-symbols-outlined text-on-primary-container"
                style={{ fontSize: "20px", fontVariationSettings: "'FILL' 1" }}
              >
                swap_horiz
              </span>
            </div>
            <div>
              <p className="text-sm font-semibold text-on-surface">Conexão</p>
              <p className="text-xs text-on-surface-variant">
                Endpoint que recebe mensagens outgoing do Flow
              </p>
            </div>
          </div>

          {/* Toggle habilitado */}
          <button
            onClick={toggleEnabled}
            disabled={togglingEnabled}
            className={[
              "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent",
              "transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
              initial.message_buffer_enabled ? "bg-primary" : "bg-outline-variant",
              togglingEnabled ? "opacity-50 cursor-not-allowed" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            aria-checked={initial.message_buffer_enabled}
            role="switch"
          >
            <span
              className={[
                "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform duration-200",
                initial.message_buffer_enabled ? "translate-x-5" : "translate-x-0",
              ].join(" ")}
            />
          </button>
        </div>

        {/* Campos */}
        <div className="flex flex-col gap-5 p-5">
          <InlineEditField
            label="URL de outgoing"
            value={initial.message_buffer_outgoing_url ?? ""}
            type="url"
            placeholder="https://nexushub.exemplo.com/outbound"
            description="Endpoint que o Nexos Flow chama para entregar mensagens ao runtime"
            onSave={(val) => saveField("message_buffer_outgoing_url", val)}
          />
          <InlineEditField
            label="API Key"
            value={initial.message_buffer_api_key ?? ""}
            type="secret"
            description="Credencial usada para autenticar com o Message Buffer"
            onSave={(val) => saveField("message_buffer_api_key", val)}
          />
          <InlineEditField
            label="Tenant ID externo"
            value={initial.message_buffer_tenant_id ?? ""}
            type="text"
            placeholder="opcional"
            description="ID do tenant no sistema externo, se diferente do UUID local"
            onSave={(val) => saveField("message_buffer_tenant_id", val)}
          />
        </div>

        {/* Webhook de entrada */}
        <div className="border-t border-outline-variant/60 bg-surface-container-low dark:bg-surface-container/50 px-5 py-4">
          <p className="text-xs font-medium text-on-surface-variant uppercase tracking-wide mb-2">
            Endpoint para receber mensagens externas
          </p>
          <p className="text-xs text-on-surface-variant mb-3">
            Plataformas externas (ex.: Nexus Hub, IA de atendimento) podem enviar mensagens
            diretamente para um contato usando o endpoint abaixo com um API token do painel.
          </p>
          <div className="flex items-center gap-2 rounded-xl bg-surface-container px-3 py-2 dark:bg-surface-container-high">
            <span
              className="material-symbols-outlined shrink-0 text-on-surface-variant"
              style={{ fontSize: "16px" }}
            >
              http
            </span>
            <code className="flex-1 select-all break-all font-mono text-xs text-on-surface">
              POST /webhook/outbound
            </code>
          </div>
          <p className="mt-2 text-xs text-on-surface-variant">
            Auth:{" "}
            <code className="rounded bg-surface-container px-1 py-0.5 font-mono text-xs">
              Authorization: Bearer &lt;api_token&gt;
            </code>
            {" · "}
            Body:{" "}
            <code className="rounded bg-surface-container px-1 py-0.5 font-mono text-xs">
              {"{ phone, text, conversation_id? }"}
            </code>
          </p>
        </div>
      </div>
    </section>
  );
}
