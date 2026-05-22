"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createProduct,
  deleteProduct,
  listProducts,
  updateProduct,
} from "@/lib/api";
import type { Product, CreateProductInput, UpdateProductInput } from "../types";

export function useProducts() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listProducts();
      setProducts(data);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const create = useCallback(
    async (input: CreateProductInput): Promise<Product> => {
      const p = await createProduct(input);
      await refresh();
      return p;
    },
    [refresh]
  );

  const update = useCallback(
    async (id: string, input: UpdateProductInput): Promise<Product> => {
      const p = await updateProduct(id, input);
      await refresh();
      return p;
    },
    [refresh]
  );

  const remove = useCallback(
    async (id: string): Promise<void> => {
      await deleteProduct(id);
      await refresh();
    },
    [refresh]
  );

  return { products, loading, error, refresh, create, update, remove };
}
