#!/usr/bin/env python3
"""Dispara um webhook Hubla simulado para o endpoint local /webhook/purchase.

Uso:
    uv run python scripts/webhook-sim/fire_webhook.py
    uv run python scripts/webhook-sim/fire_webhook.py --phone +5511999999999
    uv run python scripts/webhook-sim/fire_webhook.py --payload hubla_subscription_activated_multi
    uv run python scripts/webhook-sim/fire_webhook.py --url http://staging.example.com

Requer em .env.local:
    HUBLA_WEBHOOK_SECRET=...
    TEST_CONTACT_PHONE=+55...
    TEST_HUBLA_PRODUCT_ID=...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_REPO_ROOT = Path(__file__).parent.parent.parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(_REPO_ROOT / ".env.local", override=True)
    except ImportError:
        pass  # python-dotenv não instalado — variáveis devem estar no ambiente


def _load_payload(name: str) -> dict:
    payloads_dir = Path(__file__).parent / "payloads"
    path = payloads_dir / f"{name}.json"
    if not path.exists():
        available = [p.stem for p in payloads_dir.glob("*.json")]
        print(f"Payload '{name}' não encontrado. Disponíveis: {available}", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())


def _fill_placeholders(payload: dict, *, phone: str, product_id: str, product_id_2: str = "") -> dict:
    text = json.dumps(payload)
    now = datetime.now(UTC)
    text = text.replace("{{PHONE}}", phone)
    text = text.replace("{{HUBLA_PRODUCT_ID_2}}", product_id_2 or product_id)
    text = text.replace("{{HUBLA_PRODUCT_ID}}", product_id)
    text = text.replace("{{SUBSCRIPTION_ID}}", str(uuid4()))
    text = text.replace("{{TIMESTAMP_ISO}}", now.isoformat().replace("+00:00", "Z"))
    return json.loads(text)


def main() -> None:
    _load_dotenv()

    parser = argparse.ArgumentParser(description="Dispara webhook Hubla de teste")
    parser.add_argument("--payload", default="hubla_subscription_activated",
                        help="Nome do arquivo de payload (sem .json)")
    parser.add_argument("--phone", default=os.getenv("TEST_CONTACT_PHONE", ""),
                        help="Telefone do contato (ex: +5511999999999)")
    parser.add_argument("--product-id", default=os.getenv("TEST_HUBLA_PRODUCT_ID", ""),
                        help="ID do produto na Hubla")
    parser.add_argument("--url", default=os.getenv("API_URL", "http://localhost:8000"),
                        help="URL base da API")
    args = parser.parse_args()

    if not args.phone:
        print("Erro: defina TEST_CONTACT_PHONE no .env.local ou use --phone", file=sys.stderr)
        sys.exit(1)
    if not args.product_id:
        print("Erro: defina TEST_HUBLA_PRODUCT_ID no .env.local ou use --product-id", file=sys.stderr)
        sys.exit(1)

    token = os.getenv("HUBLA_WEBHOOK_SECRET", "")
    if not token:
        print("Erro: HUBLA_WEBHOOK_SECRET não encontrado no .env.local", file=sys.stderr)
        sys.exit(1)

    raw_payload = _load_payload(args.payload)
    payload = _fill_placeholders(raw_payload, phone=args.phone, product_id=args.product_id)

    try:
        import httpx
    except ImportError:
        print("Erro: httpx não instalado. Execute: uv add httpx", file=sys.stderr)
        sys.exit(1)

    url = f"{args.url.rstrip('/')}/webhook/purchase"
    print(f"→ POST {url}")
    print(f"  payload: {args.payload} | telefone: {args.phone} | produto: {args.product_id}")

    response = httpx.post(url, json=payload, params={"token": token})
    print(f"  status: {response.status_code}")
    print(f"  body:   {response.text}")

    if response.status_code not in (200, 202):
        sys.exit(1)


if __name__ == "__main__":
    main()
