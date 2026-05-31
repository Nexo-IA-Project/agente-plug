"use client";

import Link from "next/link";
import { RequirePermission } from "@/features/auth/components/RequirePermission";
import { IntegrationCard } from "@/features/settings/components/IntegrationCard";
import { useToast } from "@/shared/hooks/useToast";

export default function PagamentosSettingsPage() {
  const toast = useToast();

  const emBreve = () => toast.info("Integração em desenvolvimento — em breve.");

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
                payments
              </span>
            </div>
            <div className="flex-1">
              <Link
                href="/settings"
                className="inline-flex items-center gap-1 text-xs font-medium text-on-surface-variant transition-colors hover:text-on-surface"
              >
                <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>arrow_back</span>
                Integrações
              </Link>
              <h1 className="mt-1 text-2xl font-bold text-on-surface">Pagamentos</h1>
              <p className="mt-1 text-sm text-on-surface-variant">
                Gateways e plataformas de pagamento conectados ao agente.
              </p>
            </div>
          </div>
        </header>

        {/* Grade de gateways */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <IntegrationCard
            icon="bolt"
            title="Hubla"
            subtitle="Gateway de pagamento e webhooks de compra"
            status="active"
            href="/settings/pagamentos/hubla"
          />
          <IntegrationCard
            icon="local_fire_department"
            title="Hotmart"
            subtitle="Plataforma de produtos digitais"
            status="soon"
            onClick={emBreve}
          />
          <IntegrationCard
            icon="storefront"
            title="Kiwify"
            subtitle="Plataforma de vendas digitais"
            status="soon"
            onClick={emBreve}
          />
          <IntegrationCard
            icon="school"
            title="Eduzz"
            subtitle="Plataforma de infoprodutos"
            status="soon"
            onClick={emBreve}
          />
          <IntegrationCard
            icon="account_balance_wallet"
            title="Asaas"
            subtitle="Gateway de pagamentos"
            status="soon"
            onClick={emBreve}
          />
        </div>
      </div>
    </RequirePermission>
  );
}
