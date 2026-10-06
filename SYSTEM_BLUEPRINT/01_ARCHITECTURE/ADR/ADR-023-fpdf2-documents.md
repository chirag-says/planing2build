# ADR-023: fpdf2 for issued PDFs (supersedes ADR-018)

| Item | Value |
|---|---|
| Status | Accepted (Chirag, 2026-10-05) |
| Deciders | Chirag (decision), Sakha (record) |
| Supersedes | ADR-018 (WeasyPrint), in full |
| Related | ADR-011, ADR-022, INTEGRATION_ARCHITECTURE.md section 8, SLICE3_5_IMPLEMENTATION_REPORT.md section F |

## Context

ADR-018 proposed WeasyPrint (HTML and CSS templates) for every PDF; it was never accepted. Invoices and credit notes (Slice 3.3) and the Build Plan (Slice 3.5) were built with fpdf2. The Build Plan PDF works, is deterministic, and is tested. WeasyPrint needs native Pango, Cairo and GDK-PixBuf libraries that are neither on the development machine nor in the image.

## Decision

- **Approved engine:** fpdf2 for:
  - Build Plan PDFs (the issued document and the accepted copy);
  - invoices and credit notes.
- **Layout:** built in code from one data source per document (for the Build Plan, the version snapshot that also feeds the web view and the RFQ manifest).
- **Determinism:** the creation date is the issue or acceptance time and the producer is fixed, so the same snapshot gives the same bytes. Outputs are immutable files with a stored sha256.
- **Fonts:** production needs a Unicode TTF font (`P2B_INVOICE_FONT_PATH`, already required). Without it, text is limited to Latin-1. English only (ADR-022); a Devanagari font is added with Hindi.
- **Rendering:** Build Plan PDFs render inside the issue and acceptance transactions, so an ISSUED version always has its document; a storage failure fails the issue. Invoices render in the `render` job.
- **Where ADR-018 still applies:** nowhere. WeasyPrint is not used. Later document types (quote reviews, comparisons, inspection reports, receipts, estimate PDFs, build record exports) use fpdf2 by default. A document that genuinely needs HTML and CSS layout needs a new ADR, which then weighs WeasyPrint or headless Chromium with their system-library and memory costs.

## Why

- It works today for both issued document families and is covered by tests (determinism, content, TEST banner).
- It is pure Python with no system libraries: the same behaviour on the development machine, in CI and in the worker image.
- It has a small memory footprint on the single VPS (ADR-005).

## Alternatives considered

| Alternative | Why not now |
|---|---|
| WeasyPrint (ADR-018) | System libraries to install and keep patched in every environment; not needed for the current text-and-table documents |
| Headless Chromium | 300 to 500 MB per render and a browser to patch |
| A hosted PDF API | Sends Build Plans to a third party |

## Consequences

- The PDF and the web view do not share a template; they share the snapshot data. The web view and the PDF can differ in presentation, never in content.
- Layout changes are code changes. The POC documents are plain (lines and simple tables). A designed layout is a later UI pass, inside this ADR unless HTML layout becomes necessary.
- The 30-second target (BR-058) holds for the current documents (synchronous render in tests).

## Migration path

The Build Plan renderer is one function (`buildplan/pdf.py: render(settings, view, ...)`) taking the snapshot. Another engine replaces that function without touching the version, sign-off, acceptance or storage model.
