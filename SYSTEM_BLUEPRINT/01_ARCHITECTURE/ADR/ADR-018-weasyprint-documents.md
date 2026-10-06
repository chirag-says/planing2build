# ADR-018: WeasyPrint for PDF rendering from the same HTML templates as the web view

| Item | Value |
|---|---|
| Status | **Superseded by ADR-023 (Chirag, 2026-10-05).** Never accepted; not applicable to any document type. fpdf2 renders Build Plan PDFs, invoices and credit notes |
| Deciders | Sakha (proposal) |
| Related | INTEGRATION_ARCHITECTURE.md section 8, ADR-002, ADR-011 |

## Context

The platform issues Build Plans, quote reviews, comparisons, inspection reports (team and plain-language versions), receipts, invoices, credit notes, estimate PDFs and build record exports. S05 P3 requires that the PDF equals the web link render and is legible on a phone; BR-058 requires Build Plan generation within 30 seconds.

## Decision

Documents are rendered in the worker by WeasyPrint from HTML and CSS templates (Jinja2) that share data models and most markup with the web views; fonts are bundled; rendering runs on the `render` queue with a 120-second timeout and three retries; outputs are immutable objects with a stored hash.

## Why

- HTML and CSS templates are maintainable by the same developers who build the web screens, and the web view and the PDF come from one source of truth.
- WeasyPrint is a Python library (no browser process), deterministic, and fast enough: a 40-page Build Plan renders in seconds on one vCPU.
- No headless Chromium to run, patch and feed memory on a small VPS.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Headless Chromium (Playwright or Puppeteer) | Pixel-perfect CSS support, but 300 to 500 MB per render process on an 8 GB host and a browser to keep patched; use only if WeasyPrint's CSS coverage proves insufficient for a template |
| ReportLab or a programmatic PDF library | Layouts in code diverge from the web view; slower to iterate |
| A hosted PDF API (DocRaptor, PDFShift) | Sends Build Plans and inspection reports to a third party |
| Office documents (DOCX) | The sources ask for PDF and a web record; DOCX is editable and not suitable for issued records |

## Consequences

- Templates avoid CSS features WeasyPrint does not support (some flexbox and grid cases); a template lint and a render test per document type catch regressions.
- Memory spikes to a few hundred megabytes during large renders; the worker's limit accounts for it; images in templates are thumbnails.

## Migration path

Templates are HTML; a switch to Chromium rendering changes the renderer function, not the templates or the pipeline.
