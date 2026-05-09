from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

NAME_REGEX = re.compile(r"^[a-z0-9_]{3,512}$")
PHONE_E164_REGEX = re.compile(r"^\+\d{8,15}$")
VARIABLE_REGEX = re.compile(r"\{\{(\d+)\}\}")
ADJACENT_VAR_REGEX = re.compile(r"\}\}\{\{")

ALLOWED_CATEGORIES = {"MARKETING", "UTILITY"}
ALLOWED_LANGUAGES = {"pt_BR", "en_US"}
ALLOWED_HEADER_FORMATS = {"TEXT", "IMAGE", "VIDEO", "DOCUMENT"}

HEADER_TEXT_MAX = 60
BODY_TEXT_MAX = 1024
FOOTER_MAX = 60
BUTTON_LABEL_MAX = 25
BUTTON_URL_MAX = 2000
BUTTONS_TOTAL_MAX = 10
CTA_BUTTONS_MAX = 2

MEDIA_LIMITS: dict[str, dict[str, Any]] = {
    "IMAGE": {"mimes": ["image/jpeg", "image/png"], "max_bytes": 5 * 1024 * 1024},
    "VIDEO": {"mimes": ["video/mp4"], "max_bytes": 16 * 1024 * 1024},
    "DOCUMENT": {"mimes": ["application/pdf"], "max_bytes": 100 * 1024 * 1024},
}


@dataclass(frozen=True)
class ValidationError:
    field: str
    code: str
    message: str


def _err(field: str, code: str, message: str) -> ValidationError:
    return ValidationError(field=field, code=code, message=message)


def _detect_variables(text: str) -> list[int]:
    return [int(m) for m in VARIABLE_REGEX.findall(text)]


