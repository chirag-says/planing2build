"""Invoices and credit notes (SLICE3_3_READINESS F). Plan2Build's own documents, issued only
after a verified capture (a tax invoice for the due it paid) or a completed refund (a credit
note against that invoice), so unpaid checkouts never take a number. Numbers are gapless per
series and Indian financial year, taken from a locked counter row in the issuing transaction.
The seller is the published tax configuration; the buyer is the order's snapshot. The PDF is
rendered by a job and stored privately; the layout is a development format until the
accountant approves one (launch gate N-05)."""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.billing.configuration import tax_config_of
from p2b.billing.models import (
    Invoice,
    InvoiceLine,
    InvoiceSequence,
    InvoiceTaxLine,
    Offering,
    OfferingVersion,
    Order,
    Payment,
    PaymentDue,
    Refund,
    TaxConfigurationVersion,
)
from p2b.billing.money import financial_year, rupees
from p2b.billing.tax import STATE_CODES, scale
from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.storage import Storage
from p2b.core.vocabulary import ActorType, FilePurpose, InvoiceKind
from p2b.documents.interface import store_generated_file


class InvoiceIssued(EventPayload):
    invoice_id: uuid.UUID
    order_id: uuid.UUID


async def _number(session: AsyncSession, series: str, year: str) -> int:
    await session.execute(
        insert(InvoiceSequence)
        .values(series=series, financial_year=year, next_number=1)
        .on_conflict_do_nothing(index_elements=["series", "financial_year"])
    )
    counter = await session.get_one(
        InvoiceSequence, (series, year), with_for_update=True, populate_existing=True
    )
    number = counter.next_number
    counter.next_number = number + 1
    await session.flush()
    return number


def _seller(tax: TaxConfigurationVersion) -> dict[str, str]:
    return {
        "legal_name": tax.legal_name,
        "address": tax.address,
        "gstin": tax.gstin,
        "state_code": tax.state_code,
        "state": STATE_CODES.get(tax.state_code, ""),
    }


async def _issue(
    session: AsyncSession,
    *,
    kind: InvoiceKind,
    order: Order,
    description: str,
    sac: str,
    taxable: Decimal,
    tax_lines: list[dict[str, str]],
    due_id: uuid.UUID | None,
    payment_id: uuid.UUID | None,
    refund_id: uuid.UUID | None,
    original_invoice_id: uuid.UUID | None,
) -> Invoice:
    tax_version = await session.get_one(TaxConfigurationVersion, order.tax_configuration_version_id)
    now = (await session.execute(select(func.now()))).scalar_one()
    year = financial_year(now)
    series = tax_version.invoice_series + ("-CN" if kind == InvoiceKind.CREDIT_NOTE else "")
    number = await _number(session, series, year)
    tax_total = sum((Decimal(line["amount"]) for line in tax_lines), Decimal("0.00"))
    invoice = Invoice(
        id=new_id(),
        kind=kind.value,
        series=series,
        financial_year=year,
        number=number,
        code=f"{series}/{year}/{number:05d}",
        order_id=order.id,
        due_id=due_id,
        payment_id=payment_id,
        refund_id=refund_id,
        original_invoice_id=original_invoice_id,
        seller=_seller(tax_version),
        buyer=order.buyer,
        taxable_total=taxable,
        tax_total=tax_total,
        total=taxable + tax_total,
        currency=order.currency,
        is_test=order.is_test,
        issued_at=now,
    )
    session.add(invoice)
    await session.flush()
    session.add(
        InvoiceLine(
            id=new_id(),
            invoice_id=invoice.id,
            sequence=1,
            description=description[:200],
            sac=sac,
            quantity=order.quantity,
            taxable_value=taxable,
        )
    )
    for line in tax_lines:
        session.add(
            InvoiceTaxLine(
                id=new_id(),
                invoice_id=invoice.id,
                component=line["component"],
                rate=Decimal(line["rate"]),
                amount=Decimal(line["amount"]),
            )
        )
    await session.flush()
    await record(
        session,
        action=f"billing.{kind.value.lower()}_issued",
        entity_type="invoice",
        entity_id=invoice.id,
        project_id=order.project_id,
        actor_type=ActorType.JOB,
        new_value={"code": invoice.code, "total": str(invoice.total)},
    )
    await publish(
        session,
        event_type="billing.invoice_issued",
        aggregate_type="invoice",
        aggregate_id=invoice.id,
        payload=InvoiceIssued(invoice_id=invoice.id, order_id=order.id),
        dedupe_suffix="issued",
    )
    return invoice


