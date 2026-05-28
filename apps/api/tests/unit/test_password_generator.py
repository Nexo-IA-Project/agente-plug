from __future__ import annotations

import re

from shared.utils.password_generator import generate_temp_password


def test_password_has_correct_length():
    pwd = generate_temp_password()
    assert len(pwd) == 16


def test_password_has_letter_number_and_symbol():
    pwd = generate_temp_password()
    assert re.search(r"[a-zA-Z]", pwd) is not None
    assert re.search(r"\d", pwd) is not None
    assert re.search(r"[!@#$%^&*+=]", pwd) is not None


def test_passwords_are_unique():
    pwds = {generate_temp_password() for _ in range(50)}
    assert len(pwds) == 50
