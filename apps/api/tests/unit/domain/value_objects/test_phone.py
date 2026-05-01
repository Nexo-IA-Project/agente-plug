import pytest

from shared.domain.errors import InvalidPhoneError
from shared.domain.value_objects.phone import Phone


def test_phone_normalizes_br_number_without_country_code() -> None:
    assert Phone.parse("11987654321").e164 == "+5511987654321"


def test_phone_keeps_country_code_if_present() -> None:
    assert Phone.parse("5511987654321").e164 == "+5511987654321"
    assert Phone.parse("+5511987654321").e164 == "+5511987654321"


def test_phone_strips_non_digits() -> None:
    assert Phone.parse("(11) 98765-4321").e164 == "+5511987654321"


def test_phone_rejects_invalid() -> None:
    with pytest.raises(InvalidPhoneError):
        Phone.parse("abc")
    with pytest.raises(InvalidPhoneError):
        Phone.parse("123")
