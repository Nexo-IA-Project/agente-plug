"use client";

import { useEffect, useState } from "react";
import { Drawer } from "@/shared/components/Drawer";
import { listProducts, resolveUnmapped, reprocessUnmapped } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import type { Product } from "@/features/products/types";
import type { UnmappedProduct, ReprocessScheduleMode } from "../types";

interface Props {
  open: boolean;
  item: UnmappedProduct | null;
  onClose: () => void;
  /** Chamado após resolver/reprocessar para recarregar a lista. */
  onResolved: () => void;
}

type Phase = "select" | "reprocess";

export function ResolveDrawer({ open, item, onClose, onResolved }: Props) {
  const toast = useToast();
  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [productId, setProductId] = useState("");
  const [phase, setPhase] = useState<Phase>("select");
  const [affectedLeads, setAffectedLeads] = useState(0);
  const [scheduleMode, setScheduleMode] = useState<ReprocessScheduleMode>("from_now");
  const [submitting, setSubmitting] = useState(false);

  // Reset ao abrir/trocar de item
  useEffect(() => {
    if (!open) return;
    setPhase("select");
    setProductId("");
    setAffectedLeads(0);
    setScheduleMode("from_now");
    setSubmitting(false);
  }, [open, item]);

  // Carrega produtos ativos para o dropdown
  useEffect(() => {
    if (!open) return;
    setProductsLoading(true);
    listProducts()
      .then((all) => setProducts(all.filter((p) => p.is_active)))
      .catch((e) =>
        toast.error(e instanceof Error ? e.message : "Erro ao carregar produtos"),
      )
      .finally(() => setProductsLoading(false));
    // toast intencionalmente omitido (novo objeto a cada render)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const handleResolve = async () => {
    if (!item || !productId) return;
    setSubmitting(true);
    try {
      const res = await resolveUnmapped({
        hubla_product_id: item.hubla_product_id,
        product_id: productId,
      });
      setAffectedLeads(res.affected_leads);
      setPhase("reprocess");
      toast.success(
        "Produto associado",
        `${res.affected_leads.toLocaleString("pt-BR")} lead${res.affected_leads === 1 ? "" : "s"} afetado${res.affected_leads === 1 ? "" : "s"}`,
      );
      onResolved();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao associar produto");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReprocess = async () => {
    if (!item) return;
    setSubmitting(true);
    try {
      const res = await reprocessUnmapped({
        hubla_product_id: item.hubla_product_id,
        schedule_mode: scheduleMode,
      });
      toast.success(
        "Reprocessamento enfileirado",
        `${res.enqueued.toLocaleString("pt-BR")} lead${res.enqueued === 1 ? "" : "s"} na fila`,
      );
      onResolved();
      onClose();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao reprocessar leads");
    } finally {
      setSubmitting(false);
    }
  };

  const footer =
    phase === "select" ? (
      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={onClose}
          className="rounded-md px-4 py-2 text-on-surface-variant hover:bg-surface-container-high"
        >
          Cancelar
        </button>
        <button
          type="button"
          onClick={() => void handleResolve()}
          disabled={submitting || !productId}
          className="rounded-md bg-primary px-4 py-2 text-on-primary disabled:opacity-50"
        >
          {submitting ? "Associando..." : "Associar"}
        </button>
      </div>
    ) : (
      <div className="flex justify-between gap-3">
        <button
          type="button"
          onClick={onClose}
          className="rounded-md px-4 py-2 text-on-surface-variant hover:bg-surface-container-high"
        >
          Fechar
        </button>
        <button
          type="button"
          onClick={() => void handleReprocess()}
          disabled={submitting || affectedLeads === 0}
          className="rounded-md bg-primary px-4 py-2 text-on-primary disabled:opacity-50"
        >
          {submitting
            ? "Reprocessando..."
            : `Reprocessar ${affectedLeads.toLocaleString("pt-BR")} lead${affectedLeads === 1 ? "" : "s"}`}
        </button>
      </div>
    );

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={
        item
          ? `Resolver pendência — ${item.product_name || item.hubla_product_id}`
          : "Resolver pendência"
      }
      footer={footer}
    >
      {item && (
        <div className="flex flex-col gap-6">
          {/* Resumo da pendência */}
          <div className="rounded-lg border border-outline-variant bg-surface-container-low p-4">
            <dl className="flex flex-col gap-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-on-surface-variant">Produto (Hubla)</dt>
                <dd className="font-medium text-on-surface">
                  {item.product_name || "Sem nome"}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-on-surface-variant">ID Hubla</dt>
                <dd className="font-mono text-xs text-on-surface">
                  {item.hubla_product_id}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-on-surface-variant">Leads afetados</dt>
                <dd className="font-medium text-on-surface">
                  {item.affected_leads.toLocaleString("pt-BR")}
                </dd>
              </div>
            </dl>
          </div>

          {phase === "select" ? (
            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-on-surface">
                Associar ao produto
              </span>
              <select
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                disabled={productsLoading}
                className="rounded-md border border-outline-variant bg-surface px-3 py-2 text-on-surface disabled:opacity-50"
              >
                <option value="">
                  {productsLoading ? "Carregando produtos..." : "Selecione um produto"}
                </option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.hubla_id})
                  </option>
                ))}
              </select>
              <span className="text-xs text-on-surface-variant">
                O ID Hubla acima passará a ser reconhecido como este produto nos
                próximos eventos.
              </span>
            </label>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="flex items-start gap-2 rounded-lg border border-outline-variant bg-surface-container-low p-3 text-sm text-on-surface">
                <span
                  className="material-symbols-outlined text-emerald-500"
                  style={{ fontSize: "20px" }}
                >
                  check_circle
                </span>
                <span>
                  Produto associado.{" "}
                  <strong>{affectedLeads.toLocaleString("pt-BR")}</strong> lead
                  {affectedLeads === 1 ? "" : "s"} afetado
                  {affectedLeads === 1 ? "" : "s"}. Escolha como reprocessá-los.
                </span>
              </div>

              <fieldset className="flex flex-col gap-3">
                <legend className="text-sm font-medium text-on-surface">
                  Modo de reprocessamento
                </legend>

                <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-outline-variant p-3 hover:bg-surface-container">
                  <input
                    type="radio"
                    name="schedule_mode"
                    value="from_now"
                    checked={scheduleMode === "from_now"}
                    onChange={() => setScheduleMode("from_now")}
                    className="mt-0.5 h-4 w-4"
                  />
                  <span className="flex flex-col gap-0.5">
                    <span className="text-sm font-medium text-on-surface">
                      Tratar como compra agora
                    </span>
                    <span className="text-xs text-on-surface-variant">
                      Os delays dos follow-ups são contados a partir de agora.
                    </span>
                  </span>
                </label>

                <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-outline-variant p-3 hover:bg-surface-container">
                  <input
                    type="radio"
                    name="schedule_mode"
                    value="original"
                    checked={scheduleMode === "original"}
                    onChange={() => setScheduleMode("original")}
                    className="mt-0.5 h-4 w-4"
                  />
                  <span className="flex flex-col gap-0.5">
                    <span className="text-sm font-medium text-on-surface">
                      Respeitar data original
                    </span>
                    <span className="text-xs text-on-surface-variant">
                      Os delays são contados a partir da data original do evento.
                      Atenção: follow-ups já vencidos podem disparar imediatamente.
                    </span>
                  </span>
                </label>
              </fieldset>
            </div>
          )}
        </div>
      )}
    </Drawer>
  );
}