def _validate_body(idx: int, c: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    text = c.get("text") or ""
    if len(text) > BODY_TEXT_MAX:
        errors.append(
            _err(
                f"components[{idx}].text",
                "BODY_TEXT_TOO_LONG",
                f"Body excede {BODY_TEXT_MAX} caracteres",
            )
        )
    if not text.strip():
        errors.append(_err(f"components[{idx}].text", "BODY_REQUIRED", "Body é obrigatório"))
    if ADJACENT_VAR_REGEX.search(text):
        errors.append(
            _err(
                f"components[{idx}].text",
                "VARIABLES_ADJACENT",
                "Variáveis não podem ser adjacentes (ex.: {{1}}{{2}})",
            )
        )
    vars_found = _detect_variables(text)
    if vars_found:
        unique = sorted(set(vars_found))
        if unique != list(range(1, len(unique) + 1)):
            errors.append(
                _err(
                    f"components[{idx}].text",
                    "VARIABLES_NOT_SEQUENTIAL",
                    "Variáveis devem ser sequenciais a partir de {{1}}",
                )
            )
        examples = ((c.get("example") or {}).get("body_text") or [[]])[0]
        if len(examples) < len(unique):
            errors.append(
                _err(
                    f"components[{idx}].example",
                    "VARIABLE_MISSING_EXAMPLE",
                    "Cada variável precisa de um exemplo em example.body_text",
                )
            )
    return errors


def _validate_header(idx: int, c: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    fmt = c.get("format")
    if fmt not in ALLOWED_HEADER_FORMATS:
        errors.append(
            _err(
                f"components[{idx}].format",
                "HEADER_FORMAT_INVALID",
                f"Header format inválido (esperado um de {sorted(ALLOWED_HEADER_FORMATS)})",
            )
        )
        return errors
    if fmt == "TEXT":
        text = c.get("text") or ""
        if len(text) > HEADER_TEXT_MAX:
            errors.append(
                _err(
                    f"components[{idx}].text",
                    "HEADER_TEXT_TOO_LONG",
                    f"Header excede {HEADER_TEXT_MAX} caracteres",
                )
            )
        vars_found = _detect_variables(text)
        if len(set(vars_found)) > 1:
            errors.append(
                _err(
                    f"components[{idx}].text",
                    "HEADER_TOO_MANY_VARIABLES",
                    "Header text aceita no máximo 1 variável",
                )
            )
    return errors


def _validate_footer(idx: int, c: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    text = c.get("text") or ""
    if len(text) > FOOTER_MAX:
        errors.append(
            _err(
                f"components[{idx}].text",
                "FOOTER_TOO_LONG",
                f"Footer excede {FOOTER_MAX} caracteres",
            )
        )
    if VARIABLE_REGEX.search(text):
        errors.append(
            _err(
                f"components[{idx}].text",
                "FOOTER_HAS_VARIABLES",
                "Footer não pode conter variáveis",
            )
        )
    return errors


def _validate_buttons(idx: int, c: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    buttons = c.get("buttons") or []
    if len(buttons) > BUTTONS_TOTAL_MAX:
        errors.append(
            _err(
                f"components[{idx}].buttons",
                "BUTTONS_TOO_MANY",
                f"Total de botões excede {BUTTONS_TOTAL_MAX}",
            )
        )
    cta_count = sum(1 for b in buttons if b.get("type") in {"URL", "PHONE_NUMBER"})
    if cta_count > CTA_BUTTONS_MAX:
        errors.append(
            _err(
                f"components[{idx}].buttons",
                "BUTTONS_TOO_MANY_CTA",
                f"Botões CTA (URL/PHONE) excedem {CTA_BUTTONS_MAX}",
            )
        )
    for j, b in enumerate(buttons):
        label = b.get("text") or ""
        if len(label) > BUTTON_LABEL_MAX:
            errors.append(
                _err(
                    f"components[{idx}].buttons[{j}].text",
                    "BUTTON_LABEL_TOO_LONG",
                    f"Label do botão excede {BUTTON_LABEL_MAX} caracteres",
                )
            )
        if b.get("type") == "URL":
            url = b.get("url") or ""
            if len(url) > BUTTON_URL_MAX:
                errors.append(
                    _err(
                        f"components[{idx}].buttons[{j}].url",
                        "BUTTON_URL_TOO_LONG",
                        f"URL do botão excede {BUTTON_URL_MAX} caracteres",
                    )
                )
            try:
                parsed = urlparse(url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ValueError
            except Exception:
                errors.append(
                    _err(
                        f"components[{idx}].buttons[{j}].url",
                        "BUTTON_URL_INVALID",
                        "URL inválida",
                    )
                )
        if b.get("type") == "PHONE_NUMBER":
            phone = b.get("phone_number") or ""
            if not PHONE_E164_REGEX.match(phone):
                errors.append(
                    _err(
                        f"components[{idx}].buttons[{j}].phone_number",
                        "BUTTON_PHONE_INVALID",
                        "Telefone deve estar em E.164 (ex.: +5511999999999)",
                    )
                )
    return errors


def validate_template_payload(payload: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []

    name = payload.get("name") or ""
    if not NAME_REGEX.match(name):
        errors.append(
            _err(
                "name",
                "NAME_INVALID",
                "Nome deve ser snake_case (a-z, 0-9, _) com 3-512 caracteres",
            )
        )

    category = payload.get("category")
    if category not in ALLOWED_CATEGORIES:
        errors.append(
            _err(
                "category",
                "CATEGORY_INVALID",
                f"Categoria deve ser uma de {sorted(ALLOWED_CATEGORIES)}",
            )
        )

    language = payload.get("language")
    if language not in ALLOWED_LANGUAGES:
        errors.append(
            _err(
                "language", "LANGUAGE_INVALID", f"Idioma deve ser um de {sorted(ALLOWED_LANGUAGES)}"
            )
        )

    components = payload.get("components") or []
    has_body = False
    for i, c in enumerate(components):
        ctype = c.get("type")
        if ctype == "HEADER":
            errors.extend(_validate_header(i, c))
        elif ctype == "BODY":
            has_body = True
            errors.extend(_validate_body(i, c))
        elif ctype == "FOOTER":
            errors.extend(_validate_footer(i, c))
        elif ctype == "BUTTONS":
            errors.extend(_validate_buttons(i, c))

    if not has_body:
        errors.append(_err("components", "BODY_REQUIRED", "Body é obrigatório"))

    return errors


def validate_media_file(*, kind: str, size: int, mime: str) -> ValidationError | None:
    limits = MEDIA_LIMITS.get(kind)
    if limits is None:
        return _err(
            "media.kind", "MEDIA_KIND_INVALID", f"Kind deve ser um de {list(MEDIA_LIMITS.keys())}"
        )
    if mime not in limits["mimes"]:
        return _err(
            "media.mime",
            "MEDIA_TYPE_INVALID",
            f"MIME inválido para {kind} (esperado: {limits['mimes']})",
        )
    if size > limits["max_bytes"]:
        max_mb = limits["max_bytes"] // (1024 * 1024)
        return _err("media.size", "MEDIA_SIZE_EXCEEDED", f"Arquivo excede {max_mb}MB para {kind}")
    return None
