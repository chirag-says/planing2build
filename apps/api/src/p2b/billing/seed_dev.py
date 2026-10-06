"""Publish TEST commercial configuration for local development (Slice 3.3). Every version is
marked TEST and says so; production refuses TEST versions, and this command refuses to run
outside local and test environments. These are development values for clicking through the
flow, never a price, an instalment share, a tax rate, a GSTIN or a SAC (O-01 to O-07).

Run (local Compose does it after migrating):
    python -m p2b.identity.staff grant --email dev-admin@example.in --role ADMIN --reason "local"
    python -m p2b.billing.seed_dev --email dev-admin@example.in
"""

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select

from p2b.billing import configuration
from p2b.billing.models import OfferingVersion
from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.vocabulary import Audience, ConfigStatus, PaymentMode
from p2b.identity.interface import create_account_for

NOTE = "TEST: development value for local use, not a price or a tax figure"
RULE = {
    "base": "1000",
    "adjustments": [
        {
            "kind": "BAND",
            "characteristic": "built_up_area_sqft",
            "bands": [{"from": 0, "to": 2000, "amount": "0"}, {"from": 2000, "amount": "500"}],
        },
        {"kind": "ADD_IF", "characteristic": "quality_tier", "equals": "PREMIUM", "amount": "250"},
    ],
}
COMPONENTS = [
    {"name": "CGST", "rate": "9", "applies": "SAME_STATE"},
    {"name": "SGST", "rate": "9", "applies": "SAME_STATE"},
    {"name": "IGST", "rate": "18", "applies": "OTHER_STATE"},
]
PLAN = [
    {"share_bp": 5000, "due": "ON_ORDER"},
    {"share_bp": 5000, "due": "DAYS_AFTER_ACTIVATION", "days": 30},
]


async def seed(email: str) -> bool:
    settings = get_settings()
    if settings.env not in ("local", "test"):
        raise SystemExit("TEST billing configuration is for local development only")
    database = Database(settings)
    try:
        async with database.transaction() as session:
            existing = await session.scalar(
                select(OfferingVersion.id).where(
                    OfferingVersion.status == ConfigStatus.ACTIVE.value
                )
            )
            if existing is not None:
                return False
            admin, created = await create_account_for(
                session, audience=Audience.OPS, email=email, created_by=uuid.UUID(int=0)
            )
            if created:
                raise SystemExit("grant the account ADMIN first (python -m p2b.identity.staff)")
            who = {"actor_user_id": admin, "session_id": uuid.UUID(int=0)}

            async def publish(kind: configuration.ConfigKind, version_id: uuid.UUID) -> None:
                await configuration.publish(session, settings, kind, version_id, **who)

            rules = {}
            for code, rule in (("P2B_PACKAGE", RULE), ("AI_CREDIT_SINGLE", {"base": "10"})):
                row = await configuration.create_pricing_rule(
                    session, offering_code=code, rule=rule, is_test=True, note=NOTE, **who
                )
                await publish("pricing-rules", row.id)
                rules[code] = row.id
            plan = await configuration.create_instalment_plan(
                session, instalments=PLAN, is_test=True, note=NOTE, **who
            )
            await publish("instalment-plans", plan.id)
            tax = await configuration.create_tax_configuration(
                session,
                legal_name="TEST ENTITY (development)",
                address="TEST ADDRESS",
                gstin="TESTGSTIN000000",
                state_code="22",
                invoice_series="TEST",
                prices_include_tax=False,
                lines={
                    "PACKAGE": {"sac": "TEST", "components": COMPONENTS},
                    "AI_CREDIT": {"sac": "TEST", "components": COMPONENTS},
                },
                is_test=True,
                note=NOTE,
                **who,
            )
            await publish("tax-configurations", tax.id)
            for code, modes, plan_id in (
                ("P2B_PACKAGE", [PaymentMode.FULL, PaymentMode.INSTALMENTS], plan.id),
                ("AI_CREDIT_SINGLE", [PaymentMode.FULL], None),
            ):
                offering = await configuration.create_offering_version(
                    session,
                    offering_code=code,
                    pricing_rule_version_id=rules[code],
                    payment_modes=modes,
                    instalment_plan_version_id=plan_id,
                    terms_version="TEST-TERMS-1",
                    is_test=True,
                    note=NOTE,
                    **who,
                )
                await publish("offerings", offering.id)
        return True
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish TEST billing configuration locally.")
    parser.add_argument("--email", required=True, help="an existing ADMIN staff account")
    args = parser.parse_args()
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    done = asyncio.run(seed(args.email), loop_factory=loop_factory)
    print("seeded TEST billing configuration" if done else "billing configuration already present")


if __name__ == "__main__":
    main()
