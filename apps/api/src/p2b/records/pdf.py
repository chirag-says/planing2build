"""The Build Record PDF (EX-17, ADR-023): rendered once at issue from the frozen snapshot only,
deterministic (the creation date is the issue time, so the same snapshot gives the same bytes),
with the snapshot hash printed so the PDF and the JSON export can be matched. No price or amount;
product, purchase and installation show NOT RECORDED (EX-16). English only (ADR-022)."""

from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF, XPos, YPos

from p2b.core.config import Settings

FLOORS = {-1: "basement", 0: "ground floor", 1: "first floor", 2: "second floor",
          3: "third floor"}  # fmt: skip


def _text(unicode_font: bool, value: object) -> str:
    text = "" if value is None else str(value)
    return text if unicode_font else text.encode("latin-1", "replace").decode("latin-1")


def _floor(value: object) -> str:
    return "" if value is None else f" ({FLOORS.get(int(str(value)), f'floor {value}')})"


def render_record(
    settings: Settings, snapshot: dict[str, Any], *, version_no: int, issued_at: datetime,
    digest: str, basis: str, correction_reason: str | None,
) -> bytes:  # fmt: skip
    pdf = FPDF(format="A4")
    pdf.set_creation_date(issued_at)
    pdf.set_producer("Plan2Build")
    pdf.set_creator("Plan2Build")
    code = snapshot["identity"]["project_code"]
    pdf.set_title(f"Build Record {code} version {version_no}")
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
    line("Plan2Build Build Record", 18, 10)
    line(f"Project: {code}   Locality: {snapshot['identity']['locality'] or 'not recorded'}")
    line(f"Version {version_no}   Issued: {issued_at.isoformat()}")
    line(f"Snapshot sha256: {digest}", 7, 4)
    if correction_reason:
        line(f"This version corrects an earlier one: {correction_reason}")
    handover = snapshot["handover"]
    if basis == "ISSUED_BY_OPERATIONS":
        forced = handover["issued_without_acknowledgement"] or {}
        line(f"The handover was issued by Plan2Build without the owner's acknowledgement on "
             f"{forced.get('issued_at')}: {forced.get('reason')}", 9, 5)  # fmt: skip
    elif handover["acknowledgement"]:
        when = handover["acknowledgement"]["acknowledged_at"]
        line(f"The owner acknowledged the handover on {when}.")

    heading("Plan")
    plan = snapshot["plan"]
    line(f"Accepted Build Plan version {plan['build_plan_version_no']}, accepted "
         f"{plan['accepted_at']}, content hash {plan['content_hash']}")  # fmt: skip
    for d in snapshot["drawings"]:
        line(f"Drawing {d.get('sheet_no') or ''} {d.get('title') or d.get('drawing_class') or ''}"
             f"{_floor(d.get('floor'))} sha256 {d.get('sha256')}", 7, 4)  # fmt: skip

    heading("Contractors")
    for c in snapshot["contractors"]:
        who = c["name"] or "Contractor"
        label = " (chosen by the family)" if c["chosen_by_family"] else ""
        line(f"{who}{label}: {c['started_at']} to {c['ended_at'] or 'now'} ({c['state']})")

    heading("Execution")
    for s in snapshot["execution"]:
        line(f"Stage {s['stage_number']} {s['name']}{_floor(s['floor'])}: {s['state']}; "
             f"started {s['actual_start'] or '-'}, completed {s['actual_end'] or '-'}; "
             f"{s['updates']} updates", 8, 4)  # fmt: skip

    heading("Assurance")
    for i in snapshot["assurance"]["inspections"]:
        line(f"Gate {i['gate']} {i['stage']}{_floor(i['floor'])} ({i['kind'].lower()}), approved "
             f"{i['approved_at']}, auditor {i['auditor_code']}: {i['outcome']}", 8, 4)  # fmt: skip
        for r in i["reports"]:
            line(f"   Report version {r['version']} sha256 {r['sha256']}", 7, 4)
    for f in snapshot["assurance"]["findings"]:
        closed = f" closed {f['closed_at']}" if f["closed_at"] else ""
        line(f"Finding ({f['severity']}): {f['description']} - {f['state']}{closed}", 8, 4)

    heading("Payment marks (information only, no amounts)")
    for m in snapshot["payment_marks"]:
        paid = m["paid"]["value"] if m["paid"] else "not marked"
        received = m["received"]["value"] if m["received"] else "not marked"
        line(f"Stage {m['stage_number']}{_floor(m['floor'])}: paid {paid}; received {received}",
             8, 4)  # fmt: skip

    heading("Handover")
    for d in handover["documents"]:
        line(f"{d['kind']}: {d['title']} sha256 {d['sha256']}", 8, 4)
    for w in handover["warranties"]:
        line(f"Warranty: {w['item']}, {w['term']}, expires {w['expiry_date']}, installer "
             f"{w['installer']}", 8, 4)  # fmt: skip

    pdf.add_page()
    line("Specification", 14, 8)
    for s in snapshot["specification"]:
        checks = "; ".join(f"Gate {v['gate']} {v['result']}" for v in s["verification"])
        line(f"{s['code']} {s['item']}: {s['accepted_value'] or '-'}", 8, 4)
        line(f"   Verified: {checks or 'not inspected'}. Product, purchase and installation: "
             f"{s['product']}.", 7, 4)  # fmt: skip
    line(f"{code}  Build Record version {version_no}", 7, 4)
    return bytes(pdf.output())
