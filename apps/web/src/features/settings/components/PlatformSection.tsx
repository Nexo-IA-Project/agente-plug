"use client";

import { useEffect, useState } from "react";
import {
  getPlatformConfig,
  savePlatformConfig,
  testPlatformConfig,
} from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import type { PlatformConfig } from "@/features/settings/types";

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

function StatusBadge({ active, labelOn, labelOff }: { active: boolean; labelOn: string; labelOff: string }) {
  return (
    <span
      className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
        active
          ? "bg-[color:var(--color-tertiary-container)] text-[color:var(--color-on-tertiary-container)]"
          : "bg-surface-container text-on-surface-variant"
      }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${active ? "bg-[color:var(--color-tertiary)]" : "bg-on-surface-variant/40"}`}
      />
      {active ? labelOn : labelOff}
    </span>
  );
}

function CardHeader({
  icon,
  title,
  subtitle,
  badge,
}: {
  icon: string;
  title: string;
  subtitle: string;
  badge?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between border-b border-outline-variant/60 bg-surface-container-low dark:bg-surface-container px-5 py-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-container">
          <span
            className="material-symbols-outlined text-on-primary-container"
            style={{ fontSize: "20px", fontVariationSettings: "'FILL' 1" }}
          >
            {icon}
          </span>
        </div>
        <div>
          <p className="text-sm font-semibold text-on-surface">{title}</p>
          <p className="text-xs text-on-surface-variant">{subtitle}</p>
        </div>
      </div>
      {badge}
    </div>
  );
}

export function PlatformSection() {
  const toast = useToast();
  const [loaded, setLoaded] = useState(false);

  // OpenAI
  const [openaiConfigured, setOpenaiConfigured] = useState(false);
  const [openaiMask, setOpenaiMask] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [savingOpenai, setSavingOpenai] = useState(false);

  // SMTP
  const [hasPassword, setHasPassword] = useState(false);
  const [smtpConfigured, setSmtpConfigured] = useState(false);
  const [host, setHost] = useState("");
  const [port, setPort] = useState(587);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [useTls, setUseTls] = useState(true);
  const [fromName, setFromName] = useState("");
  const [fromEmail, setFromEmail] = useState("");
  const [savingSmtp, setSavingSmtp] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testEmail, setTestEmail] = useState("");

  function hydrate(cfg: PlatformConfig) {
    setOpenaiConfigured(cfg.openai_configured);
    setOpenaiMask(cfg.openai_api_key ?? "");
    const s = cfg.smtp;
    setHost(s.host ?? "");
    setPort(s.port ?? 587);
    setUsername(s.username ?? "");
    setUseTls(s.use_tls);
    setFromName(s.from_name ?? "");
    setFromEmail(s.from_email ?? "");
    setHasPassword(s.has_password);
    setSmtpConfigured(Boolean(s.host));
  }

  useEffect(() => {
    getPlatformConfig()
      .then((cfg) => {
        hydrate(cfg);
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  async function onSaveOpenai(e: React.FormEvent) {
    e.preventDefault();
    if (!openaiKey) {
      toast.error("Informe a API key da OpenAI");
      return;
    }
    setSavingOpenai(true);
    try {
      const updated = await savePlatformConfig({ openai_api_key: openaiKey });
      hydrate(updated);
      setOpenaiKey("");
      toast.success("Chave OpenAI salva");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha ao salvar");
    } finally {
      setSavingOpenai(false);
    }
  }

  async function onSaveSmtp(e: React.FormEvent) {
    e.preventDefault();
    setSavingSmtp(true);
    try {
      const updated = await savePlatformConfig({
        smtp: {
          host,
          port: Number(port),
          use_tls: useTls,
          username,
          password: password || null,
          from_name: fromName,
          from_email: fromEmail,
        },
      });
      hydrate(updated);
      setPassword("");
      toast.success("Configuração SMTP salva");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha ao salvar");
    } finally {
      setSavingSmtp(false);
    }
  }

  async function onTest() {
    if (!testEmail) {
      toast.error("Informe um email para teste");
      return;
    }
    setTesting(true);
    try {
      await testPlatformConfig(testEmail);
      toast.success("Email de teste enviado com sucesso");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha no teste SMTP");
    } finally {
      setTesting(false);
    }
  }

  return (
    <section>
      {/* Section title */}
      <div className="mb-6 flex items-center gap-3">
        <div className="h-5 w-1 rounded-full bg-primary" />
        <div>
          <h2 className="text-lg font-semibold text-on-surface">Plataforma / Núcleo</h2>
          <p className="mt-0.5 text-sm text-on-surface-variant">
            Configuração global da plataforma — compartilhada por todos os clientes, não pertence a uma conta específica.
          </p>
        </div>
      </div>

      {!loaded ? (
        <div className="flex items-center gap-2 rounded-2xl border border-outline-variant bg-white px-5 py-6 text-sm text-on-surface-variant dark:bg-surface-container">
          <span className="material-symbols-outlined animate-spin" style={{ fontSize: "18px" }}>
            progress_activity
          </span>
          Carregando...
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {/* ── OpenAI ── */}
          <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
            <CardHeader
              icon="psychology"
              title="OpenAI"
              subtitle="Modelo de linguagem e embeddings (chave global da plataforma)"
              badge={
                <StatusBadge active={openaiConfigured} labelOn="Configurado" labelOff="Não configurado" />
              }
            />
            <form onSubmit={onSaveOpenai} className="flex items-end gap-3 px-5 py-5">
              <div className="flex-1">
                <FieldRow
                  label="API Key"
                  description={
                    openaiConfigured
                      ? "Deixe em branco para manter a chave atual"
                      : undefined
                  }
                >
                  <input
                    type="password"
                    value={openaiKey}
                    onChange={(e) => setOpenaiKey(e.target.value)}
                    placeholder={openaiConfigured ? openaiMask || "Configurado" : "sk-proj-..."}
                    className={inputCls}
                    autoComplete="off"
                  />
                </FieldRow>
              </div>
              <button
                type="submit"
                disabled={savingOpenai}
                className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-on-primary shadow-sm transition hover:opacity-90 disabled:opacity-50"
              >
                <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                  {savingOpenai ? "progress_activity" : "save"}
                </span>
                {savingOpenai ? "Salvando..." : "Salvar"}
              </button>
            </form>
          </div>

          {/* ── SMTP ── */}
          <div className="overflow-hidden rounded-2xl border border-outline-variant bg-white dark:bg-surface-container">
            <CardHeader
              icon="mail"
              title="Email (SMTP)"
              subtitle="Servidor de envio para notificações e senhas de acesso"
              badge={
                <StatusBadge active={smtpConfigured} labelOn="Configurado" labelOff="Não configurado" />
              }
            />
            <form onSubmit={onSaveSmtp}>
              {/* Servidor */}
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
                        {(["STARTTLS (587)", "SMTPS (465)", "Nenhum"] as const).map((label, i) => (
                          <button
                            key={label}
                            type="button"
                            onClick={() => setUseTls(i === 0)}
                            className={`flex-1 rounded-xl border px-3 py-2 text-sm font-medium transition ${
                              (i === 0 && useTls) || (i === 2 && !useTls)
                                ? "border-primary bg-primary/10 text-primary"
                                : "border-outline-variant bg-surface text-on-surface-variant hover:border-primary/40"
                            }`}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                    </FieldRow>
                  </div>
                </div>
              </div>

              {/* Autenticação */}
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
                    description={hasPassword ? "Deixe em branco para manter a atual" : undefined}
                  >
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder={hasPassword ? "••••••••" : "Senha do servidor SMTP"}
                      className={inputCls}
                    />
                  </FieldRow>
                </div>
              </div>

              {/* Remetente */}
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

              {/* Footer */}
              <div className="flex items-center justify-between border-t border-outline-variant/60 bg-surface-container-low/50 px-5 py-4">
                <div className="flex items-center gap-2">
                  <input
                    type="email"
                    value={testEmail}
                    onChange={(e) => setTestEmail(e.target.value)}
                    placeholder="Testar: email@destino.com"
                    className="w-60 rounded-xl border border-outline-variant bg-surface px-3.5 py-2 text-sm text-on-surface placeholder:text-on-surface-variant/50 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                  />
                  <button
                    type="button"
                    onClick={onTest}
                    disabled={testing || !smtpConfigured}
                    className="flex items-center gap-1.5 rounded-xl border border-outline-variant bg-surface px-4 py-2 text-sm font-medium text-on-surface transition hover:bg-surface-container disabled:opacity-40"
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                      {testing ? "progress_activity" : "send"}
                    </span>
                    {testing ? "Enviando..." : "Testar"}
                  </button>
                </div>
                <button
                  type="submit"
                  disabled={savingSmtp}
                  className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-on-primary shadow-sm transition hover:opacity-90 disabled:opacity-50"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                    {savingSmtp ? "progress_activity" : "save"}
                  </span>
                  {savingSmtp ? "Salvando..." : "Salvar configuração"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}
