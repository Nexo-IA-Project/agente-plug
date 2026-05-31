"use client";

import { RequirePermission } from "@/features/auth/components/RequirePermission";
import { IntegrationCard } from "@/features/settings/components/IntegrationCard";

const WhatsAppIcon = (
  <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true">
    <path d="M19.05 4.91A9.82 9.82 0 0 0 12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38a9.86 9.86 0 0 0 4.73 1.2h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01zm-7.01 15.24h-.01a8.2 8.2 0 0 1-4.18-1.15l-.3-.18-3.11.82.83-3.04-.2-.31a8.18 8.18 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.24-8.24 2.2 0 4.27.86 5.82 2.42a8.18 8.18 0 0 1 2.41 5.83c0 4.54-3.7 8.24-8.23 8.24zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.25-.64.81-.79.97-.14.17-.29.19-.54.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.01-.38.11-.51.11-.11.25-.29.37-.43.13-.14.17-.25.25-.41.08-.17.04-.31-.02-.43-.06-.12-.56-1.34-.76-1.84-.2-.48-.41-.42-.56-.43-.14-.01-.31-.01-.48-.01-.17 0-.43.06-.66.31-.23.25-.86.85-.86 2.07 0 1.22.89 2.4 1.01 2.56.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.68-1.18.21-.58.21-1.07.14-1.18-.06-.1-.22-.16-.47-.28z" />
  </svg>
);

export default function SettingsPage() {
  return (
    <RequirePermission perm="settings.view">
      <div className="space-y-8 p-6">
        {/* Page header */}
        <header className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
          <div className="flex items-center gap-5 px-7 py-6">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary-container">
              <span
                className="material-symbols-outlined text-on-primary-container"
                style={{ fontSize: "28px", fontVariationSettings: "'FILL' 1" }}
              >
                hub
              </span>
            </div>
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-on-surface">Integrações</h1>
              <p className="mt-1 text-sm text-on-surface-variant">
                Conecte o agente aos seus canais e serviços.
              </p>
            </div>
          </div>
        </header>

        {/* Grade de integrações */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <IntegrationCard
            icon="chat"
            title="ChatNexo"
            subtitle="Conexão e atendentes do WhatsApp via ChatNexo"
            status="active"
            href="/settings/chatnexo"
          />
          <IntegrationCard
            icon="payments"
            title="Pagamentos"
            subtitle="Gateways e plataformas de pagamento"
            status="active"
            href="/settings/pagamentos"
          />
          <IntegrationCard
            iconSvg={WhatsAppIcon}
            title="WhatsApp"
            subtitle="Credenciais da API oficial do WhatsApp (Meta)"
            status="active"
            href="/settings/whatsapp"
          />
          <IntegrationCard
            icon="swap_horiz"
            title="Message Buffer"
            subtitle="Runtime externo de mensageria e webhook para plataformas externas"
            status="active"
            href="/settings/message-buffer"
          />
        </div>
      </div>
    </RequirePermission>
  );
}
