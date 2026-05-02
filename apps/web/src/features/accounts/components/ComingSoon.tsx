// apps/web/src/features/accounts/components/ComingSoon.tsx
"use client";

import { useRouter } from "next/navigation";

export function ComingSoon() {
  const router = useRouter();

  return (
    <div className="flex flex-1 items-center justify-center py-16">
      <div className="flex w-full max-w-lg flex-col items-center rounded-xl border border-outline-variant bg-surface-container-low p-card-padding text-center">
        <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-xl border border-outline-variant bg-surface-container">
          <span className="material-symbols-outlined text-primary" style={{ fontSize: "28px" }}>construction</span>
        </div>
        <span className="mb-4 text-label-caps font-sans uppercase tracking-widest text-primary">Em breve</span>
        <h2 className="text-h1 font-sans font-bold text-on-surface mb-4">Configuração de Contas</h2>
        <p className="text-body-base text-on-surface-variant max-w-sm">
          Em breve você poderá gerenciar múltiplas instâncias e configurações de inquilinos diretamente por aqui.
        </p>
        <button
          onClick={() => router.push("/dashboard")}
          className="mt-8 w-full rounded-lg bg-primary-container px-6 py-input-padding text-mono-label font-mono text-on-primary-container hover:opacity-90 transition-opacity"
        >
          Voltar ao Dashboard
        </button>
      </div>
    </div>
  );
}
