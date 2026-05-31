"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { getAccountSettings, updateAccountSettings } from "@/lib/api";
import { HublaWebhookCard } from "@/features/settings/components/HublaWebhookCard";
import { RequirePermission } from "@/features/auth/components/RequirePermission";
import { usePermission } from "@/features/auth/hooks/usePermission";
import { useToast } from "@/shared/hooks/useToast";

export default function HublaSettingsPage() {
  const toast = useToast();
  const canEdit = usePermission().can("settings.edit_credentials");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savedSecret, setSavedSecret] = useState("");
  const [secretInput, setSecretInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [clearing, setClearing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getAccountSettings()
      .then((s) => {
        if (cancelled) return;
        const secret = s.hubla_webhook_secret ?? "";
        setSavedSecret(secret);
        setSecretInput(secret);
      })
      .catch(() => {
        if (!cancelled) setError("Não foi possível carregar as configurações.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSave() {
    setSaving(true);
    try {
      await updateAccountSettings({ hubla_webhook_secret: secretInput });
      setSavedSecret(secretInput);
      toast.success("Chave salva");
    } catch {
      toast.error("Não foi possível salvar a chave.");
    } finally {
      setSaving(false);
    }
  }

  async function handleClear() {
    setClearing(true);
    try {
      await updateAccountSettings({ hubla_webhook_secret: "" });
      setSavedSecret("");
      setSecretInput("");
      toast.success("Chave removida");
    } catch {
      toast.error("Não foi possível remover a chave.");
    } finally {
      setClearing(false);
    }
  }

  const busy = saving || clearing;

  return (
    <RequirePermission perm="settings.view">
      {error ? (
        <div className="flex min-h-[200px] items-center justify-center">
          <div className="flex flex-col items-center gap-2 text-center">
            <span className="material-symbols-outlined text-error" style={{ fontSize: "32px" }}>
              error
            </span>
            <p className="text-sm font-medium text-error">{error}</p>
          </div>
        </div>
      ) : loading ? (
        <div className="flex min-h-[200px] items-center justify-center">
          <div className="flex items-center gap-2 text-sm text-on-surface-variant">
            <span className="material-symbols-outlined animate-spin" style={{ fontSize: "20px" }}>
              progress_activity
            </span>
            Carregando configurações...
          </div>
        </div>
      ) : (
        <div className="space-y-8 p-6">
          {/* Page header */}
          <header className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
            <div className="flex items-center gap-5 px-7 py-6">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary-container">
                <span
                  className="material-symbols-outlined text-on-primary-container"
                  style={{ fontSize: "28px", fontVariationSettings: "'FILL' 1" }}
                >
                  bolt
                </span>
              </div>
              <div className="flex-1">
                <Link
                  href="/settings/pagamentos"
                  className="inline-flex items-center gap-1 text-xs font-medium text-on-surface-variant transition-colors hover:text-on-surface"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                    arrow_back
                  </span>
                  Pagamentos
                </Link>
                <h1 className="mt-1 text-2xl font-bold text-on-surface">Hubla</h1>
                <p className="mt-1 text-sm text-on-surface-variant">
                  Gateway de pagamento e webhooks de compra integrados ao agente.
                </p>
              </div>
            </div>
          </header>

          {/* Card: Webhook da Hubla */}
          <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
            {/* Card header */}
            <div className="flex items-center gap-3 border-b border-outline-variant/60 bg-surface-container-low dark:bg-surface-container px-5 py-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-container">
                <span
                  className="material-symbols-outlined text-on-primary-container"
                  style={{ fontSize: "20px", fontVariationSettings: "'FILL' 1" }}
                >
                  key
                </span>
              </div>
              <div>
                <p className="text-sm font-semibold text-on-surface">Webhook da Hubla</p>
                <p className="text-xs text-on-surface-variant">
                  Autenticação dos eventos enviados pela Hubla
                </p>
              </div>
            </div>

            {/* Card body */}
            <div className="p-5">
              <p className="text-sm text-on-surface-variant">
                Essa chave autentica os eventos que a Hubla envia ao nosso webhook. Defina uma
                chave, salve, e cole a URL gerada no painel da Hubla. Sem ela, a Hubla recebe 401.
              </p>

              <div className="mt-4">
                <label
                  htmlFor="hubla-webhook-secret"
                  className="block text-sm font-medium text-on-surface"
                >
                  Chave secreta do webhook
                </label>
                <input
                  id="hubla-webhook-secret"
                  type="password"
                  autoComplete="off"
                  value={secretInput}
                  disabled={!canEdit || busy}
                  onChange={(e) => setSecretInput(e.target.value)}
                  placeholder="••••••••••••••••"
                  className="mt-1.5 w-full rounded-lg border border-outline-variant bg-surface px-3 py-2 font-mono text-sm text-on-surface outline-none transition-colors placeholder:text-on-surface-variant/60 focus:border-primary disabled:cursor-not-allowed disabled:opacity-60"
                />
              </div>

              {canEdit && (
                <div className="mt-4 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void handleSave()}
                    disabled={busy || secretInput === savedSecret}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {saving && (
                      <span
                        className="material-symbols-outlined animate-spin"
                        style={{ fontSize: "18px" }}
                      >
                        progress_activity
                      </span>
                    )}
                    Salvar
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleClear()}
                    disabled={busy || savedSecret.length === 0}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-outline-variant px-4 py-2 text-sm font-medium text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {clearing && (
                      <span
                        className="material-symbols-outlined animate-spin"
                        style={{ fontSize: "18px" }}
                      >
                        progress_activity
                      </span>
                    )}
                    Limpar
                  </button>
                </div>
              )}

              {/* Revelação condicional da URL do webhook */}
              <div
                className={`overflow-hidden transition-all duration-300 ease-in-out ${
                  savedSecret ? "mt-4 max-h-[700px] opacity-100" : "max-h-0 opacity-0"
                }`}
              >
                <HublaWebhookCard key={savedSecret} />
              </div>
            </div>
          </div>
        </div>
      )}
    </RequirePermission>
  );
}
