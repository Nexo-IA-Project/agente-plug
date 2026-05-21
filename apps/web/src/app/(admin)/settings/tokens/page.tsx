"use client";

import { useEffect, useState } from "react";
import {
  listApiTokens,
  createApiToken,
  revokeApiToken,
  type ApiToken,
  type CreateApiTokenResponse,
} from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import { useConfirm } from "@/shared/components/confirm/ConfirmProvider";

export default function ApiTokensPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const [tokens, setTokens] = useState<ApiToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newTokenName, setNewTokenName] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [createdToken, setCreatedToken] = useState<CreateApiTokenResponse | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function loadTokens() {
    try {
      const data = await listApiTokens();
      setTokens(data);
    } catch {
      toast.error("Erro ao carregar tokens");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTokens();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newTokenName.trim()) return;
    setCreating(true);
    try {
      const result = await createApiToken(newTokenName.trim());
      setCreatedToken(result);
      setNewTokenName("");
      setShowForm(false);
      await loadTokens();
    } catch {
      toast.error("Erro ao criar token");
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(tokenId: string, name: string) {
    const ok = await confirm({
      title: "Revogar token",
      description: `Tem certeza que deseja revogar o token "${name}"? Esta ação não pode ser desfeita e qualquer integração que usa este token irá parar de funcionar.`,
      confirmLabel: "Revogar",
      variant: "danger",
    });
    if (!ok) return;
    setRevoking(tokenId);
    try {
      await revokeApiToken(tokenId);
      toast.success(`Token "${name}" revogado`);
      setTokens((prev) => prev.filter((t) => t.id !== tokenId));
    } catch {
      toast.error("Erro ao revogar token");
    } finally {
      setRevoking(null);
    }
  }

  function copyToken() {
    if (!createdToken) return;
    navigator.clipboard.writeText(createdToken.raw_token).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-h1 font-sans font-bold text-on-background">
            Tokens de API
          </h1>
          <p className="mt-1 text-body-base text-on-surface-variant">
            Tokens Bearer para autenticação do webhook. Mostre o valor apenas uma vez ao criar.
          </p>
        </div>
        <button
          onClick={() => { setShowForm(true); setCreatedToken(null); }}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-mono-label font-semibold text-on-primary hover:opacity-90 transition-opacity"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>add</span>
          Novo token
        </button>
      </div>

      {/* Token criado — mostrar só uma vez */}
      {createdToken && (
        <div className="rounded-xl border border-green-500/30 bg-green-500/5 p-6">
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-green-400 mt-0.5" style={{ fontSize: 22 }}>
              check_circle
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-body-base font-semibold text-on-surface">
                Token <span className="text-green-400">{createdToken.name}</span> criado com sucesso
              </p>
              <p className="mt-1 text-body-sm text-on-surface-variant">
                Copie agora — este valor não será exibido novamente.
              </p>
              <div className="mt-3 flex items-center gap-3">
                <code className="flex-1 rounded-lg bg-surface-container-lowest px-4 py-3 font-mono text-sm text-green-400 border border-outline-variant truncate select-all">
                  {createdToken.raw_token}
                </code>
                <button
                  onClick={copyToken}
                  className="flex items-center gap-1.5 rounded-lg border border-outline-variant px-3 py-3 text-body-sm text-on-surface hover:bg-surface-container-high transition-colors shrink-0"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                    {copied ? "check" : "content_copy"}
                  </span>
                  {copied ? "Copiado!" : "Copiar"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Form novo token */}
      {showForm && !createdToken && (
        <div className="rounded-xl border border-outline-variant bg-surface-container p-6">
          <h3 className="text-body-base font-semibold text-on-surface mb-4">Novo token</h3>
          <form onSubmit={handleCreate} className="flex items-end gap-3">
            <div className="flex-1">
              <label className="block text-label-caps text-on-surface-variant mb-2">
                Nome do token
              </label>
              <input
                type="text"
                value={newTokenName}
                onChange={(e) => setNewTokenName(e.target.value)}
                placeholder="ex: chatnexo-webhook"
                autoFocus
                required
                className="field-input"
              />
            </div>
            <button
              type="submit"
              disabled={creating}
              className="rounded-lg bg-primary px-5 py-2.5 text-body-sm font-semibold text-on-primary hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {creating ? "Criando..." : "Criar"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="rounded-lg border border-outline-variant px-5 py-2.5 text-body-sm text-on-surface hover:bg-surface-container-high transition-colors"
            >
              Cancelar
            </button>
          </form>
        </div>
      )}

      {/* Lista de tokens */}
      <div className="rounded-xl border border-outline-variant bg-surface-container">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-on-surface-variant">
            <span className="material-symbols-outlined animate-spin mr-2" style={{ fontSize: 20 }}>
              progress_activity
            </span>
            Carregando...
          </div>
        ) : tokens.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-on-surface-variant">
            <span className="material-symbols-outlined" style={{ fontSize: 40, opacity: 0.3 }}>
              key_off
            </span>
            <p className="text-body-sm">Nenhum token criado ainda.</p>
          </div>
        ) : (
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-outline-variant">
                <th className="px-6 py-4 text-left text-label-caps text-on-surface-variant">Nome</th>
                <th className="px-6 py-4 text-left text-label-caps text-on-surface-variant">Prefixo</th>
                <th className="px-6 py-4 text-left text-label-caps text-on-surface-variant">Criado em</th>
                <th className="px-6 py-4 text-left text-label-caps text-on-surface-variant">Último uso</th>
                <th className="px-6 py-4 text-left text-label-caps text-on-surface-variant">Status</th>
                <th className="px-6 py-4" />
              </tr>
            </thead>
            <tbody>
              {tokens.map((token, i) => (
                <tr
                  key={token.id}
                  className={`hover:bg-surface-container-high/50 transition-colors ${i < tokens.length - 1 ? "border-b border-outline-variant" : ""}`}
                >
                  <td className="px-6 py-4 text-body-base font-medium text-on-surface">
                    {token.name}
                  </td>
                  <td className="px-6 py-4">
                    {token.token_prefix ? (
                      <code className="rounded bg-surface-container-highest px-2 py-1 font-mono text-sm text-on-surface-variant">
                        {token.token_prefix}…
                      </code>
                    ) : (
                      <span className="text-on-surface-variant/40 text-sm">—</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-body-sm text-on-surface-variant">
                    {formatDate(token.created_at)}
                  </td>
                  <td className="px-6 py-4 text-body-sm text-on-surface-variant">
                    {token.last_used_at ? formatDate(token.last_used_at) : (
                      <span className="text-on-surface-variant/40">Nunca</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
                      token.is_active
                        ? "bg-green-500/10 text-green-400"
                        : "bg-surface-container-highest text-on-surface-variant"
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${token.is_active ? "bg-green-400" : "bg-on-surface-variant/40"}`} />
                      {token.is_active ? "Ativo" : "Revogado"}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    {token.is_active && (
                      <button
                        onClick={() => handleRevoke(token.id, token.name)}
                        disabled={revoking === token.id}
                        className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-error hover:bg-error/10 disabled:opacity-50 transition-colors ml-auto"
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 15 }}>
                          {revoking === token.id ? "progress_activity" : "key_off"}
                        </span>
                        {revoking === token.id ? "Revogando..." : "Revogar"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