async def _sac(session: AsyncSession, order: Order) -> tuple[str, str]:
    tax_version = await session.get_one(TaxConfigurationVersion, order.tax_configuration_version_id)
    line = getattr(tax_config_of(tax_version).lines, order.kind)
    version = await session.get_one(OfferingVersion, order.offering_version_id)
    offering = await session.get_one(Offering, version.offering_code)
    return line.sac, offering.name


async def issue_tax_invoice(
    session: AsyncSession, order: Order, due: PaymentDue, payment: Payment
) -> Invoice:
    sac, name = await _sac(session, order)
    count = await session.scalar(select(func.count()).where(PaymentDue.order_id == order.id))
    description = name if count == 1 else f"{name}: instalment {due.sequence} of {count}"
    return await _issue(
        session,
        kind=InvoiceKind.TAX_INVOICE,
        order=order,
        description=description,
        sac=sac,
        taxable=due.taxable_amount,
        tax_lines=due.tax,
        due_id=due.id,
        payment_id=payment.id,
        refund_id=None,
        original_invoice_id=None,
    )


async def issue_credit_note(session: AsyncSession, order: Order, refund: Refund) -> Invoice:
    """Against the tax invoice of the refunded payment, in proportion to the refund."""
    original = (
        await session.scalars(select(Invoice).where(Invoice.payment_id == refund.payment_id))
    ).one()
    tax_lines = await session.scalars(
        select(InvoiceTaxLine).where(InvoiceTaxLine.invoice_id == original.id)
    )
    lines = [
        {"component": t.component, "rate": str(t.rate), "amount": str(t.amount)} for t in tax_lines
    ]
    share_tax = scale(lines, refund.amount, original.total)
    tax_total = sum((Decimal(line["amount"]) for line in share_tax), Decimal("0.00"))
    taxable = rupees(refund.amount) - tax_total
    sac, name = await _sac(session, order)
    return await _issue(
        session,
        kind=InvoiceKind.CREDIT_NOTE,
        order=order,
        description=f"Refund: {name} (invoice {original.code})",
        sac=sac,
        taxable=taxable,
        tax_lines=share_tax,
        due_id=original.due_id,
        payment_id=None,
        refund_id=refund.id,
        original_invoice_id=original.id,
    )


# --- rendering ------------------------------------------------------------------------------


@dataclass(frozen=True)
class RenderedInvoice:
    content: bytes
    file_name: str


def _text(unicode_font: bool, value: str) -> str:
    # The core font is Latin-1 only; production sets a Unicode font (Settings requires it).
    return value if unicode_font else value.encode("latin-1", "replace").decode("latin-1")


