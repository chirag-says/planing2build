"""The quote comparison PDF (QD-23, ADR-023): rendered once at publication from the frozen
snapshot only, deterministic (the creation date is the publication time, so the same snapshot
gives the same bytes). The adjustment list comes first; quotes follow in the snapshot's neutral
order; there is no rank, score or recommendation. English only (ADR-022)."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fpdf import FPDF, XPos, YPos

from p2b.core.config import Settings


def _text(unicode_font: bool, value: object) -> str:
    text = "" if value is None else str(value)
    return text if unicode_font else text.encode("latin-1", "replace").decode("latin-1")


def _money(value: object) -> str:
    return f"INR {Decimal(str(value)):,.2f}"


def render(
    settings: Settings, snapshot: dict[str, Any], *, version_no: int, published_at: datetime
) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_creation_date(published_at)
    pdf.set_producer("Plan2Build")
    pdf.set_creator("Plan2Build")
    pdf.set_title(f"Quote comparison {snapshot['project_code']} version {version_no}")
    pdf.set_auto_page_break(auto=True, margin=15)
    unicode_font = bool(settings.invoice_font_path and Path(settings.invoice_font_path).is_file())
    family = "Body" if unicode_font else "helvetica"
    if unicode_font:
        pdf.add_font("Body", fname=settings.invoice_font_path)

    def line(value: object, size: int = 9, height: float = 5) -> None:
        pdf.set_font(family, size=size)
        pdf.multi_cell(0, height, _text(unicode_font, value), new_x=XPos.LMARGIN,
                       new_y=YPos.NEXT)  # fmt: skip

    def heading(value: str) -> None:
        pdf.ln(2)
        line(value, 13, 8)

    pdf.add_page()
    line("Plan2Build quote comparison", 18, 10)
    line(f"Project: {snapshot['project_code']}")
    line(f"Comparison version: {version_no}   Published: {published_at.isoformat()}")
    line(f"Build Plan version: {snapshot['build_plan_version_no']}   "
         f"Request pack sha256: {snapshot['manifest_sha256']}", 8, 4)  # fmt: skip
    counts = snapshot["counts"]
    line(
        f"Contractors invited: {counts['invited']}   Quotes received: "
        f"{counts['quotes_received']}   Quotes compared: {counts['included']}"
    )
    for note in snapshot["notes"]:
        line(note, 8, 4)

    quotes = snapshot["quotes"]

    def title(q: dict[str, Any]) -> str:
        name = q["contractor_name"] or "Contractor"
        firm = f" ({q['firm_name']})" if q["firm_name"] else ""
        return f"{name}{firm}, quote version {q['quote']['version_no']}"

    heading("Adjustments found by Plan2Build")
    for q in quotes:
        line(title(q), 10, 6)
        if not q["adjustments"]:
            line("No adjustments.", 8, 4)
        for a in q["adjustments"]:
            where = f"line {a['line_no']}" if a["line_no"] else (a["spec_line_code"] or "quote")
            line(
                f"{a['deviation_type']} ({where}): {a['description']}  impact "
                f"{_money(a['rupee_impact'])}"
                + (f"  [clarification {a['clarification_status']}]"
                   if a["clarification_status"] != "NONE" else ""),
                8, 4,
            )  # fmt: skip

    heading("Totals")
    for q in quotes:
        line(title(q), 10, 6)
        line(
            f"As submitted: {_money(q['quote']['comparable_total'])}   Adjustments: "
            f"{_money(q['adjustments_total'])}   On the same scope: "
            f"{_money(q['normalised_total'])}",
            8, 4,
        )  # fmt: skip
        if Decimal(str(q["quote"]["additional_total"])):
            line(f"Additional items proposed (not compared): "
                 f"{_money(q['quote']['additional_total'])}", 8, 4)  # fmt: skip
        line(
            f"Valid {q['quote']['valid_from']} to {q['quote']['valid_to']}; GST "
            f"{q['quote']['tax_treatment'].lower()}; {q['quote']['duration_days']} days",
            8, 4,
        )  # fmt: skip

    heading("Lines as submitted")
    for row in snapshot["lines"]:
        line(f"{row['line_no']}. {row['description']} ({row['quantity']} {row['unit']})", 9, 5)
        for q in quotes:
            match = next((x for x in q["quote"]["lines"] if x["line_no"] == row["line_no"]), None)
            if match is None:
                continue
            value = (
                f"excluded: {match['exclusion_reason']}"
                if match["excluded"]
                else f"{_money(match['rate'])} per {row['unit']} = {_money(match['amount'])}"
            )
            alt = f"; alternate: {match['alternate_spec']}" if match["alternate_spec"] else ""
            line(f"   {q['contractor_name'] or 'Contractor'}: {value}{alt}", 8, 4)

    heading("Terms as submitted")
    for q in quotes:
        line(title(q), 10, 6)
        content = q["quote"]
        for label, key in (("Payment terms", "payment_terms"), ("Warranty", "warranty"),
                           ("Materials", "materials"), ("Tax note", "tax_note")):  # fmt: skip
            if content[key]:
                line(f"{label}: {content[key]}", 8, 4)
        for item in content["exclusions"]:
            line(f"Exclusion: {item}", 8, 4)
        for item in content["assumptions"]:
            line(f"Assumption: {item}", 8, 4)

    line(f"{snapshot['project_code']}  comparison version {version_no}", 7, 4)
    return bytes(pdf.output())
