"""Slice 3.3 billing (SLICE3_3_READINESS): orders priced by the server and immutable, instalments,
checkout through the fake gateway, webhooks verified and stored once, captures applied once
under the order lock, exceptions instead of invalid captures, reconciliation, package activation
without any project change, cancellation, refunds, invoices and credit notes, AI credits, the
eligibility checklist, access rules and production refusals."""

import asyncio
import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError

from p2b.billing.configuration import active_offer
from p2b.billing.credits import return_credit
from p2b.billing.models import (
    AiCreditEntry,
    BillingException,
    Invoice,
    Order,
    PackageEntitlement,
    Payment,
    PaymentAttempt,
    PaymentEvent,
)
from p2b.billing.payments import process_event, reconcile_daily, reconcile_open_attempts
from p2b.core.config import Settings, get_settings
from p2b.core.db import Database
from p2b.core.errors import BillingNotConfigured
from p2b.core.vocabulary import Audience, OfferingKind, StaffRole
from p2b.designs.models import DesignGeneration
from tests.billing_support import (
    BUYER,
    CHECKS,
    CREDIT_TOTAL,
    PACKAGE_TOTAL,
    TEST_TAX,
    admin_staff,
    checkout,
    configure,
    created,
    deliver,
    eligible_project,
    gateway,
    key,
    ops_key,
    order_of,
    order_package,
    ordered_credit,
    ordered_package,
    package_view,
    pricing_rule,
    publish,
    publish_ok,
)
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.staff_support import make_staff, verified_staff
from tests.test_designs import FailingProvider, designs, request_design, run_pending
from tests.test_review_workspace import review_ready


