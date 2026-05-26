// apps/web/src/lib/api.ts

import type {
  KbDocumentListResponse,
  UploadDocumentResponse,
} from "@/types/api";
import { getToken, clearToken } from "@/lib/auth";
import type { AccountSettings, AccountSettingsPatch } from "@/features/settings/types";
import type {
  CreateFlowInput,
  CreateStepInput,
  OnboardingFlow,
  OnboardingStep,
  ReorderItem,
  UpdateFlowInput,
  UpdateStepInput,
} from "@/features/onboarding/types";
import type {
  Product,
  CreateProductInput,
  UpdateProductInput,
} from "@/features/products/types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const token = getToken();
  const autoContentType: Record<string, string> =
    options?.body && typeof options.body === "string"
      ? { "Content-Type": "application/json" }
      : {};
  const res = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...autoContentType,
      ...(options?.headers ?? {}),
    },
  });

  if (!res.ok) {
    if (res.status === 401) {
      clearToken();
      if (typeof window !== "undefined") window.location.href = "/login";
      throw new Error("Sessão expirada");
    }
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }

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
  });
}

export async function deleteDocument(
  documentId: string,
): Promise<void> {
  return apiFetch<void>(`/admin/documents/${documentId}`, {
    method: "DELETE",
  });
}

// ─── API Tokens Admin ─────────────────────────────────────────────────────────

export interface ApiToken {
  id: string;
  name: string;
  token_prefix: string | null;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
}

export interface CreateApiTokenResponse {
  id: string;
  name: string;
  raw_token: string;
  created_at: string;
}

export async function listApiTokens(): Promise<ApiToken[]> {
  return apiFetch<ApiToken[]>("/admin/api-tokens");
}

