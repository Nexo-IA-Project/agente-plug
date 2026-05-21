// apps/web/src/lib/api.ts

import type {
  KbDocumentListResponse,
  UploadDocumentResponse,
} from "@/types/api";
import { getToken } from "@/lib/auth";
import type { AccountSettings, AccountSettingsPatch } from "@/features/settings/types";
import type {
  CreateFlowInput,
  CreateStepInput,
  FollowupFlow,
  FollowupStep,
  ReorderItem,
  UpdateFlowInput,
  UpdateStepInput,
} from "@/features/followup/types";
import type {
  Course,
  CreateCourseInput,
  UpdateCourseInput,
} from "@/features/courses/types";

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

// ─── Follow-up Flows ─────────────────────────────────────────────────────────

export async function listFollowupFlows(): Promise<FollowupFlow[]> {
  return apiFetch<FollowupFlow[]>("/admin/followup/flows");
}

export async function createFollowupFlow(dto: CreateFlowInput): Promise<FollowupFlow> {
  return apiFetch<FollowupFlow>("/admin/followup/flows", {
    method: "POST",
    body: JSON.stringify(dto),
  });
}

export async function updateFollowupFlow(id: string, dto: UpdateFlowInput): Promise<FollowupFlow> {
  return apiFetch<FollowupFlow>(`/admin/followup/flows/${id}`, {
    method: "PUT",
    body: JSON.stringify(dto),
  });
}

export async function deleteFollowupFlow(id: string): Promise<void> {
  return apiFetch<void>(`/admin/followup/flows/${id}`, { method: "DELETE" });
}

export async function listFollowupSteps(flowId: string): Promise<FollowupStep[]> {
  return apiFetch<FollowupStep[]>(`/admin/followup/flows/${flowId}/steps`);
}

export async function createFollowupStep(
  flowId: string,
  dto: CreateStepInput
): Promise<FollowupStep> {
  return apiFetch<FollowupStep>(`/admin/followup/flows/${flowId}/steps`, {
    method: "POST",
    body: JSON.stringify(dto),
  });
}

export async function updateFollowupStep(
  flowId: string,
  stepId: string,
  dto: UpdateStepInput
): Promise<FollowupStep> {
  return apiFetch<FollowupStep>(`/admin/followup/flows/${flowId}/steps/${stepId}`, {
    method: "PUT",
    body: JSON.stringify(dto),
  });
}

export async function deleteFollowupStep(flowId: string, stepId: string): Promise<void> {
  return apiFetch<void>(`/admin/followup/flows/${flowId}/steps/${stepId}`, { method: "DELETE" });
}

export async function reorderFollowupSteps(
  flowId: string,
  items: ReorderItem[]
): Promise<void> {
  return apiFetch<void>(`/admin/followup/flows/${flowId}/steps/reorder`, {
    method: "PATCH",
    body: JSON.stringify({ steps: items }),
  });
}


// ─── Courses ─────────────────────────────────────────────────────────────────

export async function listCourses(): Promise<Course[]> {
  return apiFetch<Course[]>("/admin/courses");
}

export async function createCourse(input: CreateCourseInput): Promise<Course> {
  return apiFetch<Course>("/admin/courses", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateCourse(
  id: string,
  input: UpdateCourseInput,
): Promise<Course> {
  return apiFetch<Course>(`/admin/courses/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function deleteCourse(id: string): Promise<void> {
  return apiFetch<void>(`/admin/courses/${id}`, { method: "DELETE" });
}


// ─── Meta Templates ──────────────────────────────────────────────────────────

import type { CreateTemplateDto, MetaTemplate } from "@/features/templates/types";

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
