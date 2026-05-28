"use client";

import { useEffect, useState } from "react";
import type { DateRange } from "react-day-picker";

import { Modal } from "@/shared/components/Modal";
import { DatePicker } from "@/shared/components/DatePicker";
import { useProducts } from "@/features/products/hooks/useProducts";
import { suggestUtmSources } from "@/lib/api";
import { getLeadStatusBadge } from "../lib/statusBadges";
import type { LeadFilters } from "../types";

interface Props {
  open: boolean;
  onClose: () => void;
  initial: LeadFilters;
  onApply: (filters: LeadFilters) => void;
}

const STATUS_OPTIONS = [
  { value: "", label: "Todos" },
  { value: "active", label: "Ativado" },
  { value: "inactive", label: "Inativo" },
  { value: "abandoned", label: "Abandonado" },
  { value: "refunded", label: "Reembolsado" },
  { value: "cancelled", label: "Cancelado" },
];

function toIso(d: Date | undefined, end = false): string | undefined {
  if (!d) return undefined;
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const suffix = end ? "T23:59:59.999-03:00" : "T00:00:00-03:00";
  return new Date(`${yyyy}-${mm}-${dd}${suffix}`).toISOString();
}

function fromIso(s: string | undefined): Date | undefined {
  return s ? new Date(s) : undefined;
}

export function LeadFiltersModal({ open, onClose, initial, onApply }: Props) {
  const { products } = useProducts();
  const [productId, setProductId] = useState<string>(initial.product_id ?? "");
  const [statusValue, setStatusValue] = useState<string>(initial.status ?? "");
  const [range, setRange] = useState<DateRange | undefined>({
    from: fromIso(initial.date_from),
    to: fromIso(initial.date_to),
  });
  const [utm, setUtm] = useState<string>(initial.utm_source ?? "");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  useEffect(() => {
    if (!open) return;
    setProductId(initial.product_id ?? "");
    setStatusValue(initial.status ?? "");
    setRange({
      from: fromIso(initial.date_from),
      to: fromIso(initial.date_to),
    });
    setUtm(initial.utm_source ?? "");
  }, [open, initial]);

  useEffect(() => {
    if (!open) return;
    suggestUtmSources(utm || undefined)
      .then(setSuggestions)
      .catch(() => setSuggestions([]));
  }, [open, utm]);

  const apply = () => {
    onApply({
      ...initial,
      product_id: productId || undefined,
      status: statusValue || undefined,
      date_from: toIso(range?.from),
      date_to: toIso(range?.to, true),
      utm_source: utm || undefined,
      page: 1,
    });
    onClose();
  };

  const clearAll = () => {
    setProductId("");
    setStatusValue("");
    setRange(undefined);
    setUtm("");
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Filtros"
      size="md"
      footer={
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={clearAll}
            className="text-sm text-on-surface-variant hover:underline"
          >
            Limpar tudo
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-outline-variant px-4 py-2 text-sm text-on-surface hover:bg-surface-container-high"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={apply}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:opacity-90"
            >
              Aplicar filtros
            </button>
          </div>
        </div>
      }
    >
      <div className="space-y-5">
        {/* Produto */}
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
            Produto
          </label>
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            className="field-select w-full"
          >
            <option value="">Todos os produtos</option>
            {products.map((p) => (
              <option key={p.id} value={p.hubla_id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        {/* Status */}
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
            Status
          </label>
          <div className="flex flex-wrap gap-2">
            {STATUS_OPTIONS.map((opt) => {
              const badge = opt.value
                ? getLeadStatusBadge(opt.value)
                : { className: "border-outline-variant text-on-surface" };
              const selected = statusValue === opt.value;
              return (
                <button
                  key={opt.value || "all"}
                  type="button"
                  onClick={() => setStatusValue(opt.value)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    selected
                      ? badge.className
                      : "border-outline-variant text-on-surface-variant hover:bg-surface-container-high"
                  }`}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Período */}
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
            Período
          </label>
          <DatePicker value={range} onChange={setRange} />
        </div>

        {/* UTM */}
        <div className="relative">
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
            UTM source
          </label>
          <input
            type="text"
            value={utm}
            onChange={(e) => {
              setUtm(e.target.value);
              setShowSuggestions(true);
            }}
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            placeholder="Ex.: facebook"
            className="field-input w-full"
          />
          {showSuggestions && suggestions.length > 0 && (
            <ul className="absolute left-0 right-0 z-10 mt-1 max-h-40 overflow-auto rounded-lg border border-outline-variant bg-surface-container-low shadow-lg">
              {suggestions.map((s) => (
                <li
                  key={s}
                  onMouseDown={() => {
                    setUtm(s);
                    setShowSuggestions(false);
                  }}
                  className="cursor-pointer px-3 py-1.5 text-sm hover:bg-surface-container"
                >
                  {s}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Modal>
  );
}
