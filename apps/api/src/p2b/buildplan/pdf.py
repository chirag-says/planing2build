"""The Build Plan PDF (Slice 3.5): rendered from one version's snapshot only, deterministic (the
creation date is the version's issue or acceptance time, so the same snapshot gives the same
bytes). The issued document is stored at issue and never changes; acceptance stores a second,
separate document that adds the acceptance record.

Wording: section titles and the source statements only (S04: "Plan2Build compiles and
communicates; the engineer specifies"; criteria are indicative and confirmed against the
applicable Indian Standards and the structural design). No other legal language. English only
(ADR-022, BP-11). Rendered with fpdf2 like the 3.3 invoices; see the implementation report for
the ADR-018 deviation."""

from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF, XPos, YPos

from p2b.core.config import Settings

SOURCE_STATEMENTS = (
    "Plan2Build compiles and communicates; the engineer specifies.",
    "Specification criteria are indicative and are confirmed against the applicable Indian "
    "Standards and the project's structural design.",
)


def _text(unicode_font: bool, value: object) -> str:
    text = "" if value is None else str(value)
    return text if unicode_font else text.encode("latin-1", "replace").decode("latin-1")


def render(
    settings: Settings, view: dict[str, Any], *, created_at: datetime, accepted_copy: bool
) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_creation_date(created_at)
    pdf.set_producer("Plan2Build")
    pdf.set_creator("Plan2Build")
    pdf.set_title(f"Build Plan {view['project']['code']} version {view['version']['version_no']}")
    pdf.set_auto_page_break(auto=True, margin=15)
    unicode_font = bool(settings.invoice_font_path and Path(settings.invoice_font_path).is_file())
    family = "Body" if unicode_font else "helvetica"
    if unicode_font:
        pdf.add_font("Body", fname=settings.invoice_font_path)
    footer = (
        f"{view['project']['code']}  Build Plan version {view['version']['version_no']}  "
        f"content {view['version']['content_hash']}"
    )

    class _Doc:
        def line(self, value: object, size: int = 9, height: float = 5) -> None:
            pdf.set_font(family, size=size)
            pdf.multi_cell(0, height, _text(unicode_font, value), new_x=XPos.LMARGIN,
                           new_y=YPos.NEXT)  # fmt: skip

        def heading(self, value: str) -> None:
            pdf.ln(2)
            self.line(value, 13, 8)

    doc = _Doc()
    pdf.add_page()
    card = view.get("rate_card") or {}
    if card.get("is_demo"):
        doc.line("TEST DOCUMENT: priced from a DEMO rate card, not valid for construction", 11, 7)
    doc.line("Plan2Build Build Plan", 18, 10)
    v = view["version"]
    doc.line(f"Project: {view['project']['code']}  {view['project']['locality'] or ''}")
    doc.line(f"Version: {v['version_no']}   State: {v['state']}")
    doc.line(f"Issued: {v['issued_at'] or 'not issued'}")
    if accepted_copy and view.get("acceptance"):
        doc.line(f"Accepted by the homeowner: {view['acceptance']['accepted_at']}")
    doc.line(f"Content hash: {v['content_hash']}")
    doc.line(f"Requirement version: {v['requirement_version']}")
    if card:
        doc.line(f"Rate card: {card['geography']} version {card['version']}")
    for statement in SOURCE_STATEMENTS:
        doc.line(statement, 8, 4)

    doc.heading("Drawings")
    drawing_set = view.get("drawing_set")
    if drawing_set:
        doc.line(
            f"Drawing set {drawing_set['set_no']} ({drawing_set['request_kind']}), "
            f"provider {drawing_set['provider_name'] or 'the homeowner'}; checked by "
            f"{(drawing_set['checker'] or {}).get('name', '')} on {drawing_set['checked_at']}"
        )
        doc.line(f"Set hash: {drawing_set['content_hash']}", 8, 4)
        for f in drawing_set["files"]:
            floor = f" floor {f['floor']}" if f["floor"] is not None else ""
            doc.line(
                f"{f['drawing_class']}{floor}: {f['title']}  sheet {f['sheet_no'] or '-'}  "
                f"sha256 {f['sha256']}",
                8,
                4,
            )

    doc.heading("Specification values")
    for group in ("A", "B", "C"):
        doc.line(f"Group {group}", 10, 6)
        for value in [x for x in view["values"] if x["group"] == group]:
            if value["applicability"] == "APPLICABLE":
                stated = f"{value['value']} (basis: {value['basis']})"
            else:
                stated = f"Not applicable: {value['not_applicable_reason']}"
            mark = " [structural]" if value["is_structural"] else ""
            doc.line(f"{value['code']} {value['item']}{mark}", 8, 4)
            doc.line(f"   Criteria: {value['criteria']}", 7, 4)
            doc.line(f"   Project value: {stated}", 8, 4)

    doc.heading("Bill of quantities (BOQ)")
    for b in view["boq"]:
        doc.line(
            f"{b['line_no']}. {b['item_code']} {b['description']}  {b['quantity']} {b['unit']} "
            f"x INR {b['rate']} = INR {b['amount']}  stage {b['stage_number'] or '-'}",
            8,
            4,
        )
    doc.line(f"Total: INR {view['boq_total']}", 10, 6)
    for stage, total in view["stage_totals"].items():
        doc.line(f"Stage {stage}: INR {total}", 8, 4)

    doc.heading("Schedule")
    doc.line(
        "Durations and dependencies only. Calendar dates are not calculated: the canonical "
        "construction order (BP-07A) is not yet decided.",
        8,
        4,
    )
    for e in view["schedule"]:
        floor = f" floor {e['floor']}" if e["floor"] is not None else ""
        after = ", ".join(e["predecessors"]) or "none entered"
        doc.line(
            f"{e['entry_key']} {e['stage_name']}{floor}: {e['duration_days']} days; after: {after}",
            8,
            4,
        )

    doc.heading("Scope")
    for name in ("inclusions", "exclusions", "assumptions"):
        doc.line(name.capitalize(), 10, 6)
        for item in view["scope"][name]:
            doc.line(f"- {item}", 8, 4)
    if view["scope"]["explanation_note"]:
        doc.line(f"Note: {view['scope']['explanation_note']}", 8, 4)

    doc.heading("Structural sign-off")
    for s in [x for x in view["signoffs"] if x["state"] == "SIGNED"]:
        doc.line(
            f"{s['line_code']}: {s['engineer_name']} {s['engineer_firm'] or ''}, registration "
            f"{s['registration_number'] or '-'} ({s['registration_issuer'] or '-'}), "
            f"{s['mode']}, statement version {s['statement_version']}, {s['signed_at']}",
            8,
            4,
        )
    for number, text in view["statements"].items():
        doc.line(f"Statement version {number}: {text}", 8, 4)

    doc.heading("Revision history")
    for h in view["history"]:
        doc.line(
            f"Version {h['version_no']}: {h['state']}, issued {h['issued_at']}"
            + (f", closed {h['closed_at']} ({h['close_reason']})" if h["closed_at"] else ""),
            8,
            4,
        )

    if accepted_copy and view.get("acceptance"):
        doc.heading("Homeowner acceptance")
        a = view["acceptance"]
        doc.line(f"Accepted: {a['accepted_at']}", 9, 5)
        doc.line(f"Content hash accepted: {a['content_hash']}", 8, 4)
        doc.line(f"Issued document sha256: {a['issued_document_sha256']}", 8, 4)
        doc.line(f"Statement: {a['statement']}", 8, 4)

    doc.line(footer, 7, 4)
    return bytes(pdf.output())
