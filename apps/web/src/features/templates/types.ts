export type MediaKind = "IMAGE" | "VIDEO" | "DOCUMENT";
export type TemplateCategory = "MARKETING" | "UTILITY";
export type TemplateStatus = "APPROVED" | "PENDING" | "REJECTED";

export interface TemplateButton {
  type: "QUICK_REPLY" | "URL" | "PHONE_NUMBER";
  text: string;
  url?: string;
  phone_number?: string;
  example?: string[];
}

export interface TemplateComponent {
  type: "HEADER" | "BODY" | "FOOTER" | "BUTTONS";
  format?: "TEXT" | MediaKind;
  text?: string;
  buttons?: TemplateButton[];
  example?: {
    header_text?: string[];
    header_handle?: string[];
    body_text?: string[][];
  };
}

export interface UploadedMedia {
  url: string;
  objectKey: string;
  kind: MediaKind;
  size: number;
  sha256: string;
  fileName: string;
}

export interface MetaTemplate {
  id: string;
  name: string;
  category: TemplateCategory;
  language: string;
  status: TemplateStatus;
  components: TemplateComponent[];
  media_url?: string | null;
  media_kind?: MediaKind | null;
  rejection_reason?: string | null;
  meta_template_id?: string | null;
  created_at: string;
}

export interface CreateTemplateDto {
  name: string;
  category: TemplateCategory;
  language: string;
  components: Record<string, unknown>[];
  media_url?: string | null;
  media_object_key?: string | null;
  media_kind?: MediaKind | null;
}
