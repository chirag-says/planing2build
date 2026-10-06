"""Slice 3.3 operations paths: declining a refund, a failed refund retried, refund events the
provider sends that billing did not ask for, exception resolution, ADMIN configuration and the
eligibility checklist versions, and the Razorpay adapter's requests (mock transport)."""

import base64
import json
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, text

from p2b.billing.models import BillingException, Refund
from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.payments import GatewayError, GatewayRefund
from p2b.core.vocabulary import Audience, StaffRole
from p2b.integrations.razorpay import RazorpayGateway
from tests.billing_support import (
    CHECKS,
    PACKAGE_TOTAL,
    admin_staff,
    checkout,
    configure,
    created,
    eligible_project,
    gateway,
    key,
    ops_key,
    order_of,
    ordered_package,
    publish,
)
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.staff_support import OPS_HEADERS, verified_staff
from tests.test_review_workspace import review_ready


async def paid_order(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> tuple[Any, dict[str, Any]]:
    admin = await admin_staff(database, client_for, sign_in)
    await configure(admin)
    family, project_id, _ = await eligible_project(database, client_for, make_user, sign_in)
    order = await ordered_package(family, project_id)
    ticket = await checkout(family, order["dues"][0]["due_id"])
    fake = gateway(app)
    payment = await fake.simulate_payment(ticket["provider_order_id"])
    body, signature, event_id = fake.signed_webhook("payment.captured", payment=payment)
    await client_for(Audience.IHB).post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": event_id},
    )
    await work()
    return family, await order_of(family, order["order_id"])


async def request_refund(family: Any, order_id: str) -> str:
    response = await family.post(
        f"/api/v1/orders/{order_id}/refund-requests", json={"reason": "Please."}, headers=key()
    )
    assert response.status_code == 201, response.text
    request_id: str = response.json()["refund_requests"][-1]["request_id"]
    return request_id


