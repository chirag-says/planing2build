"""Helpers for the billing tests (Slice 3.3): TEST commercial configuration published through the
ADMIN routes, an eligible project accepted with the F-05 checklist, orders, checkout, and the
fake gateway standing in for the shopper and for Razorpay's servers. Every value here is a
marked TEST value, never a price, rate or GSTIN."""

import uuid
from decimal import Decimal
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient, Response

from p2b.core.db import Database
from p2b.core.payments import GatewayPayment
from p2b.core.vocabulary import Audience, StaffRole
from p2b.integrations.fake_gateway import FakeGateway
from tests.conftest import ClientFactory, SignIn, UserFactory, csrf_headers
from tests.staff_support import OPS_HEADERS, Staff, verified_staff
from tests.test_review_workspace import accept, review_ready

H = csrf_headers(Audience.IHB)

# TEST pricing: base 1000, +500 from 2000 sq ft, +250 for the premium tier. The COMPLETE
# requirement (2650 sq ft, premium) prices at 1750.
TEST_RULE = {
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
TEST_COMPONENTS = [
    {"name": "CGST", "rate": "9", "applies": "SAME_STATE"},
    {"name": "SGST", "rate": "9", "applies": "SAME_STATE"},
    {"name": "IGST", "rate": "18", "applies": "OTHER_STATE"},
]
TEST_TAX = {
    "legal_name": "TEST ENTITY (development)",
    "address": "TEST ADDRESS",
    "gstin": "TESTGSTIN000000",
    "state_code": "22",
    "invoice_series": "TEST",
    "prices_include_tax": False,
    "lines": {
        "PACKAGE": {"sac": "TEST", "components": TEST_COMPONENTS},
        "AI_CREDIT": {"sac": "TEST", "components": TEST_COMPONENTS},
    },
    "is_test": True,
    "note": "TEST values",
}
TEST_PLAN = [
    {"share_bp": 5000, "due": "ON_ORDER"},
    {"share_bp": 5000, "due": "DAYS_AFTER_ACTIVATION", "days": 30},
]
PACKAGE_TOTAL = Decimal("2065.00")  # 1750 + 9% + 9%
CREDIT_TOTAL = Decimal("11.80")  # 10 + 9% + 9%
BUYER = {"name": "Asha Verma", "address": "12 Civil Lines, Raipur", "state_code": "22"}
CHECKS = [
    "new_individual_house",
    "service_geography",
    "requirement_complete",
    "review_flags_resolved",
    "information_plausible",
]


def key() -> dict[str, str]:
    return {**H, "Idempotency-Key": str(uuid.uuid4())}


def ops_key() -> dict[str, str]:
    return {**OPS_HEADERS, "Idempotency-Key": str(uuid.uuid4())}


async def created(admin: Staff, path: str, body: dict[str, Any]) -> str:
    response = await admin.client.post(
        f"/api/v1/admin/billing/{path}", json=body, headers=OPS_HEADERS
    )
    assert response.status_code == 201, response.text
    version_id: str = response.json()["version_id"]
    return version_id


async def publish(admin: Staff, kind: str, version_id: str) -> Response:
    return await admin.client.post(
        f"/api/v1/admin/billing/{kind}/{version_id}/publish", headers=OPS_HEADERS
    )


async def publish_ok(admin: Staff, kind: str, version_id: str) -> None:
    response = await publish(admin, kind, version_id)
    assert response.status_code == 200, response.text


async def pricing_rule(admin: Staff, offering: str, rule: dict[str, Any]) -> str:
    version_id = await created(
        admin,
        "pricing-rules",
        {"offering_code": offering, "rule": rule, "is_test": True, "note": "TEST"},
    )
    await publish_ok(admin, "pricing-rules", version_id)
    return version_id


async def offering(
    admin: Staff, code: str, rule_id: str, modes: list[str], plan_id: str | None = None
) -> str:
    version_id = await created(
        admin,
        "offerings",
        {
            "offering_code": code,
            "pricing_rule_version_id": rule_id,
            "payment_modes": modes,
            "instalment_plan_version_id": plan_id,
            "terms_version": "TEST-TERMS-1",
            "is_test": True,
        },
    )
    await publish_ok(admin, "offerings", version_id)
    return version_id


async def configure(admin: Staff, *, tax: bool = True) -> dict[str, str]:
    """Publish TEST offers for the package (FULL and INSTALMENTS) and the AI credit."""
    ids = {
        "package_rule": await pricing_rule(admin, "P2B_PACKAGE", TEST_RULE),
        "credit_rule": await pricing_rule(admin, "AI_CREDIT_SINGLE", {"base": "10"}),
    }
    ids["plan"] = await created(
        admin, "instalment-plans", {"instalments": TEST_PLAN, "is_test": True}
    )
    await publish_ok(admin, "instalment-plans", ids["plan"])
    if tax:
        ids["tax"] = await created(admin, "tax-configurations", TEST_TAX)
        await publish_ok(admin, "tax-configurations", ids["tax"])
    ids["package"] = await offering(
        admin, "P2B_PACKAGE", ids["package_rule"], ["FULL", "INSTALMENTS"], ids["plan"]
    )
    ids["credit"] = await offering(admin, "AI_CREDIT_SINGLE", ids["credit_rule"], ["FULL"])
    return ids


async def admin_staff(database: Database, client_for: ClientFactory, sign_in: SignIn) -> Staff:
    return await verified_staff(database, client_for, sign_in, StaffRole.ADMIN)


async def eligible_project(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> tuple[AsyncClient, str, Staff]:
    family, project_id, ops = await review_ready(database, client_for, make_user, sign_in)
    assert (await accept(ops, project_id)).status_code == 200
    return family, project_id, ops


async def package_view(family: AsyncClient, project_id: str) -> dict[str, Any]:
    response = await family.get(f"/api/v1/projects/{project_id}/package")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def order_package(
    family: AsyncClient, project_id: str, mode: str = "FULL", **extra: Any
) -> Response:
    offer = (await package_view(family, project_id))["offer"]
    body = {
        "offering_version_id": offer["offering_version_id"],
        "payment_mode": mode,
        "buyer": BUYER,
        "accept_terms_version": offer["terms_version"],
        **extra,
    }
    return await family.post(
        f"/api/v1/projects/{project_id}/package/orders", json=body, headers=key()
    )


async def ordered_package(
    family: AsyncClient, project_id: str, mode: str = "FULL"
) -> dict[str, Any]:
    response = await order_package(family, project_id, mode)
    assert response.status_code == 201, response.text
    order: dict[str, Any] = response.json()
    return order


async def ordered_credit(family: AsyncClient) -> dict[str, Any]:
    offer = (await family.get("/api/v1/me/ai-credits")).json()["offer"]
    response = await family.post(
        "/api/v1/ai-credits/orders",
        json={
            "offering_version_id": offer["offering_version_id"],
            "buyer": BUYER,
            "accept_terms_version": offer["terms_version"],
        },
        headers=key(),
    )
    assert response.status_code == 201, response.text
    order: dict[str, Any] = response.json()
    return order


async def checkout(family: AsyncClient, due_id: str) -> dict[str, Any]:
    response = await family.post(f"/api/v1/payment-dues/{due_id}/checkout", headers=H)
    assert response.status_code == 200, response.text
    ticket: dict[str, Any] = response.json()
    return ticket


def gateway(app: FastAPI) -> FakeGateway:
    fake: FakeGateway = app.state.payment_gateway
    return fake


async def deliver(
    client: AsyncClient,
    fake: FakeGateway,
    event: str,
    payment: GatewayPayment,
    event_id: str | None = None,
) -> tuple[Response, str]:
    """Razorpay's servers posting a signed webhook to the real route."""
    body, signature, minted = fake.signed_webhook(event, payment=payment)
    response = await client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "X-Razorpay-Event-Id": event_id or minted,
        },
    )
    return response, event_id or minted


async def order_of(family: AsyncClient, order_id: str) -> dict[str, Any]:
    response = await family.get(f"/api/v1/orders/{order_id}")
    assert response.status_code == 200, response.text
    order: dict[str, Any] = response.json()
    return order
