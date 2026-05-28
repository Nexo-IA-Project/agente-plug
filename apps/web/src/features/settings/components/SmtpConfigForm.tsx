"use client";

import { useEffect, useState } from "react";
import { getSmtpConfig, saveSmtpConfig, testSmtpConfig } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import type { SmtpConfig, SmtpConfigInput } from "@/features/profile/types";

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
      const input: SmtpConfigInput = {
        host,
        port: Number(port),
        username,
        password: password || null,
        use_tls: useTls,
        from_name: fromName,
        from_email: fromEmail,
      };
      await saveSmtpConfig(input);
      setHasExisting(true);
      setPassword("");
      toast.success("Configuração SMTP salva");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao salvar");
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
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha no teste SMTP");
    } finally {
      setTesting(false);
    }
  }

  if (!loaded) return <div className="text-on-surface-variant">Carregando SMTP...</div>;

  return (
    <section className="flex flex-col gap-4 max-w-2xl">
      <h2 className="text-title-lg">Email (SMTP)</h2>
      <form onSubmit={onSave} className="grid grid-cols-2 gap-4">
        <label className="flex flex-col gap-1 col-span-2">
          <span className="text-body-sm text-on-surface-variant">Host SMTP</span>
          <input
            value={host}
            onChange={(e) => setHost(e.target.value)}
            required
            placeholder="smtp.gmail.com"
            className="px-3 py-2 rounded border border-outline-variant bg-surface"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-body-sm text-on-surface-variant">Porta</span>
          <input
            type="number"
            value={port}
            onChange={(e) => setPort(Number(e.target.value))}
            required
            className="px-3 py-2 rounded border border-outline-variant bg-surface"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-body-sm text-on-surface-variant">TLS (STARTTLS)</span>
          <select
            value={useTls ? "1" : "0"}
            onChange={(e) => setUseTls(e.target.value === "1")}
            className="px-3 py-2 rounded border border-outline-variant bg-surface"
          >
            <option value="1">Ativado</option>
            <option value="0">Desativado</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 col-span-2">
          <span className="text-body-sm text-on-surface-variant">Usuário</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            className="px-3 py-2 rounded border border-outline-variant bg-surface"
          />
        </label>
        <label className="flex flex-col gap-1 col-span-2">
          <span className="text-body-sm text-on-surface-variant">
            Senha{" "}
            {hasExisting && (
              <em className="text-on-surface-variant text-label-sm">
                (deixe em branco para manter a atual)
              </em>
            )}
          </span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={hasExisting ? "••••••••" : ""}
            className="px-3 py-2 rounded border border-outline-variant bg-surface"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-body-sm text-on-surface-variant">Nome do remetente</span>
          <input
            value={fromName}
            onChange={(e) => setFromName(e.target.value)}
            required
            placeholder="NexoIA"
            className="px-3 py-2 rounded border border-outline-variant bg-surface"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-body-sm text-on-surface-variant">Email do remetente</span>
          <input
            type="email"
            value={fromEmail}
            onChange={(e) => setFromEmail(e.target.value)}
            required
            placeholder="noreply@empresa.com"
            className="px-3 py-2 rounded border border-outline-variant bg-surface"
          />
        </label>
        <div className="col-span-2">
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 rounded bg-primary text-on-primary disabled:opacity-50"
          >
            {saving ? "Salvando..." : "Salvar configuração"}
          </button>
        </div>
      </form>

      <div className="border-t border-outline-variant pt-4 flex gap-2 items-end">
        <label className="flex flex-col gap-1 flex-1">
          <span className="text-body-sm text-on-surface-variant">
            Testar enviando para:
          </span>
          <input
            type="email"
            value={testEmail}
            onChange={(e) => setTestEmail(e.target.value)}
            placeholder="email@destino.com"
            className="px-3 py-2 rounded border border-outline-variant bg-surface"
          />
        </label>
        <button
          type="button"
          onClick={onTest}
          disabled={testing || !hasExisting}
          className="px-4 py-2 rounded bg-secondary-container text-on-secondary-container disabled:opacity-50"
        >
          {testing ? "Enviando..." : "Testar"}
        </button>
      </div>
    </section>
  );
}
