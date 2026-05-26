"use client";

import { useState, useEffect } from "react";
import {
  AgentItem,
  listChatnexoAgents,
  createChatnexoAgent,
  deleteChatnexoAgent,
} from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";

export function ChatNexoAgentsSection() {
  const toast = useToast();
  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listChatnexoAgents()
      .then(setAgents)
      .catch(() => toast.error("Erro ao carregar atendentes"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAdd() {
    if (!name.trim() || !apiKey.trim()) return;
    setSaving(true);
    try {
      const agent = await createChatnexoAgent({ name: name.trim(), api_key: apiKey.trim() });
      setAgents((prev) => [...prev, agent]);
      setName("");
      setApiKey("");
      toast.success(`Atendente "${agent.name}" adicionado`);
    } catch {
      toast.error("Erro ao adicionar atendente");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(agent: AgentItem) {
    try {
      await deleteChatnexoAgent(agent.id);
      setAgents((prev) => prev.filter((a) => a.id !== agent.id));
      toast.success(`Atendente "${agent.name}" removido`);
    } catch {
      toast.error("Erro ao remover atendente");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-on-surface">Atendentes ChatNexo</h3>
        <span className="text-xs text-on-surface-variant">
          {agents.length === 0
            ? "Nenhum atendente — usando chave de fallback"
            : `${agents.length} atendente${agents.length > 1 ? "s" : ""}`}
        </span>
      </div>

      {loading ? (
        <p className="text-sm text-on-surface-variant">Carregando...</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {agents.map((agent) => (
            <li
              key={agent.id}
              className="flex items-center justify-between rounded-lg border border-outline-variant bg-surface-container px-3 py-2"
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-medium text-on-surface">{agent.name}</span>
                <span className="font-mono text-xs text-on-surface-variant">
                  {agent.api_key_masked}
                </span>
              </div>
              <button
                onClick={() => handleDelete(agent)}
                className="text-on-surface-variant hover:text-error transition-colors"
                title="Remover atendente"
              >
                <span className="material-symbols-outlined text-[18px]">delete</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-col gap-2 rounded-lg border border-outline-variant bg-surface-container p-3">
        <p className="text-xs font-medium text-on-surface-variant">Adicionar atendente</p>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Nome do atendente"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1 rounded-md border border-outline-variant bg-surface px-3 py-1.5 text-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <input
            type="password"
            placeholder="API Key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="flex-1 rounded-md border border-outline-variant bg-surface px-3 py-1.5 text-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <button
            onClick={handleAdd}
            disabled={saving || !name.trim() || !apiKey.trim()}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-on-primary disabled:opacity-50 hover:opacity-90 transition-opacity"
          >
            {saving ? "..." : "Adicionar"}
          </button>
        </div>
      </div>
    </div>
  );
}
