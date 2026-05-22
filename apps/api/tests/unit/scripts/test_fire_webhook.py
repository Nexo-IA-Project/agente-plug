from __future__ import annotations

import sys
from pathlib import Path

# Adiciona scripts/webhook-sim ao path para importar fire_webhook
# Path: /home/fabio/www/agente-plug/apps/api/tests/unit/scripts/test_fire_webhook.py
# Target: /home/fabio/www/agente-plug/scripts/webhook-sim/
# Parent dirs: tests(1) -> unit(2) -> scripts(3) -> api(4) -> apps(5) -> agente-plug(root)
repo_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(repo_root / "scripts" / "webhook-sim"))

from fire_webhook import _fill_placeholders, _load_payload  # noqa: E402


def test_fill_placeholders_replaces_phone():
    payload = {"event": {"subscription": {"payer": {"phone": "{{PHONE}}"}}}}
    result = _fill_placeholders(payload, phone="+5511999999999", product_id="prod123")
    assert result["event"]["subscription"]["payer"]["phone"] == "+5511999999999"


def test_fill_placeholders_replaces_product_id():
    payload = {"event": {"product": {"id": "{{HUBLA_PRODUCT_ID}}"}}}
    result = _fill_placeholders(payload, phone="+5511999999999", product_id="abc123")
    assert result["event"]["product"]["id"] == "abc123"


def test_fill_placeholders_subscription_id_is_unique():
    payload = {"event": {"subscription": {"id": "{{SUBSCRIPTION_ID}}"}}}
    result1 = _fill_placeholders(payload, phone="+55", product_id="x")
    result2 = _fill_placeholders(payload, phone="+55", product_id="x")
    assert result1["event"]["subscription"]["id"] != result2["event"]["subscription"]["id"]


def test_fill_placeholders_timestamp_iso_is_valid():
    from datetime import datetime
    payload = {"activatedAt": "{{TIMESTAMP_ISO}}"}
    result = _fill_placeholders(payload, phone="+55", product_id="x")
    dt = datetime.fromisoformat(result["activatedAt"].replace("Z", "+00:00"))
    assert dt is not None


def test_load_payload_returns_dict():
    payload = _load_payload("hubla_subscription_activated")
    assert payload["type"] == "subscription.activated"
    assert "event" in payload


def test_load_payload_multi_returns_two_products():
    payload = _load_payload("hubla_subscription_activated_multi")
    assert len(payload["event"]["products"]) == 2