async def setup(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> tuple[AsyncClient, str, Any]:
    admin = await admin_staff(database, client_for, sign_in)
    await configure(admin)
    family, project_id, _ = await eligible_project(database, client_for, make_user, sign_in)
    return family, project_id, admin


async def pay(
    app: FastAPI,
    client: AsyncClient,
    ticket: dict[str, Any],
    *,
    status: str = "captured",
    amount_paise: int | None = None,
) -> Any:
    fake = gateway(app)
    payment = await fake.simulate_payment(
        ticket["provider_order_id"],
        status=status,
        amount_paise=amount_paise,  # type: ignore[arg-type]
    )
    event = "payment.captured" if status == "captured" else "payment.failed"
    response, _ = await deliver(client, fake, event, payment)
    assert response.status_code == 200, response.text
    return payment


async def count(database: Database, model: Any, *conditions: Any) -> int:
    async with database.transaction() as session:
        return int(
            await session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
        )


async def exceptions_of(database: Database) -> list[str]:
    async with database.transaction() as session:
        return list(await session.scalars(select(BillingException.kind)))


# --- orders and pricing ---------------------------------------------------------------------


async def test_the_server_prices_and_stamps_an_order_and_its_amount_never_changes(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    view = await package_view(family, project_id)
    assert view["state"] == "NOT_ACTIVE"
    assert view["offer"]["is_test"] is True
    assert Decimal(view["offer"]["price"]) == Decimal("1750.00")
    assert Decimal(view["offer"]["total"]) == PACKAGE_TOTAL
    assert view["offer"]["pricing_inputs"] == {
        "built_up_area_sqft": 2650,
        "quality_tier": "PREMIUM",
    }
    assert (await family.get(f"/api/v1/projects/{project_id}")).json()["package"]["purchasable"]

    order = await ordered_package(family, project_id)
    assert (order["state"], Decimal(order["total"]), order["is_test"]) == (
        "AWAITING_PAYMENT",
        PACKAGE_TOTAL,
        True,
    )
    assert [(t["component"], Decimal(t["amount"])) for t in order["tax"]] == [
        ("CGST", Decimal("157.50")),
        ("SGST", Decimal("157.50")),
    ]
    assert len(order["dues"]) == 1
    assert order["dues"][0]["payable"] is True

    async with database.transaction() as session:
        row = await session.get_one(Order, uuid.UUID(order["order_id"]))
        assert row.pricing_inputs == {"built_up_area_sqft": 2650, "quality_tier": "PREMIUM"}
    for statement in (
        "UPDATE orders SET total = 1, taxable_total = 1, tax_total = 0",
        "UPDATE orders SET buyer = '{}'::jsonb",
        "UPDATE payment_dues SET amount = 1, taxable_amount = 1, tax_amount = 0",
        "DELETE FROM orders",
    ):
        with pytest.raises(DBAPIError, match=r"may change|never deleted"):
            async with database.transaction() as session:
                await session.execute(text(statement))

    # One open order per project; another is refused with its id.
    second = await order_package(family, project_id)
    assert second.status_code == 409
    assert second.json()["error"]["details"]["open_order_id"] == order["order_id"]


async def test_a_client_cannot_name_an_amount_anywhere(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    for extra in ({"total": "1.00"}, {"amount": 1}, {"price": "1"}):
        response = await order_package(family, project_id, **extra)
        assert response.status_code == 422, response.text
    order = await ordered_package(family, project_id)
    ticket = await checkout(family, order["dues"][0]["due_id"])
    assert ticket["amount_paise"] == 206500  # the server's amount, in paise
    # The provider order carries the due's amount, whatever a page might claim.
    provider = await gateway(app).order_payments(ticket["provider_order_id"])
    assert provider == []
    async with database.transaction() as session:
        attempt = await session.get_one(PaymentAttempt, uuid.UUID(ticket["attempt_id"]))
        assert attempt.amount == PACKAGE_TOTAL
    # A paid amount different from the due is never applied.
    await pay(app, client_for(Audience.IHB), ticket, amount_paise=100)
    assert (await order_of(family, order["order_id"]))["state"] == "AWAITING_PAYMENT"


async def test_pricing_rules_are_versioned_and_orders_keep_theirs(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, admin = await setup(database, client_for, make_user, sign_in)
    old_offer = (await package_view(family, project_id))["offer"]
    first = await ordered_package(family, project_id)
    await family.post(f"/api/v1/orders/{first['order_id']}/cancel", headers=key())

    v2 = await pricing_rule(admin, "P2B_PACKAGE", {"base": "2000"})
    from tests.billing_support import offering

    await offering(admin, "P2B_PACKAGE", v2, ["FULL"])
    new_offer = (await package_view(family, project_id))["offer"]
    assert Decimal(new_offer["price"]) == Decimal("2000.00")
    # An order against the replaced offer is refused: the family sees the new price first.
    stale = await family.post(
        f"/api/v1/projects/{project_id}/package/orders",
        json={
            "offering_version_id": old_offer["offering_version_id"],
            "payment_mode": "FULL",
            "buyer": BUYER,
            "accept_terms_version": "TEST-TERMS-1",
        },
        headers=key(),
    )
    assert stale.status_code == 409
    second = await ordered_package(family, project_id)
    assert Decimal(second["price"]) == Decimal("2000.00")
    assert Decimal((await order_of(family, first["order_id"]))["price"]) == Decimal("1750.00")
    async with database.transaction() as session:
        rules = dict((await session.execute(select(Order.id, Order.pricing_rule_version_id))).all())
    assert rules[uuid.UUID(first["order_id"])] != rules[uuid.UUID(second["order_id"])]
    # Published rules never change.
    with pytest.raises(DBAPIError, match="may change"):
        async with database.transaction() as session:
            await session.execute(text("UPDATE pricing_rule_versions SET rule = '{}'::jsonb"))


async def test_instalments_split_the_order_exactly_and_later_dues_date_from_activation(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await ordered_package(family, project_id, "INSTALMENTS")
    first, second = order["dues"]
    assert Decimal(first["amount"]) + Decimal(second["amount"]) == PACKAGE_TOTAL
    assert Decimal(first["amount"]) == Decimal("1032.50")
    assert Decimal(first["taxable_amount"]) + Decimal(second["taxable_amount"]) == Decimal(
        "1750.00"
    )
    assert (first["due_rule"], second["due_rule"], second["due_days"]) == (
        "ON_ORDER",
        "DAYS_AFTER_ACTIVATION",
        30,
    )
    assert second["due_at"] is None
    assert second["payable"] is False
    # The second instalment cannot be paid before the package is active.
    early = await family.post(f"/api/v1/payment-dues/{second['due_id']}/checkout", headers=key())
    assert early.status_code == 409

    await pay(app, client_for(Audience.IHB), await checkout(family, first["due_id"]))
    await work()
    order = await order_of(family, order["order_id"])
    assert order["state"] == "PART_PAID"
    assert order["dues"][1]["due_at"] is not None
    assert order["dues"][1]["payable"] is True
    assert (await package_view(family, project_id))["state"] == "ACTIVE"
    await pay(app, client_for(Audience.IHB), await checkout(family, order["dues"][1]["due_id"]))
    await work()
    order = await order_of(family, order["order_id"])
    assert order["state"] == "PAID"
    assert len(order["invoices"]) == 2  # one per captured instalment


# --- paying ---------------------------------------------------------------------------------


async def test_a_verified_capture_activates_the_package_and_changes_nothing_else(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await ordered_package(family, project_id)
    ticket = await checkout(family, order["dues"][0]["due_id"])
    assert ticket["provider"] == "fake"
    assert ticket["key_id"] == "fake_key_test"
    # Asking again while the attempt is open reuses it: never two provider orders at once.
    assert (await checkout(family, order["dues"][0]["due_id"]))["attempt_id"] == ticket[
        "attempt_id"
    ]
    before = (await family.get(f"/api/v1/projects/{project_id}")).json()["project"]["status"]

    await pay(app, client_for(Audience.IHB), ticket)
    assert (await order_of(family, order["order_id"]))[
        "state"
    ] == "AWAITING_PAYMENT"  # not yet processed
    await work()

    order = await order_of(family, order["order_id"])
    assert order["state"] == "PAID"
    assert order["attempts"][0]["state"] == "CAPTURED"
    assert len(order["invoices"]) == 1
    assert order["invoices"][0]["document_ready"] is True
    view = await package_view(family, project_id)
    assert view["state"] == "ACTIVE"
    assert view["offer"] is None
    detail = (await family.get(f"/api/v1/projects/{project_id}")).json()
    assert detail["project"]["status"] == before == "ACCEPTED"  # L-06: the project does not move
    assert detail["package"]["state"] == "ACTIVE"
    assert detail["package"]["purchasable"] is False
    workspace = (await family.get(f"/api/v1/projects/{project_id}/workspace")).json()
    assert workspace["criteria_visible"] is True
    # The invoice PDF is the buyer's, by a logged link.
    link = await family.get(f"/api/v1/invoices/{order['invoices'][0]['invoice_id']}/document")
    assert link.status_code == 200


async def test_a_failed_payment_changes_nothing_and_a_new_attempt_can_follow(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await ordered_package(family, project_id)
    ticket = await checkout(family, order["dues"][0]["due_id"])
    await pay(app, client_for(Audience.IHB), ticket, status="failed")
    await work()
    order = await order_of(family, order["order_id"])
    assert (order["state"], order["attempts"][0]["state"]) == ("AWAITING_PAYMENT", "FAILED")
    assert (await package_view(family, project_id))["state"] == "NOT_ACTIVE"
    assert order["invoices"] == []
    retry = await checkout(family, order["dues"][0]["due_id"])
    assert retry["attempt_id"] != ticket["attempt_id"]
    assert retry["provider_order_id"] != ticket["provider_order_id"]


async def test_a_second_capture_for_a_paid_due_is_an_exception_never_applied(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await ordered_package(family, project_id)
    ticket = await checkout(family, order["dues"][0]["due_id"])
    await pay(app, client_for(Audience.IHB), ticket)
    await pay(app, client_for(Audience.IHB), ticket)  # paid twice in two tabs
    await work()
    assert await exceptions_of(database) == ["DUPLICATE_CAPTURE"]
    assert await count(database, Payment, Payment.applied.is_(True)) == 1
    assert await count(database, Payment, Payment.applied.is_(False)) == 1
    assert await count(database, Invoice) == 1
    order = await order_of(family, order["order_id"])
    assert order["state"] == "PAID"
    # The unapplied payment is refundable through a staff request.
    assert Decimal(order["refundable"]) == PACKAGE_TOTAL * 2


async def test_a_wrong_amount_is_an_exception_never_applied(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await ordered_package(family, project_id)
    ticket = await checkout(family, order["dues"][0]["due_id"])
    await pay(app, client_for(Audience.IHB), ticket, amount_paise=ticket["amount_paise"] - 100)
    await work()
    assert await exceptions_of(database) == ["AMOUNT_MISMATCH"]
    assert (await order_of(family, order["order_id"]))["state"] == "AWAITING_PAYMENT"
    assert (await package_view(family, project_id))["state"] == "NOT_ACTIVE"
    assert await count(database, Invoice) == 0


async def test_a_capture_after_the_attempt_expired_is_still_the_dues_money(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await ordered_package(family, project_id)
    ticket = await checkout(family, order["dues"][0]["due_id"])
    now = app.state.settings.model_copy(update={"billing_attempt_check_minutes": 0})
    counts = await reconcile_open_attempts(database, now, gateway(app))
    assert counts["expired"] == 1
    assert (await order_of(family, order["order_id"]))["attempts"][0]["state"] == "EXPIRED"

    await pay(app, client_for(Audience.IHB), ticket)  # the shopper's payment lands late
    await work()
    order = await order_of(family, order["order_id"])
    assert (order["state"], order["attempts"][0]["state"]) == ("PAID", "CAPTURED")
    assert (await package_view(family, project_id))["state"] == "ACTIVE"


async def test_a_capture_after_the_order_was_cancelled_is_an_exception(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await ordered_package(family, project_id)
    ticket = await checkout(family, order["dues"][0]["due_id"])
    cancelled = await family.post(f"/api/v1/orders/{order['order_id']}/cancel", headers=key())
    assert cancelled.json()["state"] == "CANCELLED"
    await pay(app, client_for(Audience.IHB), ticket)
    await work()
    assert await exceptions_of(database) == ["CAPTURE_AFTER_CANCEL"]
    order = await order_of(family, order["order_id"])
    assert order["state"] == "CANCELLED"
    assert (await package_view(family, project_id))["state"] == "NOT_ACTIVE"
    assert Decimal(order["refundable"]) == PACKAGE_TOTAL  # operations can return it


async def test_a_webhook_replay_is_stored_once_and_applied_once(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await ordered_package(family, project_id)
    ticket = await checkout(family, order["dues"][0]["due_id"])
    fake = gateway(app)
    payment = await fake.simulate_payment(ticket["provider_order_id"])
    client = client_for(Audience.IHB)
    first, event_id = await deliver(client, fake, "payment.captured", payment)
    again, _ = await deliver(client, fake, "payment.captured", payment, event_id=event_id)
    assert (first.status_code, again.status_code) == (200, 200)
    await work()
    assert await count(database, PaymentEvent) == 1
    assert await count(database, Payment) == 1
    assert await count(database, Invoice) == 1
    # A forged webhook is refused and leaves nothing behind.
    body, _, _ = fake.signed_webhook("payment.captured", payment=payment)
    forged = await client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": "0" * 64, "X-Razorpay-Event-Id": "evt_forged"},
    )
    assert forged.status_code == 401
    assert await count(database, PaymentEvent) == 1


async def test_racing_events_for_one_payment_apply_it_once_under_the_order_lock(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await ordered_package(family, project_id)
    ticket = await checkout(family, order["dues"][0]["due_id"])
    fake = gateway(app)
    payment = await fake.simulate_payment(ticket["provider_order_id"])
    client = client_for(Audience.IHB)
    await deliver(client, fake, "payment.captured", payment)
    await deliver(client, fake, "order.paid", payment)
    async with database.transaction() as session:
        event_ids = list(await session.scalars(select(PaymentEvent.id)))
    settings: Settings = app.state.settings
    results = await asyncio.gather(*(process_event(database, settings, e) for e in event_ids))
    assert sorted(results) == ["ALREADY_APPLIED", "APPLIED"]  # type: ignore[type-var]
    assert await count(database, Payment) == 1
    assert await count(database, Invoice) == 1
    assert await count(database, PackageEntitlement) == 1


async def test_the_browser_callback_is_only_a_hint_verified_with_the_provider(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await ordered_package(family, project_id)
    ticket = await checkout(family, order["dues"][0]["due_id"])
    fake = gateway(app)
    url = f"/api/v1/payment-attempts/{ticket['attempt_id']}/confirm"
    # A forged callback is refused and changes nothing.
    forged = await family.post(
        url,
        json={
            "provider_order_id": ticket["provider_order_id"],
            "provider_payment_id": "pay_forged",
            "signature": "x",
        },
        headers=key(),
    )
    assert forged.status_code == 401
    # A genuine callback for a payment the provider holds (its webhook not yet arrived): the
    # callback itself applies nothing; the verified fetch it queues does.
    payment = await fake.simulate_payment(ticket["provider_order_id"])
    hint = await family.post(
        url,
        json={
            "provider_order_id": ticket["provider_order_id"],
            "provider_payment_id": payment.payment_id,
            "signature": fake.checkout_signature(ticket["provider_order_id"], payment.payment_id),
        },
        headers=key(),
    )
    assert hint.status_code == 200
    assert hint.json() == {
        "attempt_id": ticket["attempt_id"],
        "state": "CREATED",
        "verifying": True,
    }
    assert (await package_view(family, project_id))["state"] == "NOT_ACTIVE"
    await work()
    assert (await package_view(family, project_id))["state"] == "ACTIVE"
    async with database.transaction() as session:
        assert (await session.scalar(select(Payment.source))) == "FETCH"


async def test_reconciliation_applies_captures_the_webhooks_missed_and_flags_strangers(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await ordered_package(family, project_id)
    ticket = await checkout(family, order["dues"][0]["due_id"])
    fake = gateway(app)
    await fake.simulate_payment(ticket["provider_order_id"])  # no webhook ever arrives
    settings = app.state.settings.model_copy(update={"billing_attempt_check_minutes": 0})
    counts = await reconcile_open_attempts(database, settings, fake)
    assert counts["applied"] == 1
    assert (await order_of(family, order["order_id"]))["state"] == "PAID"
    # The daily match finds a capture for a provider order that is not ours.
    stranger = await fake.create_order(amount_paise=500, currency="INR", receipt="x", notes={})
    await fake.simulate_payment(stranger.provider_order_id)
    daily = await reconcile_daily(database, settings, fake)
    assert daily["applied"] == 0
    assert daily["exceptions"] == 1
    assert await exceptions_of(database) == ["UNKNOWN_ORDER"]
    assert await count(database, Payment) == 1  # applied once across both runs


# --- the package after payment --------------------------------------------------------------


async def paid_package(
    app: FastAPI, work: Any, family: AsyncClient, client: AsyncClient, project_id: str
) -> dict[str, Any]:
    order = await ordered_package(family, project_id)
    await pay(app, client, await checkout(family, order["dues"][0]["due_id"]))
    await work()
    return await order_of(family, order["order_id"])


async def test_admin_cancels_a_package_with_a_reason_and_mfa(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, admin = await setup(database, client_for, make_user, sign_in)
    await paid_package(app, work, family, client_for(Audience.IHB), project_id)
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    url = f"/api/v1/ops/billing/packages/{project_id}/cancel"
    assert (await ops.client.post(url, json={"reason": "x"}, headers=ops_key())).status_code == 403
    response = await admin.client.post(
        url, json={"reason": "Duplicate account."}, headers=ops_key()
    )
    assert response.status_code == 200, response.text
    history = response.json()["package_history"]
    assert [(h["from_state"], h["to_state"]) for h in history] == [
        (None, "ACTIVE"),
        ("ACTIVE", "CANCELLED"),
    ]
    assert history[-1]["reason"] == "Duplicate account."
    assert (await package_view(family, project_id))["state"] == "CANCELLED"
    detail = (await family.get(f"/api/v1/projects/{project_id}")).json()
    assert detail["project"]["status"] == "ACCEPTED"


async def refund_request(family: AsyncClient, order_id: str) -> str:
    response = await family.post(
        f"/api/v1/orders/{order_id}/refund-requests",
        json={"reason": "Changed plans."},
        headers=key(),
    )
    assert response.status_code == 201, response.text
    request_id: str = response.json()["refund_requests"][-1]["request_id"]
    return request_id


async def test_an_approved_full_refund_returns_the_money_ends_the_package_and_issues_a_credit_note(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await paid_package(app, work, family, client_for(Audience.IHB), project_id)
    request_id = await refund_request(family, order["order_id"])
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    queue = (await ops.client.get("/api/v1/ops/billing/refund-requests?state=REQUESTED")).json()
    assert [r["request_id"] for r in queue] == [request_id]
    approved = await ops.client.post(
        f"/api/v1/ops/billing/refund-requests/{request_id}/approve",
        json={"amount": str(PACKAGE_TOTAL), "ends_package": True, "reason": "Before any work."},
        headers=ops_key(),
    )
    assert approved.status_code == 200, approved.text
    assert (await package_view(family, project_id))["state"] == "REFUNDED"
    await work()
    order = await order_of(family, order["order_id"])
    assert order["state"] == "REFUNDED"
    assert Decimal(order["refundable"]) == 0
    assert order["refund_requests"][0]["state"] == "REFUNDED"
    assert order["refund_requests"][0]["decision"]["reason"] == "Before any work."
    kinds = sorted(i["kind"] for i in order["invoices"])
    assert kinds == ["CREDIT_NOTE", "TAX_INVOICE"]
    credit_note = next(i for i in order["invoices"] if i["kind"] == "CREDIT_NOTE")
    assert Decimal(credit_note["total"]) == PACKAGE_TOTAL
    refunds = await gateway(app).payment_refund_records(
        (await session_payment(database)).provider_payment_id
    )
    assert len(refunds) == 1  # one provider refund, carrying our id
    assert (await family.get(f"/api/v1/projects/{project_id}")).json()["project"][
        "status"
    ] == "ACCEPTED"


async def session_payment(database: Database) -> Payment:
    async with database.transaction() as session:
        return (await session.scalars(select(Payment).where(Payment.applied.is_(True)))).one()


async def test_a_partial_refund_keeps_the_package_and_the_rest_refundable(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await paid_package(app, work, family, client_for(Audience.IHB), project_id)
    request_id = await refund_request(family, order["order_id"])
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    too_much = await ops.client.post(
        f"/api/v1/ops/billing/refund-requests/{request_id}/approve",
        json={"amount": str(PACKAGE_TOTAL + 1), "reason": "x"},
        headers=ops_key(),
    )
    assert too_much.status_code == 422
    half = await ops.client.post(
        f"/api/v1/ops/billing/refund-requests/{request_id}/approve",
        json={"amount": "1032.50", "ends_package": False, "reason": "Half the work done."},
        headers=ops_key(),
    )
    assert half.status_code == 200, half.text
    await work()
    order = await order_of(family, order["order_id"])
    assert order["state"] == "PARTLY_REFUNDED"
    assert Decimal(order["refundable"]) == Decimal("1032.50")
    assert (await package_view(family, project_id))["state"] == "ACTIVE"
    note = next(i for i in order["invoices"] if i["kind"] == "CREDIT_NOTE")
    assert Decimal(note["total"]) == Decimal("1032.50")


async def test_refund_decisions_need_a_staff_role_and_fresh_mfa(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    order = await paid_package(app, work, family, client_for(Audience.IHB), project_id)
    # Another family cannot ask for this order's refund, or see it.
    stranger, _, _ = await eligible_project(database, client_for, make_user, sign_in)
    url = f"/api/v1/orders/{order['order_id']}/refund-requests"
    assert (await stranger.post(url, json={"reason": "mine"}, headers=key())).status_code == 404
    assert (await stranger.get(f"/api/v1/orders/{order['order_id']}")).status_code == 404
    request_id = await refund_request(family, order["order_id"])
    approve = f"/api/v1/ops/billing/refund-requests/{request_id}/approve"
    body = {"amount": "1.00", "reason": "x"}
    # The family cannot approve (no such route on the homeowner host).
    assert (await family.post(approve, json=body, headers=key())).status_code == 404
    # Staff without a role, and staff with a role but no verified MFA, are refused.
    no_role = await make_staff(database, client_for, sign_in)
    assert (await no_role.client.post(approve, json=body, headers=ops_key())).status_code == 403
    unverified = await make_staff(database, client_for, sign_in, StaffRole.OPS)
    response = await unverified.client.post(approve, json=body, headers=ops_key())
    assert (response.status_code, response.json()["error"]["code"]) == (403, "MFA_REQUIRED")
    assert (await order_of(family, order["order_id"]))["refund_requests"][0]["state"] == "REQUESTED"


# --- invoices and tax -----------------------------------------------------------------------


async def test_invoice_numbers_are_gapless_per_series_and_only_paid_dues_take_one(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    other, other_project, _ = await eligible_project(database, client_for, make_user, sign_in)
    unpaid = await ordered_package(other, other_project)
    failed = await checkout(other, unpaid["dues"][0]["due_id"])
    await pay(app, client_for(Audience.IHB), failed, status="failed")
    await paid_package(app, work, family, client_for(Audience.IHB), project_id)
    await work()
    await other.post(f"/api/v1/orders/{unpaid['order_id']}/cancel", headers=key())
    third, third_project, _ = await eligible_project(database, client_for, make_user, sign_in)
    await paid_package(app, work, third, client_for(Audience.IHB), third_project)
    async with database.transaction() as session:
        rows = (
            await session.execute(
                select(Invoice.series, Invoice.number, Invoice.code).order_by(Invoice.number)
            )
        ).all()
    assert [(r[0], r[1]) for r in rows] == [("TEST", 1), ("TEST", 2)]
    assert all(r[2].startswith("TEST/20") and r[2].endswith(f"/{r[1]:05d}") for r in rows)


async def test_orders_are_refused_until_a_complete_tax_configuration_is_published(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    admin = await admin_staff(database, client_for, sign_in)
    await configure(admin, tax=False)
    family, project_id, _ = await eligible_project(database, client_for, make_user, sign_in)
    view = await package_view(family, project_id)
    assert view["offer"] is None
    assert view["unavailable"] == {"code": "BILLING_NOT_CONFIGURED", "missing": ["tax"]}
    assert (await family.get(f"/api/v1/projects/{project_id}")).json()["package"][
        "purchasable"
    ] is False
    response = await family.post(
        f"/api/v1/projects/{project_id}/package/orders",
        json={
            "offering_version_id": str(uuid.uuid4()),
            "payment_mode": "FULL",
            "buyer": BUYER,
            "accept_terms_version": "TEST-TERMS-1",
        },
        headers=key(),
    )
    assert response.status_code == 503
    # An incomplete configuration cannot be published.
    incomplete = await created(admin, "tax-configurations", {**TEST_TAX, "gstin": ""})
    refused = await publish(admin, "tax-configurations", incomplete)
    assert refused.status_code == 422
    assert "gstin" in refused.json()["error"]["details"]["missing"]
    complete = await created(admin, "tax-configurations", TEST_TAX)
    await publish_ok(admin, "tax-configurations", complete)
    assert (await package_view(family, project_id))["offer"] is not None


async def test_production_refuses_test_values_fake_payments_and_wrong_keys(
    app: FastAPI, database: Database, client_for: ClientFactory, sign_in: SignIn
) -> None:
    admin = await admin_staff(database, client_for, sign_in)
    await configure(admin)
    production = app.state.settings.model_copy(update={"env": "production"})
    async with database.transaction() as session:
        await active_offer(session, app.state.settings, OfferingKind.PACKAGE)  # fine in test
        with pytest.raises(BillingNotConfigured, match="Test values"):
            await active_offer(session, production, OfferingKind.PACKAGE)
    base = get_settings().model_dump()
    live = {
        **base,
        "env": "production",
        "email_provider": "resend",
        "resend_api_key": "key",
        "cookie_secure": True,
        "storage_provider": "s3",
        "scanner_provider": "clamav",
        "ai_image_provider": "none",
        "invoice_font_path": "/fonts/body.ttf",
    }
    with pytest.raises(ValueError, match="fake payment gateway never"):
        Settings(**{**live, "payment_provider": "fake"})
    with pytest.raises(ValueError, match="live Razorpay keys only"):
        Settings(**{**live, "payment_provider": "razorpay", "payment_key_id": "rzp_test_x"})
    ok = Settings(**{**live, "payment_provider": "razorpay", "payment_key_id": "rzp_live_x"})
    assert ok.payment_provider == "razorpay"
    with pytest.raises(ValueError, match="production only"):
        Settings(**{**base, "payment_provider": "razorpay", "payment_key_id": "rzp_live_x"})
    with pytest.raises(ValueError, match="locally and in tests"):
        Settings(**{**base, "env": "staging", "payment_provider": "fake"})


# --- AI credits -----------------------------------------------------------------------------


async def test_a_paid_credit_order_grants_one_credit_after_verified_capture(
    app: FastAPI,
    database: Database,
    work: Any,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    admin = await admin_staff(database, client_for, sign_in)
    await configure(admin)
    family, _, _ = await eligible_project(database, client_for, make_user, sign_in)
    order = await ordered_credit(family)
    assert (order["kind"], Decimal(order["total"]), order["project_id"]) == (
        "AI_CREDIT",
        CREDIT_TOTAL,
        None,
    )
    ticket = await checkout(family, order["dues"][0]["due_id"])
    assert (await family.get("/api/v1/me/ai-credits")).json()["balance"] == 0  # not yet
    await pay(app, client_for(Audience.IHB), ticket)
    await work()
    credits = (await family.get("/api/v1/me/ai-credits")).json()
    assert credits["balance"] == 1
    assert [(e["entry"], e["quantity"]) for e in credits["entries"]] == [("GRANT", 1)]
    # The ledger is append-only.
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("UPDATE ai_credit_ledger SET balance_after = 5"))


async def test_eligibility_checklist_is_required_recorded_and_append_only(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    _, project_id, ops = await review_ready(database, client_for, make_user, sign_in)
    url = f"/api/v1/ops/projects/{project_id}/accept"
    detail = (await ops.client.get(f"/api/v1/ops/projects/{project_id}")).json()["eligibility"]
    assert [i["id"] for i in detail["items"]] == CHECKS
    assert detail["assessment"] is None

    missing = await ops.client.post(
        url,
        json={"checks": [{"item_id": "new_individual_house", "outcome": "PASSED"}]},
        headers=ops_key(),
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["details"]["eligibility"]["missing"] == CHECKS[1:]
    failing = [{"item_id": i, "outcome": "PASSED"} for i in CHECKS[:-1]]
    failing.append({"item_id": CHECKS[-1], "outcome": "FAILED", "note": "Budget too low."})
    refused = await ops.client.post(url, json={"checks": failing}, headers=ops_key())
    assert refused.status_code == 422
    assert refused.json()["error"]["details"]["eligibility"]["failed"] == [CHECKS[-1]]
    passed = [{"item_id": i, "outcome": "PASSED", "note": "ok"} for i in CHECKS]
    accepted = await ops.client.post(url, json={"checks": passed}, headers=ops_key())
    assert accepted.status_code == 200, accepted.text
    eligibility = accepted.json()["eligibility"]
    assert [r["item_id"] for r in eligibility["assessment"]] == CHECKS
    assert eligibility["assessed_by_email"] == ops.email
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("UPDATE eligibility_assessments SET results = '[]'::jsonb"))


async def test_unclaimed_reviews_still_cannot_be_accepted(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    _, project_id, _ = await review_ready(database, client_for, make_user, sign_in)
    other = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    passed = [{"item_id": i, "outcome": "PASSED"} for i in CHECKS]
    response = await other.client.post(
        f"/api/v1/ops/projects/{project_id}/accept", json={"checks": passed}, headers=ops_key()
    )
    assert response.status_code == 409  # the reviewer's claim rule is unchanged


async def credit_entries(database: Database) -> list[str]:
    async with database.transaction() as session:
        return list(
            await session.scalars(select(AiCreditEntry.entry).order_by(AiCreditEntry.sequence))
        )


async def test_ai_credits_are_spent_only_when_chosen_and_returned_exactly_once(
    app: FastAPI,
    database: Database,
    work: Any,
    monkeypatch: pytest.MonkeyPatch,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, _ = await setup(database, client_for, make_user, sign_in)
    no_free = app.state.settings.model_copy(update={"ai_free_generations_per_project": 0})
    monkeypatch.setattr(app.state, "settings", no_free)
    quota = (await designs(family, project_id))["quota"]
    assert (quota["block"], quota["credit_balance"], quota["can_use_credit"]) == (
        "FREE_QUOTA_USED",
        0,
        False,
    )
    no_credit = await request_design(family, project_id, {"view": "EXTERIOR", "use_credit": True})
    assert (no_credit.status_code, no_credit.json()["error"]["code"]) == (409, "NO_CREDIT")

    # A credit exists only after its payment is captured and verified.
    order = await ordered_credit(family)
    await pay(app, client_for(Audience.IHB), await checkout(family, order["dues"][0]["due_id"]))
    await work()
    quota = (await designs(family, project_id))["quota"]
    assert (quota["credit_balance"], quota["can_use_credit"]) == (1, True)

    # Never silently: without the family's choice the request is refused and nothing is spent.
    silent = await request_design(family, project_id)
    assert (silent.status_code, silent.json()["error"]["code"]) == (409, "QUOTA_EXHAUSTED")
    assert (await designs(family, project_id))["quota"]["credit_balance"] == 1

    paid = await request_design(family, project_id, {"view": "EXTERIOR", "use_credit": True})
    assert paid.status_code == 202, paid.text
    assert paid.json()["funding"] == "PAID"
    assert (await designs(family, project_id))["quota"]["credit_balance"] == 0
    assert await run_pending(app, database, FailingProvider()) == ["FAILED"]
    assert (await designs(family, project_id))["quota"]["credit_balance"] == 1
    assert await credit_entries(database) == ["GRANT", "CONSUME", "RETURN"]
    async with database.transaction() as session:
        again = await return_credit(session, generation_id=uuid.UUID(paid.json()["design_id"]))
    assert again is False
    assert await credit_entries(database) == ["GRANT", "CONSUME", "RETURN"]

    # A paid generation lost in the queue expires as stale and gets its credit back once; the
    # job finding it later changes nothing.
    lost = await request_design(family, project_id, {"view": "EXTERIOR", "use_credit": True})
    assert lost.status_code == 202
    async with database.transaction() as session:
        await session.execute(
            update(DesignGeneration)
            .where(DesignGeneration.id == uuid.UUID(lost.json()["design_id"]))
            .values(created_at=func.now() - text("interval '2 days'"))
        )
    assert (await designs(family, project_id))["quota"]["credit_balance"] == 1
    assert await run_pending(app, database) == []
    assert await credit_entries(database) == ["GRANT", "CONSUME", "RETURN", "CONSUME", "RETURN"]