export async function createApiToken(
  name: string,
): Promise<CreateApiTokenResponse> {
  return apiFetch<CreateApiTokenResponse>("/admin/api-tokens", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function revokeApiToken(tokenId: string): Promise<void> {
  return apiFetch<void>(`/admin/api-tokens/${tokenId}`, {
    method: "DELETE",
  });
}


// ─── Account Settings ─────────────────────────────────────────────────────────

export async function getAccountSettings(): Promise<AccountSettings> {
  return apiFetch<AccountSettings>("/admin/settings");
}

export async function updateAccountSettings(patch: AccountSettingsPatch): Promise<AccountSettings> {
  return apiFetch<AccountSettings>("/admin/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

// ─── Onboarding Flows ────────────────────────────────────────────────────────

export async function listOnboardingFlows(): Promise<OnboardingFlow[]> {
  return apiFetch<OnboardingFlow[]>("/admin/onboarding/flows");
}

export async function createOnboardingFlow(dto: CreateFlowInput): Promise<OnboardingFlow> {
  return apiFetch<OnboardingFlow>("/admin/onboarding/flows", {
    method: "POST",
    body: JSON.stringify(dto),
  });
}

export async function updateOnboardingFlow(id: string, dto: UpdateFlowInput): Promise<OnboardingFlow> {
  return apiFetch<OnboardingFlow>(`/admin/onboarding/flows/${id}`, {
    method: "PUT",
    body: JSON.stringify(dto),
  });
}

export async function deleteOnboardingFlow(id: string): Promise<void> {
  return apiFetch<void>(`/admin/onboarding/flows/${id}`, { method: "DELETE" });
}

export async function listOnboardingSteps(flowId: string): Promise<OnboardingStep[]> {
  return apiFetch<OnboardingStep[]>(`/admin/onboarding/flows/${flowId}/steps`);
}

export async function createOnboardingStep(
  flowId: string,
  dto: CreateStepInput
): Promise<OnboardingStep> {
  return apiFetch<OnboardingStep>(`/admin/onboarding/flows/${flowId}/steps`, {
    method: "POST",
    body: JSON.stringify(dto),
  });
}

export async function updateOnboardingStep(
  flowId: string,
  stepId: string,
  dto: UpdateStepInput
): Promise<OnboardingStep> {
  return apiFetch<OnboardingStep>(`/admin/onboarding/flows/${flowId}/steps/${stepId}`, {
    method: "PUT",
    body: JSON.stringify(dto),
  });
}

export async function deleteOnboardingStep(flowId: string, stepId: string): Promise<void> {
  return apiFetch<void>(`/admin/onboarding/flows/${flowId}/steps/${stepId}`, { method: "DELETE" });
}

export async function reorderOnboardingSteps(
  flowId: string,
  items: ReorderItem[]
): Promise<void> {
  return apiFetch<void>(`/admin/onboarding/flows/${flowId}/steps/reorder`, {
    method: "PATCH",
    body: JSON.stringify({ steps: items }),
  });
}


// ─── Products ────────────────────────────────────────────────────────────────

export async function listProducts(): Promise<Product[]> {
  return apiFetch<Product[]>("/admin/products");
}

export async function createProduct(input: CreateProductInput): Promise<Product> {
  return apiFetch<Product>("/admin/products", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateProduct(
  id: string,
  input: UpdateProductInput,
): Promise<Product> {
  return apiFetch<Product>(`/admin/products/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function deleteProduct(id: string): Promise<void> {
  return apiFetch<void>(`/admin/products/${id}`, { method: "DELETE" });
}


// ─── Meta Templates ──────────────────────────────────────────────────────────

import type { CreateTemplateDto, MetaTemplate } from "@/features/templates/types";
import type {
  LeadDetail,
  LeadFilters,
  LeadListResponse,
} from "@/features/leads/types";

export async function listMetaTemplates(): Promise<MetaTemplate[]> {
  return apiFetch("/admin/meta-templates");
}

export async function createMetaTemplate(dto: CreateTemplateDto): Promise<MetaTemplate> {
  return apiFetch("/admin/meta-templates", {
    method: "POST",
    body: JSON.stringify(dto),
  });
}

export async function deleteMetaTemplate(id: string): Promise<void> {
  await apiFetch<void>(`/admin/meta-templates/${id}`, { method: "DELETE" });
}

export interface UploadMediaResponse {
  media_url: string;
  media_object_key: string;
  media_kind: "IMAGE" | "VIDEO" | "DOCUMENT";
  sha256: string;
  size: number;
}

// ─── Leads ───────────────────────────────────────────────────────────────────

export async function listLeads(
  filters: LeadFilters = {},
): Promise<LeadListResponse> {
  const params = new URLSearchParams();
  if (filters.product_id) params.set("product_id", filters.product_id);
  if (filters.status) params.set("status", filters.status);
  if (filters.utm_source) params.set("utm_source", filters.utm_source);
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  if (filters.page) params.set("page", String(filters.page));
  if (filters.page_size) params.set("page_size", String(filters.page_size));
  const qs = params.toString();
  return apiFetch<LeadListResponse>(`/admin/leads${qs ? "?" + qs : ""}`);
}

export async function getLead(id: string): Promise<LeadDetail> {
  return apiFetch<LeadDetail>(`/admin/leads/${id}`);
}

/**
 * Força o disparo imediato de um step (pending ou failed) de um enrollment.
 * Backend cancela o job agendado (se houver) e dispara síncrono.
 */
export async function dispatchEnrollmentStep(
  enrollmentId: string,
  stepId: string,
): Promise<void> {
  return apiFetch<void>(
    `/admin/onboarding/enrollments/${enrollmentId}/steps/${stepId}/dispatch-now`,
    { method: "POST" },
  );
}

export async function downloadLeadsCsv(
  filters: LeadFilters = {},
): Promise<void> {
  const params = new URLSearchParams();
  if (filters.product_id) params.set("product_id", filters.product_id);
  if (filters.status) params.set("status", filters.status);
  if (filters.utm_source) params.set("utm_source", filters.utm_source);
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  const qs = params.toString();
  const path = `/admin/leads/export${qs ? "?" + qs : ""}`;

  const token = getToken();
  const response = await fetch(`${API_URL}${path}`, {
    method: "GET",
    credentials: "include",
    headers: {
      Accept: "text/csv",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!response.ok) {
    if (response.status === 401) {
      clearToken();
      if (typeof window !== "undefined") window.location.href = "/login";
      throw new Error("Sessão expirada");
    }
    throw new Error(`Falha ao exportar leads (${response.status})`);
  }

  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = `leads-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(downloadUrl);
}


// ── ChatNexo Agents ─────────────────────────────────────────────
export interface AgentItem {
  id: string;
  name: string;
  api_key_masked: string;
  is_active: boolean;
  created_at: string;
}

export interface CreateAgentInput {
  name: string;
  api_key: string;
}

export interface UpdateAgentInput {
  name?: string;
  api_key?: string;
  is_active?: boolean;
}

export async function listChatnexoAgents(): Promise<AgentItem[]> {
  return apiFetch<AgentItem[]>("/admin/chatnexo-agents");
}

export async function createChatnexoAgent(dto: CreateAgentInput): Promise<AgentItem> {
  return apiFetch<AgentItem>("/admin/chatnexo-agents", {
    method: "POST",
    body: JSON.stringify(dto),
  });
}

export async function updateChatnexoAgent(id: string, dto: UpdateAgentInput): Promise<AgentItem> {
  return apiFetch<AgentItem>(`/admin/chatnexo-agents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(dto),
  });
}

export async function deleteChatnexoAgent(id: string): Promise<void> {
  return apiFetch<void>(`/admin/chatnexo-agents/${id}`, { method: "DELETE" });
}

export function uploadTemplateMedia(
  file: File,
  kind: "IMAGE" | "VIDEO" | "DOCUMENT",
  onProgress?: (pct: number) => void,
): Promise<UploadMediaResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const fd = new FormData();
    fd.append("file", file);
    fd.append("kind", kind);

    const url = `${API_URL}/admin/meta-templates/upload-media`;
    xhr.open("POST", url);

    // Replicate Bearer token auth used by apiFetch
    const token = getToken();
    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }
    xhr.withCredentials = true;

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as UploadMediaResponse);
        } catch {
          reject(new Error("Invalid JSON response"));
        }
      } else {
        let detail: string = xhr.responseText;
        try {
          const parsed = JSON.parse(xhr.responseText) as Record<string, unknown>;
          detail =
            (parsed?.detail as { code?: string } | string | undefined) != null
              ? typeof parsed.detail === "string"
                ? parsed.detail
                : ((parsed.detail as { code?: string })?.code ?? JSON.stringify(parsed.detail))
              : JSON.stringify(parsed);
        } catch {
          /* keep raw */
        }
        reject(new Error(detail));
      }
    };
    xhr.onerror = () => reject(new Error("Network error"));
    xhr.send(fd);
  });
}
