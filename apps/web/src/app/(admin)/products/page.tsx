"use client";

import { useState } from "react";
import { useProducts } from "@/features/courses/hooks/useCourses";
import { CourseCard } from "@/features/courses/components/CourseCard";
import { CourseDrawer } from "@/features/courses/components/CourseDrawer";
import { useToast } from "@/shared/hooks/useToast";
import type { Product, CreateProductInput } from "@/features/courses/types";

export default function ProductsPage() {
  const { products, loading, error, create, update, remove } = useProducts();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const toast = useToast();

  const openCreate = () => {
    setEditing(null);
    setDrawerOpen(true);
  };
  const openEdit = (p: Product) => {
    setEditing(p);
    setDrawerOpen(true);
  };

  const handleSubmit = async (input: CreateProductInput) => {
    try {
      if (editing) {
        await update(editing.id, input);
        toast.success("Produto atualizado");
      } else {
        await create(input);
        toast.success("Produto criado");
      }
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("409")) {
        toast.error("Já existe produto com esse ID Hubla");
      } else {
        toast.error("Falha ao salvar produto", msg);
      }
      throw e;
    }
  };

  const handleDelete = async (p: Product) => {
    if (!confirm(`Remover o produto "${p.name}"?`)) return;
    try {
      await remove(p.id);
      toast.success("Produto removido");
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("409")) {
        toast.warning("Não é possível remover", "Existem follow-ups vinculados a este produto.");
      } else {
        toast.error("Falha ao remover", msg);
      }
    }
  };

  return (
    <div className="flex flex-col gap-6 p-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-on-surface">Produtos</h1>
          <p className="text-sm text-on-surface-variant">
            Gerencie os produtos vinculados aos seus flows de follow-up.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-on-primary"
        >
          <span className="material-symbols-outlined">add</span>
          Novo produto
        </button>
      </header>

      {loading && <p className="text-on-surface-variant">Carregando...</p>}
      {error && <p className="text-error">{error}</p>}
      {!loading && products.length === 0 && (
        <div className="rounded-lg border border-dashed border-outline-variant p-8 text-center text-on-surface-variant">
          Nenhum produto cadastrado ainda.
        </div>
      )}

      <div className="flex flex-col gap-3">
        {products.map((p) => (
          <CourseCard
            key={p.id}
            product={p}
            onEdit={() => openEdit(p)}
            onDelete={() => void handleDelete(p)}
          />
        ))}
      </div>

      <CourseDrawer
        open={drawerOpen}
        product={editing}
        onClose={() => setDrawerOpen(false)}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
