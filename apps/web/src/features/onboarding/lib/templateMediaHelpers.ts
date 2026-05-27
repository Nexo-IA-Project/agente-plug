import type { MetaTemplate } from "@/features/templates/types";

export type MediaKind = "IMAGE" | "VIDEO" | "DOCUMENT";

/**
 * Verifica se o template tem header de mídia (IMAGE/VIDEO/DOCUMENT).
 */
export function hasMedia(template: MetaTemplate | null | undefined): boolean {
  if (!template) return false;
  const header = template.components.find((c) => c.type === "HEADER");
  if (!header) return false;
  return (
    header.format === "IMAGE" ||
    header.format === "VIDEO" ||
    header.format === "DOCUMENT"
  );
}

/**
 * Retorna a URL pública da mídia (servida pelo nosso /public/media/{id}).
 * `null` se template não tem mídia.
 */
export function getMediaUrl(
  template: MetaTemplate | null | undefined,
): string | null {
  if (!template) return null;
  return template.media_url ?? null;
}

/**
 * Retorna o kind da mídia (IMAGE/VIDEO/DOCUMENT) — útil pra escolher o
 * componente de render (img/video/link).
 */
export function getMediaKind(
  template: MetaTemplate | null | undefined,
): MediaKind | null {
  if (!template) return null;
  const header = template.components.find((c) => c.type === "HEADER");
  if (!header) return null;
  if (
    header.format === "IMAGE" ||
    header.format === "VIDEO" ||
    header.format === "DOCUMENT"
  ) {
    return header.format as MediaKind;
  }
  return null;
}
