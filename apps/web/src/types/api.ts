// apps/web/src/types/api.ts

export interface KbDocument {
  id: string;
  filename: string;
  status: "pending" | "processing" | "ready" | "error";
  chunk_count: number;
  created_at: string;
}

export interface KbDocumentListResponse {
  items: KbDocument[];
  total: number;
}

export interface UploadDocumentResponse {
  id: string;
  filename: string;
  status: string;
}

export interface ApiError {
  detail: string;
}
