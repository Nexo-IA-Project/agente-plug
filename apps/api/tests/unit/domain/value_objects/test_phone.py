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
    assert Phone.parse("+55 11 9 8765-4321").e164 == "+5511987654321"


def test_phone_accepts_landline_without_9() -> None:
    # Fixo BR: 10 dígitos (DDD + 8) sem código país
    assert Phone.parse("1133334444").e164 == "+551133334444"
    # Fixo BR com código país: 12 dígitos
    assert Phone.parse("551133334444").e164 == "+551133334444"


def test_phone_rejects_invalid() -> None:
    with pytest.raises(InvalidPhoneError):
        Phone.parse("abc")
    with pytest.raises(InvalidPhoneError):
        Phone.parse("123")


def test_phone_rejects_empty_and_none() -> None:
    # Telefone vazio é obrigatório — não pode passar
    with pytest.raises(InvalidPhoneError, match="required"):
        Phone.parse("")
    with pytest.raises(InvalidPhoneError, match="required"):
        Phone.parse("   ")
    with pytest.raises(InvalidPhoneError, match="required"):
        Phone.parse(None)


def test_phone_rejects_no_digits_after_strip() -> None:
    with pytest.raises(InvalidPhoneError, match="no digits"):
        Phone.parse("(--)")


def test_phone_rejects_wrong_digit_count() -> None:
    # 14 dígitos: muito longo
    with pytest.raises(InvalidPhoneError, match="10-13 digits"):
        Phone.parse("12345678901234")
    # 9 dígitos: muito curto
    with pytest.raises(InvalidPhoneError, match="10-13 digits"):
        Phone.parse("123456789")


def test_phone_rejects_12_13_digits_without_br_prefix() -> None:
    # 12 dígitos não começando com 55
    with pytest.raises(InvalidPhoneError, match="country code 55"):
        Phone.parse("121198765432")
    # 13 dígitos não começando com 55
    with pytest.raises(InvalidPhoneError, match="country code 55"):
        Phone.parse("1234567890123")


def test_phone_rejects_invalid_ddd() -> None:
    # DDD 10 não existe no Brasil (começa em 11)
    with pytest.raises(InvalidPhoneError, match="DDD"):
        Phone.parse("10987654321")
    # DDD 01 não existe
    with pytest.raises(InvalidPhoneError, match="DDD"):
        Phone.parse("01987654321")
