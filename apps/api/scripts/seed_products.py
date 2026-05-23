"""Popula a tabela `products` com os 7 produtos oficiais da G2 Educação.

Idempotente (`INSERT ... ON CONFLICT DO NOTHING` pela constraint
`uq_products_account_hubla`). Pode ser rodado sempre que precisar restaurar
o catálogo base — útil em ambientes locais novos ou após reset do DB.

Uso:
    uv run python -m scripts.seed_products
    uv run python -m scripts.seed_products --account-id <uuid>

Sem `--account-id`, pega o primeiro account criado (comportamento single-tenant).
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from uuid import UUID

from sqlalchemy import text

from shared.adapters.db.session import get_sessionmaker

_PRODUCTS: list[tuple[str, str]] = [
    ("MVS | Máquina de Vendas: Shopee", "QaIlGtff9tlU94JjDKSq"),
    ("Comunidade Maverick Pro", "DVdGuF8RwSKYDYnJvao1"),
    ("LE | Loja Express", "mHfbJg3hAf0juI6IXJ0F"),
    ("Escola de Anúncios: Shopee", "XqPpW3fbh5VfW4XpzlwF"),
    ("MVML | Máquina de Vendas: Mercado Livre", "YTZi3Zr9b2ekuXuL3DG2"),
    ("Programa de Aceleração & Escala", "oy7iKOItf8lE6R27k869"),
    ("Black Marketplace Vitalício", "wiK0PWNsy6pgKta7STSL"),
]


async def seed(account_id: UUID | None = None) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as s:
        if account_id is None:
            row = (
                await s.execute(text("SELECT id FROM accounts ORDER BY created_at LIMIT 1"))
            ).fetchone()
            if row is None:
                print("Nenhuma account encontrada. Rode as migrations primeiro.")
                return
            account_id = row[0]
            print(f"Usando account {account_id} (primeira encontrada)")

        inserted = 0
        for name, hubla_id in _PRODUCTS:
            result = await s.execute(
                text(
                    "INSERT INTO products "
                    "(id, account_id, name, hubla_id, is_active, created_at, updated_at) "
                    "VALUES (:id, :account_id, :name, :hubla_id, true, NOW(), NOW()) "
                    "ON CONFLICT ON CONSTRAINT uq_products_account_hubla DO NOTHING"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "account_id": str(account_id),
                    "name": name,
                    "hubla_id": hubla_id,
                },
            )
            if result.rowcount > 0:
                inserted += 1
                print(f"  + {name} ({hubla_id})")
            else:
                print(f"  · {name} (já existia)")

        await s.commit()
        print(f"\nSeed concluído: {inserted} novo(s), {len(_PRODUCTS) - inserted} já existiam.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--account-id",
        type=str,
        default=None,
        help="UUID do account (default: primeiro account encontrado)",
    )
    args = parser.parse_args()
    account_uuid = UUID(args.account_id) if args.account_id else None
    asyncio.run(seed(account_uuid))


if __name__ == "__main__":
    main()
