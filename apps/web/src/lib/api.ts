// apps/web/src/lib/api.ts

import type {
  KbDocumentListResponse,
  UploadDocumentResponse,
} from "@/types/api";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      Accept: "application/json",
      ...(options?.headers ?? {}),
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ─── KB Admin ────────────────────────────────────────────────────────────────

export async function listDocuments(
  accountId: string,
): Promise<KbDocumentListResponse> {
  return apiFetch<KbDocumentListResponse>(
    `/admin/documents?account_id=${encodeURIComponent(accountId)}`,
  );
}

export async function uploadDocument(
  accountId: string,
  file: File,
): Promise<UploadDocumentResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("account_id", accountId);
  return apiFetch<UploadDocumentResponse>("/admin/documents", {
    method: "POST",
    body: form,
    // Do NOT set Content-Type — browser sets multipart boundary automatically
  });
}

export async function deleteDocument(
  documentId: string,
): Promise<void> {
  return apiFetch<void>(`/admin/documents/${documentId}`, {
    method: "DELETE",
  });
}
