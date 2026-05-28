"use client";

import { useEffect, useState } from "react";
import { getSmtpConfig, saveSmtpConfig, testSmtpConfig } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import type { SmtpConfig, SmtpConfigInput } from "@/features/profile/types";

function FieldRow({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm font-medium text-on-surface">{label}</span>
      {description && (
        <span className="text-xs text-on-surface-variant">{description}</span>
      )}
      {children}
    </div>
  );
}

const inputCls =
  "w-full rounded-xl border border-outline-variant bg-surface px-3.5 py-2.5 text-sm text-on-surface placeholder:text-on-surface-variant/50 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20";

const selectCls =
  "w-full rounded-xl border border-outline-variant bg-surface px-3.5 py-2.5 text-sm text-on-surface outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20";

export function SmtpConfigForm() {
  const [loaded, setLoaded] = useState(false);
  const [hasExisting, setHasExisting] = useState(false);
  const [host, setHost] = useState("");
  const [port, setPort] = useState(587);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [useTls, setUseTls] = useState(true);
  const [fromName, setFromName] = useState("");
  const [fromEmail, setFromEmail] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testEmail, setTestEmail] = useState("");
  const toast = useToast();

  useEffect(() => {
    getSmtpConfig()
      .then((cfg: SmtpConfig | null) => {
        if (cfg) {
          setHost(cfg.host);
          setPort(cfg.port);
          setUsername(cfg.username);
          setUseTls(cfg.use_tls);
          setFromName(cfg.from_name);
          setFromEmail(cfg.from_email);
          setHasExisting(true);
        }
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await saveSmtpConfig({
        host,
        port: Number(port),
        username,
        password: password || null,
        use_tls: useTls,
        from_name: fromName,
        from_email: fromEmail,
      } as SmtpConfigInput);
      setHasExisting(true);
      setPassword("");
      toast.success("Configuração SMTP salva");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha ao salvar");
    } finally {
      setSaving(false);
    }
  }

  async function onTest() {
    if (!testEmail) {
      toast.error("Informe um email para teste");
      return;
    }
    setTesting(true);
    try {
      await testSmtpConfig(testEmail);
      toast.success("Email de teste enviado com sucesso");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha no teste SMTP");
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
      {/* ── Card header ── */}
      <div className="flex items-center justify-between border-b border-outline-variant/60 bg-surface-container-low dark:bg-surface-container px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-container">
            <span
              className="material-symbols-outlined text-on-primary-container"
              style={{ fontSize: "20px", fontVariationSettings: "'FILL' 1" }}
            >
              mail
            </span>
          </div>
          <div>
            <p className="text-sm font-semibold text-on-surface">Email (SMTP)</p>
            <p className="text-xs text-on-surface-variant">
              Servidor de envio para notificações e senhas de acesso
            </p>
          </div>
        </div>
        {/* Status badge */}
        {loaded && (
          <span
            className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
              hasExisting
                ? "bg-[color:var(--color-tertiary-container)] text-[color:var(--color-on-tertiary-container)]"
                : "bg-surface-container text-on-surface-variant"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${hasExisting ? "bg-[color:var(--color-tertiary)]" : "bg-on-surface-variant/40"}`}
            />
            {hasExisting ? "Configurado" : "Não configurado"}
          </span>
        )}
      </div>

      {!loaded ? (
        <div className="flex items-center gap-2 px-5 py-6 text-sm text-on-surface-variant">
          <span className="material-symbols-outlined animate-spin" style={{ fontSize: "18px" }}>
            progress_activity
          </span>
          Carregando...
        </div>
      ) : (
        <form onSubmit={onSave}>
          {/* ── Seção: Servidor ── */}
          <div className="px-5 py-5">
            <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-on-surface-variant/60">
              Servidor
            </p>
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2">
                <FieldRow label="Host SMTP">
                  <input
                    value={host}
                    onChange={(e) => setHost(e.target.value)}
                    required
                    placeholder="smtp.gmail.com"
                    className={inputCls}
                  />
                </FieldRow>
              </div>
              <FieldRow label="Porta">
                <input
                  type="number"
                  value={port}
                  onChange={(e) => setPort(Number(e.target.value))}
                  required
                  className={inputCls}
                />
              </FieldRow>
              <div className="col-span-3">
                <FieldRow label="Segurança" description="STARTTLS usa porta 587; SMTPS usa porta 465">
                  <div className="flex gap-2">
                    {(["STARTTLS (587)", "SMTPS (465)", "Nenhum"] as const).map((label, i) => {
                      const val = i === 0 ? "starttls" : i === 1 ? "smtps" : "none";
                      const active = i === 0 ? useTls : false;
                      return (
                        <button
                          key={label}
                          type="button"
                          onClick={() => setUseTls(i === 0)}
                          className={`flex-1 rounded-xl border px-3 py-2 text-sm font-medium transition ${
                            (i === 0 && useTls) || (i !== 0 && !useTls && i === 2)
                              ? "border-primary bg-primary/10 text-primary"
                              : "border-outline-variant bg-surface text-on-surface-variant hover:border-primary/40"
                          }`}
                        >
                          {label}
                        </button>
                      );
                    })}
                  </div>
                </FieldRow>
              </div>
            </div>
          </div>

          {/* ── Seção: Autenticação ── */}
          <div className="border-t border-outline-variant/60 px-5 py-5">
            <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-on-surface-variant/60">
              Autenticação
            </p>
            <div className="grid grid-cols-2 gap-4">
              <FieldRow label="Usuário">
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  placeholder="seu@email.com"
                  className={inputCls}
                />
              </FieldRow>
              <FieldRow
                label="Senha"
                description={hasExisting ? "Deixe em branco para manter a atual" : undefined}
              >
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={hasExisting ? "••••••••" : "Senha do servidor SMTP"}
                  className={inputCls}
                />
              </FieldRow>
            </div>
          </div>

          {/* ── Seção: Remetente ── */}
          <div className="border-t border-outline-variant/60 px-5 py-5">
            <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-on-surface-variant/60">
              Remetente
            </p>
            <div className="grid grid-cols-2 gap-4">
              <FieldRow label="Nome" description="Aparece no campo 'De' do email">
                <input
                  value={fromName}
                  onChange={(e) => setFromName(e.target.value)}
                  required
                  placeholder="NexoIA"
                  className={inputCls}
                />
              </FieldRow>
              <FieldRow label="Email" description="Endereço de envio">
                <input
                  type="email"
                  value={fromEmail}
                  onChange={(e) => setFromEmail(e.target.value)}
                  required
                  placeholder="noreply@empresa.com"
                  className={inputCls}
                />
              </FieldRow>
            </div>
          </div>

          {/* ── Footer: ações ── */}
          <div className="flex items-center justify-between border-t border-outline-variant/60 bg-surface-container-low/50 px-5 py-4">
            {/* Teste */}
            <div className="flex items-center gap-2">
              <input
                type="email"
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
                placeholder="Testar: email@destino.com"
                className="rounded-xl border border-outline-variant bg-surface px-3.5 py-2 text-sm text-on-surface placeholder:text-on-surface-variant/50 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 w-60"
              />
              <button
                type="button"
                onClick={onTest}
                disabled={testing || !hasExisting}
                className="flex items-center gap-1.5 rounded-xl border border-outline-variant bg-surface px-4 py-2 text-sm font-medium text-on-surface transition hover:bg-surface-container disabled:opacity-40"
              >
                <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                  {testing ? "progress_activity" : "send"}
                </span>
                {testing ? "Enviando..." : "Testar"}
              </button>
            </div>
            {/* Salvar */}
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-on-primary shadow-sm transition hover:opacity-90 disabled:opacity-50"
            >
              <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                {saving ? "progress_activity" : "save"}
              </span>
              {saving ? "Salvando..." : "Salvar configuração"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
