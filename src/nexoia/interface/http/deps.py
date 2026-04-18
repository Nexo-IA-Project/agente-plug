from __future__ import annotations

from fastapi import Header, HTTPException, status

from nexoia.config.settings import get_settings


def require_chatnexo_key(x_api_key: str = Header(default="")) -> None:
    if x_api_key != get_settings().chatnexo_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")


def require_hubla_token(x_hubla_token: str = Header(default="")) -> None:
    if x_hubla_token != get_settings().hubla_webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid hubla token")


def require_admin_key(x_api_key: str = Header(default="")) -> None:
    if x_api_key != get_settings().admin_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin key")
