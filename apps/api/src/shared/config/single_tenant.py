"""Constantes de sistema single-tenant.

Enquanto multi-tenancy não chega, o sistema opera com um único account
identificado por este UUID determinístico (corresponde ao seed inicial).
Ponto único de mudança quando multi-tenant for ativado.
"""
from __future__ import annotations

from uuid import UUID

DEFAULT_ACCOUNT_UUID: UUID = UUID("00000000-0000-0000-0000-000000000001")
