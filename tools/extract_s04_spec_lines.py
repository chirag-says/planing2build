"""Regenerate the 67-line specification master seed from S04 (read-only).

S04 is `SOURCE_OF_TRUTH/Plan2Build_Specification_Schema.docx`, the product-owner-approved v1 seed
(Chirag, 2026-10-04, ruling 2.5). This script reads its line tables (packages A, B, C), the
package table and the long-lead table, applies the rulings, and writes
`apps/api/migrations/data/spec_lines_v1.json`. Run it to check the committed seed still equals
S04: `python tools/extract_s04_spec_lines.py --check` exits 1 on any difference.

Rulings applied (no other change to S04's values):
- Lines whose code carries † are structural. Their brand category is removed and not replaced
  (D-03 for A04, A05, A09, A12, A13; 2.4 for A01, 2026-10-04); S04's original text is kept in
  `s04_brand_category` for traceability, and the line carries engineer sign-off PENDING (2.4, 2.5).
- "—" or blank in S04 means no value (no brand product, nothing verifiable).
- Long-lead flags come from S04's lead-time table only (IHB_FLOW F-075).
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
S04 = REPO / "SOURCE_OF_TRUTH" / "Plan2Build_Specification_Schema.docx"
OUT = REPO / "apps" / "api" / "migrations" / "data" / "spec_lines_v1.json"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NONE = {"", "—", "-", "–"}


def tables() -> list[list[list[str]]]:
    root = ET.fromstring(zipfile.ZipFile(S04).read("word/document.xml"))
    body = root.find(W + "body")
    assert body is not None
    return [
        [["".join(t.text or "" for t in cell.iter(W + "t")).strip() for cell in row.findall(W + "tc")]
         for row in table.iter(W + "tr")]
        for table in body.iter(W + "tbl")
    ]  # fmt: skip


def value(text: str) -> str | None:
    return None if text.strip() in NONE else text.strip()


def build() -> dict[str, object]:
    t = tables()
    packages = []
    for row in t[3][1:]:
        code, _, name = row[0].partition("—")
        packages.append({"code": code.strip(), "name": name.strip(), "issued": row[1]})
    long_lead: set[str] = set()
    for row in t[10][1:]:
        long_lead.update(re.findall(r"\b([ABC]\d{2})\b", row[1]))
    lines = []
    for table in t[5:8]:
        for row in table[1:]:
            code_cell, item, spec, stage, decide, verified, brand = (row + [""] * 7)[:7]
            code = code_cell.replace("†", "").strip()
            structural = "†" in code_cell
            lines.append(
                {
                    "code": code,
                    "package": code[0],
                    "item": item,
                    "performance_specification": spec,
                    "consuming_stages": [int(n) for n in re.findall(r"\d+", stage)],
                    "decide_by_weeks": int(re.match(r"(\d+)", decide).group(1)),  # type: ignore[union-attr]
                    "verified_at": value(verified),
                    "brand_category": None if structural else value(brand),
                    "s04_brand_category": value(brand),
                    "is_structural": structural,
                    "is_long_lead": code in long_lead,
                    "engineer_signoff": "PENDING" if structural else "NOT_REQUIRED",
                }
            )
    return {
        "version": 1,
        "source": "S04 Plan2Build_Specification_Schema.docx, tables 3, 5 to 7 and 10",
        "approved_note": "Product-owner-approved v1 seed (Chirag, 2026-10-04, rulings 2.4 and 2.5)",
        "packages": packages,
        "lines": lines,
    }


def main() -> int:
    data = build()
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if "--check" in sys.argv:
        same = OUT.read_text(encoding="utf-8") == text
        print("seed equals S04" if same else "seed DIFFERS from S04")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(data['lines'])} lines")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    sys.exit(main())
