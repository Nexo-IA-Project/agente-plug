# tests/unit/domain/test_loja_express_port.py
from __future__ import annotations

from typing import Protocol

import pytest

from nexoia.domain.ports.loja_express_port import LojaExpressPort
from nexoia.infrastructure.loja_express.stub_client import LojaExpressStubClient


def test_loja_express_port_is_protocol():
    """LojaExpressPort must be a Protocol (runtime_checkable)."""
    assert issubclass(LojaExpressPort, Protocol)


def test_stub_satisfies_protocol():
    """LojaExpressStubClient must satisfy the LojaExpressPort protocol."""
    stub = LojaExpressStubClient()
    assert isinstance(stub, LojaExpressPort)


@pytest.mark.asyncio
async def test_stub_is_form_submitted_raises():
    stub = LojaExpressStubClient()
    with pytest.raises(NotImplementedError):
        await stub.is_form_submitted("case-1")


@pytest.mark.asyncio
async def test_stub_get_store_status_raises():
    stub = LojaExpressStubClient()
    with pytest.raises(NotImplementedError):
        await stub.get_store_status("case-1")
