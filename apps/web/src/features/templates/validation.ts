import type { MediaKind, TemplateButton } from "./types";

export const NAME_REGEX = /^[a-z0-9_]{3,512}$/;
export const PHONE_E164_REGEX = /^\+\d{8,15}$/;
export const ADJACENT_VAR_REGEX = /\}\}\{\{/;

export const ALLOWED_CATEGORIES = ["MARKETING", "UTILITY"] as const;
export const ALLOWED_LANGUAGES = ["pt_BR", "en_US"] as const;
export const ALLOWED_HEADER_FORMATS = ["TEXT", "IMAGE", "VIDEO", "DOCUMENT"] as const;

export const HEADER_TEXT_MAX = 60;
export const BODY_TEXT_MAX = 1024;
export const FOOTER_MAX = 60;
export const BUTTON_LABEL_MAX = 25;
export const BUTTON_URL_MAX = 2000;
export const BUTTONS_TOTAL_MAX = 10;
export const CTA_BUTTONS_MAX = 2;

export const MEDIA_LIMITS: Record<MediaKind, { mimes: string[]; maxBytes: number }> = {
  IMAGE: { mimes: ["image/jpeg", "image/png"], maxBytes: 5 * 1024 * 1024 },
  VIDEO: { mimes: ["video/mp4"], maxBytes: 16 * 1024 * 1024 },
  DOCUMENT: { mimes: ["application/pdf"], maxBytes: 100 * 1024 * 1024 },
};

export interface ValidationError {
  field: string;
  code: string;
  message: string;
}

export function detectVariables(text: string): number[] {
  const re = /\{\{(\d+)\}\}/g;
  const out: number[] = [];
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    out.push(parseInt(match[1], 10));
  }
  return out;
}

export function validateName(name: string): ValidationError | null {
  if (!NAME_REGEX.test(name)) {
    return {
      field: "name",
      code: "NAME_INVALID",
      message: "Use a-z, 0-9, _ — entre 3 e 512 caracteres",
    };
  }
  return null;
}

export function validateBody(text: string, examples: string[]): ValidationError[] {
  const errors: ValidationError[] = [];
  if (!text.trim()) {
    errors.push({ field: "body", code: "BODY_REQUIRED", message: "Body é obrigatório" });
  }
  if (text.length > BODY_TEXT_MAX) {
    errors.push({
      field: "body",
      code: "BODY_TEXT_TOO_LONG",
      message: `Body excede ${BODY_TEXT_MAX} caracteres`,
    });
  }
  if (ADJACENT_VAR_REGEX.test(text)) {
    errors.push({
      field: "body",
      code: "VARIABLES_ADJACENT",
      message: "Variáveis não podem ser adjacentes",
    });
  }
  const vars = detectVariables(text);
  const unique = Array.from(new Set(vars)).sort((a, b) => a - b);
  const expected = unique.map((_, i) => i + 1);
  if (JSON.stringify(unique) !== JSON.stringify(expected)) {
    errors.push({
      field: "body",
      code: "VARIABLES_NOT_SEQUENTIAL",
      message: "Variáveis devem ser sequenciais a partir de {{1}}",
    });
  }
  if (unique.length > 0 && (examples.length < unique.length || examples.some((e) => !e.trim()))) {
    errors.push({
      field: "body.examples",
      code: "VARIABLE_MISSING_EXAMPLE",
      message: "Cada variável precisa de um exemplo",
    });
  }
  return errors;
}

export function validateHeader(format: string | undefined, text: string): ValidationError[] {
  const errors: ValidationError[] = [];
  if (format === "TEXT") {
    if (text.length > HEADER_TEXT_MAX) {
      errors.push({
        field: "header.text",
        code: "HEADER_TEXT_TOO_LONG",
        message: `Header excede ${HEADER_TEXT_MAX} caracteres`,
      });
    }
    const vars = detectVariables(text);
    if (new Set(vars).size > 1) {
      errors.push({
        field: "header.text",
        code: "HEADER_TOO_MANY_VARIABLES",
        message: "Header text aceita no máximo 1 variável",
      });
    }
  }
  return errors;
}

export function validateFooter(text: string): ValidationError[] {
  const errors: ValidationError[] = [];
  if (text.length > FOOTER_MAX) {
    errors.push({
      field: "footer",
      code: "FOOTER_TOO_LONG",
      message: `Footer excede ${FOOTER_MAX} caracteres`,
    });
  }
  if (detectVariables(text).length > 0) {
    errors.push({
      field: "footer",
      code: "FOOTER_HAS_VARIABLES",
      message: "Footer não pode conter variáveis",
    });
  }
  return errors;
}

export function validateButtons(buttons: TemplateButton[]): ValidationError[] {
  const errors: ValidationError[] = [];
  if (buttons.length > BUTTONS_TOTAL_MAX) {
    errors.push({
      field: "buttons",
      code: "BUTTONS_TOO_MANY",
      message: `Máximo ${BUTTONS_TOTAL_MAX} botões`,
    });
  }
  const cta = buttons.filter((b) => b.type === "URL" || b.type === "PHONE_NUMBER").length;
  if (cta > CTA_BUTTONS_MAX) {
    errors.push({
      field: "buttons",
      code: "BUTTONS_TOO_MANY_CTA",
      message: `Máximo ${CTA_BUTTONS_MAX} botões CTA (URL/PHONE)`,
    });
  }
  buttons.forEach((b, i) => {
    if (b.text.length > BUTTON_LABEL_MAX) {
      errors.push({
        field: `buttons[${i}].text`,
        code: "BUTTON_LABEL_TOO_LONG",
        message: `Label excede ${BUTTON_LABEL_MAX} chars`,
      });
    }
    if (b.type === "URL") {
      const url = b.url || "";
      if (url.length > BUTTON_URL_MAX) {
        errors.push({
          field: `buttons[${i}].url`,
          code: "BUTTON_URL_TOO_LONG",
          message: `URL excede ${BUTTON_URL_MAX} chars`,
        });
      }
      try {
        const u = new URL(url);
        if (!["http:", "https:"].includes(u.protocol)) throw new Error();
      } catch {
        errors.push({
          field: `buttons[${i}].url`,
          code: "BUTTON_URL_INVALID",
          message: "URL inválida",
        });
      }
    }
    if (b.type === "PHONE_NUMBER") {
      if (!PHONE_E164_REGEX.test(b.phone_number || "")) {
        errors.push({
          field: `buttons[${i}].phone_number`,
          code: "BUTTON_PHONE_INVALID",
          message: "Use formato E.164 (ex.: +5511999999999)",
        });
      }
    }
  });
  return errors;
}

export function validateMediaFile(file: File, kind: MediaKind): ValidationError | null {
  const limits = MEDIA_LIMITS[kind];
  if (!limits.mimes.includes(file.type)) {
    return {
      field: "media.mime",
      code: "MEDIA_TYPE_INVALID",
      message: `Tipo inválido. Permitido: ${limits.mimes.join(", ")}`,
    };
  }
  if (file.size > limits.maxBytes) {
    const mb = limits.maxBytes / (1024 * 1024);
    return {
      field: "media.size",
      code: "MEDIA_SIZE_EXCEEDED",
      message: `Arquivo excede ${mb}MB`,
    };
  }
  return null;
}
