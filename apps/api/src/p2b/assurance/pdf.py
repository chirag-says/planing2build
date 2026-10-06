"""The inspection report (EX-14, ADR-023): a plain-language main report and a technical
appendix, rendered with fpdf2 only when operations approve, from the frozen inspection content.
Deterministic: the creation date is the approval time, so the same snapshot gives the same bytes.
No AI wording, no supplier, brand, product, price or homeowner contact. English only (ADR-022).
The wording is a draft awaiting approval (production blocker V)."""

from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF, XPos, YPos

from p2b.core.config import Settings

FLOORS = {-1: "basement", 0: "ground floor", 1: "first floor", 2: "second floor",
          3: "third floor"}  # fmt: skip
RESULT_WORDS = {
    "PASS": "Passed",
    "OBSERVATION": "Passed with an observation",
    "NON_CONFORMANCE": "Needs correction",
    "NOT_APPLICABLE": "Not applicable",
}


def _text(unicode_font: bool, value: object) -> str:
    text = "" if value is None else str(value)
    return text if unicode_font else text.encode("latin-1", "replace").decode("latin-1")


def outcome(snapshot: dict[str, Any]) -> str:
    """One plain sentence, counted from the recorded results only."""
    points = snapshot["checkpoints"]
    corrections = sum(1 for p in points if p.get("result") == "NON_CONFORMANCE")
    observations = sum(1 for p in points if p.get("result") == "OBSERVATION")
    if snapshot["kind"] == "REINSPECTION":
        closed = sum(1 for p in points if p.get("result") == "PASS")
        return (
            f"Re-inspection: {closed} of {len(points)} earlier findings confirmed corrected; "
            f"{corrections} still need correction."
        )
    if corrections:
        return f"{corrections} item(s) need correction before this gate can be passed."
    if observations:
        return f"Passed, with {observations} observation(s) to note."
    return "Passed: no item needs correction."


def render_report(
    settings: Settings, snapshot: dict[str, Any], *, version: int, correction_reason: str | None
) -> bytes:
    approved = datetime.fromisoformat(snapshot["approved_at"])
    pdf = FPDF(format="A4")
    pdf.set_creation_date(approved)
    pdf.set_producer("Plan2Build")
    pdf.set_creator("Plan2Build")
    pdf.set_title(f"Inspection report {snapshot['project_code']} gate {snapshot['gate']}")
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

    floor = snapshot["floor"]
    where = snapshot["stage"] + (f", {FLOORS.get(floor, f'floor {floor}')}" if floor is not None
                                 else "")  # fmt: skip
    pdf.add_page()
    line("Plan2Build inspection report", 18, 10)
    line(f"Project: {snapshot['project_code']}")
    line(f"Stage {snapshot['stage_number']}: {where}   Gate {snapshot['gate']}")
    kind = "Re-inspection" if snapshot["kind"] == "REINSPECTION" else "Inspection"
    line(f"{kind} by independent auditor {snapshot['auditor_code']} ({snapshot['auditor_name']}, "
         f"{snapshot['qualification']})")  # fmt: skip
    line(f"Approved by Plan2Build: {snapshot['approved_at']}   Report version {version}")
    if correction_reason:
        line(f"This version corrects an earlier report: {correction_reason}", 9, 5)
    if snapshot["staff_capture"]:
        line("Entered by Plan2Build from the auditor's signed report.", 8, 4)

    heading("Result")
    line(outcome(snapshot), 11, 6)
    if snapshot["summary"]:
        line(f"Auditor's summary: {snapshot['summary']}")

    findings = [p for p in snapshot["checkpoints"] if p.get("severity")]
    if findings:
        heading("What needs correcting")
        for p in findings:
            line(f"{p['text']} (severity recorded by the auditor: {p['severity']})", 10, 6)
            line(f"Found: {p['description']}", 9, 5)
            line(f"Correction required: {p['corrective_action']}   Due by: {p['due_date']}", 9, 5)
    observations = [p for p in snapshot["checkpoints"] if p.get("result") == "OBSERVATION"]
    if observations:
        heading("Observations")
        for p in observations:
            line(f"{p['text']}: {p.get('note') or 'noted'}", 9, 5)

    pdf.add_page()
    line("Technical appendix", 14, 8)
    line(f"Checklist version {snapshot['checklist_version']}. Content sha256 "
         f"{snapshot['content_sha256']}.", 8, 4)  # fmt: skip
    line(f"Scheduled {snapshot['scheduled_at']}; submitted {snapshot['submitted_at']}.", 8, 4)
    for p in snapshot["checkpoints"]:
        result = p.get("result")
        line(f"{p['code']}  {p['text']}", 9, 5)
        line(f"   Result: {RESULT_WORDS.get(result or '', 'Not recorded')}", 8, 4)
        for label, key in (("Note", "note"), ("Not applicable because", "na_reason"),
                           ("Measurement", "measurement"), ("Room", "room_tag")):  # fmt: skip
            if p.get(key):
                line(f"   {label}: {p[key]}", 8, 4)
        for e in p.get("evidence", []):
            line(f"   Evidence {e['file_id']} sha256 {e['sha256']}", 7, 4)
    line(f"{snapshot['project_code']}  gate {snapshot['gate']}  report version {version}", 7, 4)
    return bytes(pdf.output())