async def test_a_declined_refund_shows_the_reason_and_a_new_request_can_follow(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, order = await paid_order(app, database, work, client_for, make_user, sign_in)
    request_id = await request_refund(family, order["order_id"])
    again = await family.post(
        f"/api/v1/orders/{order['order_id']}/refund-requests", json={"reason": "x"}, headers=key()
    )
    assert again.status_code == 409  # one open request at a time
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    url = f"/api/v1/ops/billing/refund-requests/{request_id}/decline"
    empty = await ops.client.post(url, json={"reason": " "}, headers=ops_key())
    assert empty.status_code == 422
    declined = await ops.client.post(url, json={"reason": "Work was delivered."}, headers=ops_key())
    assert declined.status_code == 200, declined.text
    order = await order_of(family, order["order_id"])
    assert order["refund_requests"][0]["state"] == "DECLINED"
    assert order["refund_requests"][0]["decision"]["reason"] == "Work was delivered."
    assert order["state"] == "PAID"
    assert order["can_request_refund"] is True
    twice = await ops.client.post(url, json={"reason": "again"}, headers=ops_key())
    assert twice.status_code == 409


async def test_a_failed_provider_refund_is_marked_and_can_be_retried(
    app: FastAPI,
    database: Database,
    work: Any,
    monkeypatch: pytest.MonkeyPatch,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, order = await paid_order(app, database, work, client_for, make_user, sign_in)
    request_id = await request_refund(family, order["order_id"])
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    fake = gateway(app)
    real = fake.create_refund

    async def refuse(**_: Any) -> GatewayRefund:
        raise GatewayError("refund refused", retryable=False)

    monkeypatch.setattr(fake, "create_refund", refuse)
    approved = await ops.client.post(
        f"/api/v1/ops/billing/refund-requests/{request_id}/approve",
        json={"amount": str(PACKAGE_TOTAL), "reason": "Before work."},
        headers=ops_key(),
    )
    assert approved.status_code == 200
    await work()
    detail = (await ops.client.get(f"/api/v1/ops/billing/refund-requests/{request_id}")).json()
    assert detail["state"] == "FAILED"
    assert detail["refunds"][0]["failure"] == "refund refused"
    monkeypatch.setattr(fake, "create_refund", real)
    retried = await ops.client.post(
        f"/api/v1/ops/billing/refund-requests/{request_id}/retry", headers=ops_key()
    )
    assert retried.status_code == 200, retried.text
    await work()
    order = await order_of(family, order["order_id"])
    assert order["refund_requests"][0]["state"] == "REFUNDED"
    assert order["state"] == "REFUNDED"
    async with database.transaction() as session:
        states = sorted(await session.scalars(select(Refund.state)))
    assert states == ["FAILED", "REFUNDED"]


async def test_a_refund_billing_did_not_ask_for_is_an_exception_operations_resolve(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    await paid_order(app, database, work, client_for, make_user, sign_in)
    fake = gateway(app)
    stranger = GatewayRefund("rfnd_dashboard", "pay_unknown", 100, "processed", {})
    body, signature, event_id = fake.signed_webhook("refund.processed", refund=stranger)
    response = await client_for(Audience.IHB).post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": event_id},
    )
    assert response.status_code == 200
    await work()
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    listed = (await ops.client.get("/api/v1/ops/billing/exceptions")).json()
    assert [(e["kind"], e["state"]) for e in listed] == [("REFUND_MISMATCH", "OPEN")]
    url = f"/api/v1/ops/billing/exceptions/{listed[0]['exception_id']}/resolve"
    resolved = await ops.client.post(
        url, json={"resolution": "Refunded in the dashboard by mistake."}, headers=OPS_HEADERS
    )
    assert resolved.status_code == 200
    assert resolved.json()["state"] == "RESOLVED"
    assert (
        await ops.client.post(url, json={"resolution": "again"}, headers=OPS_HEADERS)
    ).status_code == 409
    async with database.transaction() as session:
        row = (await session.scalars(select(BillingException))).one()
        assert row.resolution == "Refunded in the dashboard by mistake."


async def test_admin_configuration_is_admin_only_versioned_and_previewable(
    database: Database, client_for: ClientFactory, sign_in: SignIn
) -> None:
    admin = await admin_staff(database, client_for, sign_in)
    ids = await configure(admin)
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    assert (await ops.client.get("/api/v1/admin/billing/pricing-rules")).status_code == 403
    rules = (await admin.client.get("/api/v1/admin/billing/pricing-rules")).json()
    assert {r["status"] for r in rules} == {"ACTIVE"}
    assert all(r["is_test"] for r in rules)
    preview = await admin.client.post(
        f"/api/v1/admin/billing/pricing-rules/{ids['package_rule']}/preview",
        json={"characteristics": {"built_up_area_sqft": 1000, "quality_tier": "STANDARD"}},
        headers=OPS_HEADERS,
    )
    assert preview.json()["price"] == "1000.00"
    again = await publish(admin, "pricing-rules", ids["package_rule"])
    assert again.status_code == 409  # published versions are never published or edited again
    bad = await admin.client.post(
        "/api/v1/admin/billing/instalment-plans",
        json={"instalments": [{"share_bp": 10000, "due": "ON_ORDER"}], "is_test": True},
        headers=OPS_HEADERS,
    )
    assert bad.status_code == 422
    # An offer must name a published rule of its own offering.
    draft = await created(
        admin,
        "pricing-rules",
        {"offering_code": "P2B_PACKAGE", "rule": {"base": "5"}, "is_test": True},
    )
    offer = await created(
        admin,
        "offerings",
        {
            "offering_code": "P2B_PACKAGE",
            "pricing_rule_version_id": draft,
            "payment_modes": ["FULL"],
            "terms_version": "T",
            "is_test": True,
        },
    )
    assert (await publish(admin, "offerings", offer)).status_code == 409


async def test_a_new_eligibility_checklist_version_governs_later_acceptances(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    admin = await admin_staff(database, client_for, sign_in)
    try:
        created_ = await admin.client.post(
            "/api/v1/admin/eligibility-checklists",
            json={"items": [{"id": "only_check", "label": "The only check"}], "note": "test"},
            headers=OPS_HEADERS,
        )
        assert created_.status_code == 201, created_.text
        version_id = created_.json()["version_id"]
        published = await admin.client.post(
            f"/api/v1/admin/eligibility-checklists/{version_id}/publish", headers=OPS_HEADERS
        )
        assert published.json()["status"] == "ACTIVE"
        _, project_id, ops = await review_ready(database, client_for, make_user, sign_in)
        url = f"/api/v1/ops/projects/{project_id}/accept"
        old = [{"item_id": i, "outcome": "PASSED"} for i in CHECKS]
        assert (
            await ops.client.post(url, json={"checks": old}, headers=ops_key())
        ).status_code == 422
        new = [{"item_id": "only_check", "outcome": "PASSED"}]
        assert (
            await ops.client.post(url, json={"checks": new}, headers=ops_key())
        ).status_code == 200
    finally:
        async with database.transaction() as session:
            await session.execute(
                text(
                    "UPDATE eligibility_checklist_versions SET status = 'RETIRED' WHERE version > 1"
                )
            )
            await session.execute(
                text(
                    "UPDATE eligibility_checklist_versions SET status = 'ACTIVE' WHERE version = 1"
                )
            )


async def test_the_razorpay_adapter_sends_server_amounts_with_basic_auth() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path.endswith("/orders"):
            body = json.loads(request.content)
            return httpx.Response(
                200, json={"id": "order_1", "amount": body["amount"], "currency": body["currency"]}
            )
        if path.endswith("/orders/order_1/payments"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "pay_1",
                            "order_id": "order_1",
                            "amount": 206500,
                            "currency": "INR",
                            "status": "captured",
                            "captured": True,
                            "method": "upi",
                            "fee": 100,
                            "tax": 18,
                        }
                    ]
                },
            )
        if path.endswith("/payments/pay_1/refund"):
            return httpx.Response(
                200,
                json={
                    "id": "rfnd_1",
                    "payment_id": "pay_1",
                    "amount": 100,
                    "status": "processed",
                    "notes": {"refund_id": "r"},
                },
            )
        return httpx.Response(503)

    settings = get_settings().model_copy(
        update={"payment_provider": "razorpay", "payment_key_id": "rzp_test_k"}
    )
    adapter = RazorpayGateway(settings, transport=httpx.MockTransport(handler))
    order = await adapter.create_order(
        amount_paise=206500, currency="INR", receipt="ORD-" + "X" * 60, notes={}
    )
    assert (order.provider_order_id, order.amount_paise) == ("order_1", 206500)
    sent = json.loads(seen[0].content)
    assert sent["amount"] == 206500
    assert len(sent["receipt"]) == 40  # Razorpay's receipt limit
    assert (
        seen[0].headers["authorization"]
        == "Basic " + base64.b64encode(b"rzp_test_k:test-payment-key-secret").decode()
    )
    payments = await adapter.order_payments("order_1")
    assert payments[0].captured
    assert payments[0].fee_paise == 100
    refund = await adapter.create_refund(
        payment_id="pay_1", amount_paise=100, notes={"refund_id": "r"}
    )
    assert refund.notes == {"refund_id": "r"}
    with pytest.raises(GatewayError) as unavailable:
        await adapter.payment_refunds("pay_1")
    assert unavailable.value.retryable is True
    assert adapter.public_key_id == "rzp_test_k"
