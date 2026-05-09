from __future__ import annotations

import pytest

from shared.application.use_cases.meta_templates.validators import (
    MEDIA_LIMITS,
    validate_media_file,
    validate_template_payload,
)


def _payload(**overrides):
    base = {
        "name": "boas_vindas",
        "category": "UTILITY",
        "language": "pt_BR",
        "components": [
            {"type": "BODY", "text": "Olá {{1}}!", "example": {"body_text": [["Fabio"]]}},
        ],
    }
    base.update(overrides)
    return base


def test_payload_minimo_valido():
    assert validate_template_payload(_payload()) == []


@pytest.mark.parametrize("name", ["AB", "Has Caps", "with-dash", "ç", ""])
def test_name_invalid(name):
    errors = validate_template_payload(_payload(name=name))
    assert any(e.code == "NAME_INVALID" for e in errors)


def test_name_valid_snake_case():
    assert validate_template_payload(_payload(name="meu_template_123")) == []


@pytest.mark.parametrize("category", ["AUTHENTICATION", "OTHER", ""])
def test_category_invalid(category):
    errors = validate_template_payload(_payload(category=category))
    assert any(e.code == "CATEGORY_INVALID" for e in errors)


def test_category_only_marketing_or_utility():
    assert validate_template_payload(_payload(category="MARKETING")) == []
    assert validate_template_payload(_payload(category="UTILITY")) == []


def test_body_required():
    errors = validate_template_payload(_payload(components=[]))
    assert any(e.code == "BODY_REQUIRED" for e in errors)


def test_body_too_long():
    long_body = "a" * 1025
    errors = validate_template_payload(
        _payload(
            components=[
                {"type": "BODY", "text": long_body},
            ]
        )
    )
    assert any(e.code == "BODY_TEXT_TOO_LONG" for e in errors)


def test_body_variables_must_be_sequential():
    errors = validate_template_payload(
        _payload(
            components=[
                {
                    "type": "BODY",
                    "text": "Olá {{1}} e {{3}}",
                    "example": {"body_text": [["a", "b"]]},
                },
            ]
        )
    )
    assert any(e.code == "VARIABLES_NOT_SEQUENTIAL" for e in errors)


def test_body_variables_no_adjacent():
    errors = validate_template_payload(
        _payload(
            components=[
                {"type": "BODY", "text": "Olá {{1}}{{2}}", "example": {"body_text": [["a", "b"]]}},
            ]
        )
    )
    assert any(e.code == "VARIABLES_ADJACENT" for e in errors)


def test_body_variable_missing_example():
    errors = validate_template_payload(
        _payload(
            components=[
                {"type": "BODY", "text": "Olá {{1}}"},
            ]
        )
    )
    assert any(e.code == "VARIABLE_MISSING_EXAMPLE" for e in errors)


def test_header_text_too_long():
    errors = validate_template_payload(
        _payload(
            components=[
                {"type": "HEADER", "format": "TEXT", "text": "x" * 61},
                {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
            ]
        )
    )
    assert any(e.code == "HEADER_TEXT_TOO_LONG" for e in errors)


def test_header_text_max_one_variable():
    errors = validate_template_payload(
        _payload(
            components=[
                {
                    "type": "HEADER",
                    "format": "TEXT",
                    "text": "{{1}} e {{2}}",
                    "example": {"header_text": ["a", "b"]},
                },
                {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
            ]
        )
    )
    assert any(e.code == "HEADER_TOO_MANY_VARIABLES" for e in errors)


def test_footer_too_long():
    errors = validate_template_payload(
        _payload(
            components=[
                {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
                {"type": "FOOTER", "text": "x" * 61},
            ]
        )
    )
    assert any(e.code == "FOOTER_TOO_LONG" for e in errors)


def test_footer_no_variables():
    errors = validate_template_payload(
        _payload(
            components=[
                {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
                {"type": "FOOTER", "text": "Vai {{1}}"},
            ]
        )
    )
    assert any(e.code == "FOOTER_HAS_VARIABLES" for e in errors)


def test_button_label_too_long():
    errors = validate_template_payload(
        _payload(
            components=[
                {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
                {
                    "type": "BUTTONS",
                    "buttons": [
                        {"type": "QUICK_REPLY", "text": "x" * 26},
                    ],
                },
            ]
        )
    )
    assert any(e.code == "BUTTON_LABEL_TOO_LONG" for e in errors)


def test_button_url_invalid():
    errors = validate_template_payload(
        _payload(
            components=[
                {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
                {
                    "type": "BUTTONS",
                    "buttons": [
                        {"type": "URL", "text": "Ir", "url": "not-a-url"},
                    ],
                },
            ]
        )
    )
    assert any(e.code == "BUTTON_URL_INVALID" for e in errors)


def test_button_phone_e164_required():
    errors = validate_template_payload(
        _payload(
            components=[
                {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
                {
                    "type": "BUTTONS",
                    "buttons": [
                        {"type": "PHONE_NUMBER", "text": "Liga", "phone_number": "11912345678"},
                    ],
                },
            ]
        )
    )
    assert any(e.code == "BUTTON_PHONE_INVALID" for e in errors)


def test_buttons_too_many_total():
    errors = validate_template_payload(
        _payload(
            components=[
                {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
                {
                    "type": "BUTTONS",
                    "buttons": [{"type": "QUICK_REPLY", "text": f"q{i}"} for i in range(11)],
                },
            ]
        )
    )
    assert any(e.code == "BUTTONS_TOO_MANY" for e in errors)


def test_buttons_too_many_cta():
    errors = validate_template_payload(
        _payload(
            components=[
                {"type": "BODY", "text": "ok", "example": {"body_text": [[]]}},
                {
                    "type": "BUTTONS",
                    "buttons": [
                        {"type": "URL", "text": "a", "url": "https://a.com"},
                        {"type": "URL", "text": "b", "url": "https://b.com"},
                        {"type": "URL", "text": "c", "url": "https://c.com"},
                    ],
                },
            ]
        )
    )
    assert any(e.code == "BUTTONS_TOO_MANY_CTA" for e in errors)


def test_validate_media_file_size():
    err = validate_media_file(kind="IMAGE", size=10 * 1024 * 1024, mime="image/jpeg")
    assert err is not None
    assert err.code == "MEDIA_SIZE_EXCEEDED"


def test_validate_media_file_mime():
    err = validate_media_file(kind="IMAGE", size=1024, mime="image/gif")
    assert err is not None
    assert err.code == "MEDIA_TYPE_INVALID"


def test_validate_media_file_ok():
    assert validate_media_file(kind="IMAGE", size=1024, mime="image/jpeg") is None


def test_media_limits_constants_match_spec():
    assert MEDIA_LIMITS["IMAGE"]["max_bytes"] == 5 * 1024 * 1024
    assert MEDIA_LIMITS["VIDEO"]["max_bytes"] == 16 * 1024 * 1024
    assert MEDIA_LIMITS["DOCUMENT"]["max_bytes"] == 100 * 1024 * 1024
