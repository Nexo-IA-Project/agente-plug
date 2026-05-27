// apps/web/src/features/onboarding/components/steps/StepProductPicker.tsx
"use client";

import type { Product } from "@/features/products/types";

interface StepProductPickerProps {
  products: Product[];
  loading: boolean;
  selectedProductId: string;
  onSelect: (productId: string) => void;
  disabled?: boolean;
}

export function StepProductPicker({
  products,
  loading,
  selectedProductId,
  onSelect,
  disabled = false,
}: StepProductPickerProps) {
  if (loading) {
    return (
      <div className="text-sm text-on-surface-variant">
        Carregando produtos...
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="rounded-md border border-outline-variant bg-surface-container p-4 text-sm text-on-surface-variant">
        Nenhum produto cadastrado. Cadastre um produto em{" "}
        <strong>/products</strong> antes de criar um flow.
      </div>
    );
  }

  return (
    <div>
      <label
        className="block text-sm font-medium text-on-surface"
        htmlFor="step-product-select"
      >
        Selecione o produto
      </label>
      <p className="mt-1 text-xs text-on-surface-variant">
        Cada flow de onboarding está vinculado a um produto do catálogo.
      </p>
      <select
        id="step-product-select"
        value={selectedProductId}
        onChange={(e) => onSelect(e.target.value)}
        disabled={disabled}
        className="mt-3 w-full rounded-md border border-outline-variant bg-surface-container px-3 py-2 text-sm text-on-surface focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-60"
      >
        <option value="">— Selecione —</option>
        {products.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>

      {selectedProductId && (
        <div className="mt-4 rounded-md border border-outline-variant bg-surface-container-high p-3 text-xs text-on-surface-variant">
          <span className="material-symbols-outlined align-middle text-sm">
            info
          </span>{" "}
          O nome do flow será gerado automaticamente como{" "}
          <code>
            Produto:{" "}
            {products.find((p) => p.id === selectedProductId)?.name ?? ""}
          </code>
          .
        </div>
      )}
    </div>
  );
}
