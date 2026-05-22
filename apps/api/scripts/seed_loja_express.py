"""Cria (idempotentemente) o produto "Loja Express" e um flow padrao com 5 steps.

Os steps correspondem aos delays historicos (D+0, D+1, D+3, D+5, D+7) da capability
descontinuada de Loja Express.

Uso:
  uv run python -m scripts.seed_loja_express <account_id> [--templates t0,t1,t3,t5,t7]
"""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from shared.adapters.db.repositories.followup_flow_repo import FollowupFlowRepository
from shared.adapters.db.repositories.product_repo import SqlProductRepository
from shared.adapters.db.session import get_sessionmaker

DEFAULT_TEMPLATES: list[tuple[str, int]] = [
    ("loja_express_d0", 0),
    ("loja_express_d1", 24),
    ("loja_express_d3", 72),
    ("loja_express_d5", 120),
    ("loja_express_d7", 168),
]

DEFAULT_DELAYS: list[int] = [0, 24, 72, 120, 168]


async def seed(account_id: UUID, templates: list[tuple[str, int]]) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        product_repo = SqlProductRepository(session)
        flow_repo = FollowupFlowRepository(session)

        existing = await product_repo.find_active_by_hubla_id(account_id, "loja-express")
        if existing is None:
            product = await product_repo.create(
                account_id=account_id,
                name="Loja Express",
                hubla_id="loja-express",
            )
            print(f"Created product {product.id} (Loja Express)")
        else:
            product = existing
            print(f"Product already exists: {product.id} (Loja Express) - skipping creation")

        flows = await flow_repo.list_active_by_product(product.id)
        if flows:
            print("Flow already exists for product; skipping seed of steps")
            await session.commit()
            return

        flow = await flow_repo.create_flow(
            account_id=account_id,
            product_id=product.id,
            name="Loja Express - sequencia padrao",
            is_active=True,
        )
        for i, (template_name, hours) in enumerate(templates):
            await flow_repo.create_step(
                flow_id=flow.id,
                position=i,
                delay_from_purchase_hours=hours,
                meta_template_name=template_name,
                template_variables={"1": {"source": "customer_name"}},
                message_text=None,
            )
        await session.commit()
        print(f"Seeded flow {flow.id} with {len(templates)} steps")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("account_id", type=str, help="UUID da account")
    parser.add_argument(
        "--templates",
        type=str,
        default=None,
        help="CSV de nomes de templates (default: loja_express_d0..d7)",
    )
    args = parser.parse_args()

    if args.templates:
        names = [n.strip() for n in args.templates.split(",")]
        if len(names) != len(DEFAULT_DELAYS):
            raise SystemExit(
                f"--templates must have {len(DEFAULT_DELAYS)} entries (got {len(names)})"
            )
        templates = list(zip(names, DEFAULT_DELAYS, strict=True))
    else:
        templates = DEFAULT_TEMPLATES

    asyncio.run(seed(UUID(args.account_id), templates))


if __name__ == "__main__":
    main()
