from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt as _bcrypt
from jose import jwt as jose_jwt


def create_access_token(data: dict, secret: str, expire_minutes: int) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=expire_minutes)
    to_encode["exp"] = expire
    return jose_jwt.encode(to_encode, secret, algorithm="HS256")


def verify_token(token: str, secret: str) -> dict:
    return jose_jwt.decode(token, secret, algorithms=["HS256"])


def hash_password(password: str) -> str:
    salt = _bcrypt.gensalt()
    return _bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())