def render_pdf(
    settings: Settings,
    invoice: Invoice,
    lines: list[InvoiceLine],
    taxes: list[InvoiceTaxLine],
    original_code: str | None,
) -> RenderedInvoice:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    unicode_font = bool(settings.invoice_font_path and Path(settings.invoice_font_path).is_file())
    family = "Body" if unicode_font else "helvetica"
    if unicode_font:
        pdf.add_font("Body", fname=settings.invoice_font_path)

    def line(value: str, size: int = 10, height: float = 6) -> None:
        pdf.set_font(family, size=size)
        pdf.multi_cell(0, height, _text(unicode_font, value), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if invoice.is_test:
        line("TEST DOCUMENT: development values, not a valid invoice", 11)
    title = "Tax invoice" if invoice.kind == InvoiceKind.TAX_INVOICE.value else "Credit note"
    line(title, 16, 9)
    line(f"{title} number: {invoice.code}")
    line(f"Date: {invoice.issued_at.date().isoformat()}")
    if original_code:
        line(f"Against invoice: {original_code}")
    pdf.ln(3)
    seller, buyer = invoice.seller, invoice.buyer
    line(f"From: {seller['legal_name']}")
    line(seller["address"])
    line(f"GSTIN: {seller['gstin']}   State: {seller.get('state', '')} ({seller['state_code']})")
    pdf.ln(3)
    line(f"To: {buyer.get('name', '')}")
    line(buyer.get("address", ""))
    line(
        f"State: {STATE_CODES.get(buyer.get('state_code', ''), '')} ({buyer.get('state_code', '')})"
        + (f"   GSTIN: {buyer['gstin']}" if buyer.get("gstin") else "")
    )
    pdf.ln(3)
    for item in lines:
        line(
            f"{item.description}   SAC {item.sac}   Qty {item.quantity}   "
            f"Taxable value {invoice.currency} {item.taxable_value}"
        )
    for tax in taxes:
        line(f"{tax.component} at {tax.rate}%: {invoice.currency} {tax.amount}")
    line(f"Total: {invoice.currency} {invoice.total}", 12, 8)
    content = bytes(pdf.output())
    safe = invoice.code.replace("/", "-")
    return RenderedInvoice(content, f"{safe}.pdf")


def due_split(
    total: Decimal, tax_lines: list[dict[str, str]], amounts: list[Decimal]
) -> list[tuple[Decimal, list[dict[str, str]]]]:
    """Each instalment's taxable value and tax lines, in proportion to its amount. The last
    takes what remains of every component, so the parts add up exactly to the order's."""
    remaining = [dict(line) for line in tax_lines]
    result = []
    for index, amount in enumerate(amounts):
        if index == len(amounts) - 1:
            part = remaining
        else:
            part = scale(tax_lines, amount, total)
            for left, share in zip(remaining, part, strict=True):
                left["amount"] = str(Decimal(left["amount"]) - Decimal(share["amount"]))
        tax_sum = sum((Decimal(t["amount"]) for t in part), Decimal("0.00"))
        result.append((amount - tax_sum, part))
    return result


async def render_and_store(
    database: Database, settings: Settings, storage: Storage, invoice_id: uuid.UUID
) -> bool:
    """The rendering job: the PDF for an issued invoice or credit note, stored privately for
    the buyer. Idempotent: a document once stored is kept."""
    async with database.transaction() as session:
        invoice = await session.get(Invoice, invoice_id, with_for_update=True)
        if invoice is None or invoice.document_id is not None:
            return False
        lines = list(
            await session.scalars(
                select(InvoiceLine)
                .where(InvoiceLine.invoice_id == invoice.id)
                .order_by(InvoiceLine.sequence)
            )
        )
        taxes = list(
            await session.scalars(
                select(InvoiceTaxLine)
                .where(InvoiceTaxLine.invoice_id == invoice.id)
                .order_by(InvoiceTaxLine.component)
            )
        )
        original = (
            (await session.get_one(Invoice, invoice.original_invoice_id)).code
            if invoice.original_invoice_id
            else None
        )
        order = await session.get_one(Order, invoice.order_id)
        rendered = render_pdf(settings, invoice, lines, taxes, original)
        invoice.document_id = await store_generated_file(
            session,
            settings,
            storage,
            project_id=None,
            owner_user_id=order.buyer_user_id,
            purpose=FilePurpose.INVOICE,
            data=rendered.content,
            mime="application/pdf",
            file_name=rendered.file_name,
        )
        await session.flush()
        return True
