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

  const enabled = initial.message_buffer_enabled;

  async function toggleEnabled() {
    setTogglingEnabled(true);
    try {
      const updated = await updateAccountSettings({
        message_buffer_enabled: !enabled,
      });
      onSaved(updated);
      toast.success(
        updated.message_buffer_enabled
          ? "Servidor de mensagens ativado."
          : "Servidor de mensagens desativado."
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
          <h2 className="text-lg font-semibold text-on-surface">Servidor de mensagens externo</h2>
          <p className="mt-0.5 text-sm text-on-surface-variant">
            Conecte o Nexos Flow a um servidor de mensagens próprio. Quando ativado, os
            disparos de onboarding e follow-up são entregues por esse servidor — e não mais
            diretamente pelo ChatNexo.
          </p>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
        {/* Header com toggle */}
        <div className="flex items-center justify-between px-5 py-4">
          <div className="flex items-center gap-3">
            <div
              className={[
                "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors duration-300",
                enabled ? "bg-primary-container" : "bg-surface-container-high",
              ].join(" ")}
            >
              <span
                className={[
                  "material-symbols-outlined transition-colors duration-300",
                  enabled ? "text-on-primary-container" : "text-on-surface-variant",
                ].join(" ")}
                style={{ fontSize: "20px", fontVariationSettings: "'FILL' 1" }}
              >
                swap_horiz
              </span>
            </div>
            <div>
              <p className="text-sm font-semibold text-on-surface">
                {enabled ? "Ativado" : "Desativado"}
              </p>
              <p className="text-xs text-on-surface-variant">
                {enabled
                  ? "Os disparos estão sendo entregues pelo servidor externo"
                  : "Os disparos estão sendo enviados diretamente pelo ChatNexo"}
              </p>
            </div>
          </div>

          <button
            onClick={toggleEnabled}
            disabled={togglingEnabled}
            className={[
              "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent",
              "transition-colors duration-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
              enabled ? "bg-primary" : "bg-outline-variant",
              togglingEnabled ? "opacity-50 cursor-not-allowed" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            aria-checked={enabled}
            role="switch"
          >
            <span
              className={[
                "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform duration-300",
                enabled ? "translate-x-5" : "translate-x-0",
              ].join(" ")}
            />
          </button>
        </div>

        {/* Campos — aparecem só quando habilitado */}
        <div
          className={[
            "grid transition-all duration-300 ease-in-out",
            enabled ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
          ].join(" ")}
        >
          <div className="overflow-hidden">
            <div className="flex flex-col gap-5 border-t border-outline-variant/60 p-5">
              <InlineEditField
                label="Endereço do servidor"
                value={initial.message_buffer_outgoing_url ?? ""}
                type="url"
                placeholder="https://meu-servidor.com.br"
                description="O endereço para onde o Nexos Flow vai enviar as mensagens de onboarding e follow-up"
                onSave={(val) => saveField("message_buffer_outgoing_url", val)}
              />
              <InlineEditField
                label="Chave de acesso"
                value={initial.message_buffer_api_key ?? ""}
                type="secret"
                description="Código secreto que autoriza o Nexos Flow a se comunicar com o servidor. Fornecido pelo administrador do servidor."
                onSave={(val) => saveField("message_buffer_api_key", val)}
              />
              <InlineEditField
                label="ID da conta no servidor externo"
                value={initial.message_buffer_tenant_id ?? ""}
                type="text"
                placeholder="Opcional — deixe em branco se não souber"
                description="Alguns servidores usam um identificador próprio para a sua conta. Só preencha se o suporte do servidor solicitar."
                onSave={(val) => saveField("message_buffer_tenant_id", val)}
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
